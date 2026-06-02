import logging
import os
import re

import yaml
import ahocorasick

from deerflow.guardrails.provider import GuardrailDecision, GuardrailReason, GuardrailRequest

logger = logging.getLogger(__name__)


class TopicGuardrailProvider:
    """工具调用层面的护栏：不判断话题语义，只判断工具调用是否能放行。

    L3 硬拦截策略：
    1. denied_tools（如 bash）→ 直接禁止
    2. content_check_tools（web_search/web_fetch）→ 搜索词 AC 自动机敏感词扫描
    3. 其他业务工具（ADS MCP / DeepRAG）→ 直接放行
    """

    name = "topic_guardrail"

    def __init__(self, config_path: str = None):
        self._base_dir = os.path.dirname(os.path.abspath(__file__))
        self._denied_tools: set[str] = set()
        self._content_check_tools: set[str] = set()
        self._patterns: list[re.Pattern] = []
        self._whitelist: set[str] = set()
        self._automaton = None

        self._load_config(config_path)
        self._build_automaton()
        self._load_whitelist()

    def _load_config(self, config_path: str | None):
        if config_path is None:
            config_path = os.path.join(self._base_dir, "topics.yaml")
        elif not os.path.isabs(config_path):
            config_path = os.path.join(self._base_dir, config_path)

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        tc = config.get("tool_control", {})
        self._denied_tools = set(tc.get("denied_tools", []))
        self._content_check_tools = set(tc.get("content_check_tools", []))
        self._patterns = [re.compile(p) for p in tc.get("patterns", [])]
        self._wordlist_cfg = tc.get("wordlist", {})

    def _resolve_word_path(self, relative_path: str) -> str | None:
        if not relative_path:
            return None
        path = os.path.join(self._base_dir, relative_path)
        return path if os.path.isfile(path) else None

    def _build_automaton(self):
        self._automaton = ahocorasick.Automaton()
        word_count = 0

        for key in ("base", "custom"):
            rel_path = self._wordlist_cfg.get(key)
            if not rel_path:
                continue
            abs_path = self._resolve_word_path(rel_path)
            if abs_path is None:
                logger.warning("词库文件不存在: %s", rel_path)
                continue
            with open(abs_path, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        self._automaton.add_word(word, word)
                        word_count += 1

        self._automaton.make_automaton()
        logger.info("TopicGuardrail: AC自动机构建完成，共 %d 个敏感词", word_count)

    def _load_whitelist(self):
        rel_path = self._wordlist_cfg.get("whitelist")
        if not rel_path:
            return
        abs_path = self._resolve_word_path(rel_path)
        if abs_path is None:
            logger.warning("白名单文件不存在: %s", rel_path)
            return
        with open(abs_path, "r", encoding="utf-8") as f:
            self._whitelist = {
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            }
        logger.info("TopicGuardrail: 白名单加载完毕，共 %d 个词", len(self._whitelist))

    def _extract_text(self, tool_input: dict) -> str:
        texts = []
        if isinstance(tool_input, dict):
            for v in tool_input.values():
                if isinstance(v, str):
                    texts.append(v)
                elif isinstance(v, list):
                    texts.extend(str(item) for item in v if isinstance(item, str))
        return " ".join(texts)

    def _check_automaton(self, text: str) -> list[str]:
        hits = []
        if self._automaton is None:
            return hits
        try:
            for _, word in self._automaton.iter(text):
                if self._is_whitelisted(word):
                    continue
                hits.append(word)
        except AttributeError:
            pass
        return hits

    def _is_whitelisted(self, word: str) -> bool:
        if not self._whitelist:
            return False
        if word in self._whitelist:
            return True
        for wl_word in self._whitelist:
            if word in wl_word or wl_word in word:
                return True
        return False

    def _check_patterns(self, text: str) -> list[str]:
        hits = []
        for p in self._patterns:
            m = p.search(text)
            if m:
                hits.append(m.group())
        return hits

    def evaluate(self, request: GuardrailRequest) -> GuardrailDecision:
        if request.tool_name in self._denied_tools:
            logger.warning(
                "TopicGuardrail denied: tool=%s policy=denied_tools",
                request.tool_name,
            )
            return GuardrailDecision(
                allow=False,
                reasons=[
                    GuardrailReason(
                        code="topic_guardrail.tool_denied",
                        message=f"Tool '{request.tool_name}' is not allowed.",
                    )
                ],
            )

        if request.tool_name in self._content_check_tools:
            text = self._extract_text(request.tool_input)
            if not text:
                return GuardrailDecision(
                    allow=True,
                    reasons=[GuardrailReason(code="topic_guardrail.allowed")],
                )

            hits = self._check_automaton(text)
            pattern_hits = self._check_patterns(text)
            all_hits = hits + pattern_hits

            if all_hits:
                logger.warning(
                    "TopicGuardrail denied: tool=%s policy=denylist hits=%s text=%.100s",
                    request.tool_name,
                    all_hits,
                    text,
                )
                return GuardrailDecision(
                    allow=False,
                    reasons=[
                        GuardrailReason(
                            code="topic_guardrail.denied",
                            message=f"Sensitive content detected in search query: {all_hits}",
                        )
                    ],
                )

        return GuardrailDecision(
            allow=True,
            reasons=[GuardrailReason(code="topic_guardrail.allowed")],
        )

    async def aevaluate(self, request: GuardrailRequest) -> GuardrailDecision:
        return self.evaluate(request)
