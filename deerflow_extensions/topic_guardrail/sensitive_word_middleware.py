import logging
import os
import time

import yaml
import ahocorasick

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

try:
    from topic_guardrail.text_preprocessor import preprocess
except ImportError:
    from text_preprocessor import preprocess

logger = logging.getLogger(__name__)


class SensitiveWordMiddleware(AgentMiddleware[AgentState]):
    """
    NeMo Input/Output Rails 模式的敏感词检查中间件。

    在 LLM 调用前（before_model）检查用户输入文本是否含敏感词。
    在 LLM 调用后（after_model）检查模型输出文本是否含敏感词。

    架构：
      TextPreprocessor → AC Automaton
      Fail-closed: 任何异常均拒绝而非放行
    """

    name = "sensitive_word"

    def __init__(self, config_path: str = None):
        super().__init__()
        self._base_dir = os.path.dirname(os.path.abspath(__file__))
        self._automaton = None
        self._whitelist: set[str] = set()
        self._preprocessor = preprocess

        self._load_config(config_path)
        self._build_automaton()
        self._load_whitelist()

    def _load_config(self, config_path):
        if config_path is None:
            config_path = os.path.join(self._base_dir, "topics.yaml")
        elif not os.path.isabs(config_path):
            config_path = os.path.join(self._base_dir, config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        tc = config.get("tool_control", {})
        self._wordlist_cfg = tc.get("wordlist", {})

    def _resolve_word_path(self, rel_path):
        if not rel_path:
            return None
        path = os.path.join(self._base_dir, rel_path)
        return path if os.path.isfile(path) else None

    def _build_automaton(self):
        self._automaton = ahocorasick.Automaton()
        count = 0
        for key in ("base", "custom"):
            rel_path = self._wordlist_cfg.get(key)
            if not rel_path:
                continue
            abs_path = self._resolve_word_path(rel_path)
            if abs_path is None:
                continue
            with open(abs_path, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        self._automaton.add_word(word, word)
                        count += 1
        self._automaton.make_automaton()
        logger.info("SensitiveWord AC automaton built with %d words", count)

    def _load_whitelist(self):
        rel_path = self._wordlist_cfg.get("whitelist")
        if not rel_path:
            return
        abs_path = self._resolve_word_path(rel_path)
        if abs_path is None:
            return
        with open(abs_path, "r", encoding="utf-8") as f:
            self._whitelist = {
                l.strip() for l in f if l.strip() and not l.startswith("#")
            }

    def _is_whitelisted(self, word: str) -> bool:
        if not self._whitelist:
            return False
        if word in self._whitelist:
            return True
        for wl in self._whitelist:
            if word in wl or wl in word:
                return True
        return False

    def _has_sensitive(self, text: str) -> bool:
        if not text:
            return False
        if self._automaton is None:
            logger.critical("SensitiveWord AC automaton is None — blocking all input!")
            return True
        try:
            for _, word in self._automaton.iter(text):
                if not self._is_whitelisted(word):
                    return True
        except Exception:
            logger.exception("SensitiveWord AC automaton error — blocking")
            return True
        return False

    def _get_last_user_message(self, state) -> str | None:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                content = msg.content
                return str(content) if content else None
        return None

    def _get_last_ai_message(self, state) -> str | None:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                content = msg.content
                return str(content) if content else None
        return None

    def _build_blocked(self, reason: str = "sensitive_word") -> AIMessage:
        logger.info("AUDIT|BLOCKED|reason=%s|ts=%s", reason, time.strftime("%Y-%m-%dT%H:%M:%S"))
        refusal = "您的请求涉及不允许的内容，已被系统拒绝。"
        return AIMessage(content=refusal)

    def before_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        text = self._get_last_user_message(state)
        if not text:
            return None

        clean_text, _ = self._preprocessor(text)

        if self._has_sensitive(clean_text):
            logger.warning("SensitiveWord BLOCKED: text=%.80s", text)
            return {"messages": [self._build_blocked(reason="ac_automaton")]}

        return None

    async def abefore_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self.before_model(state, runtime)

    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        text = self._get_last_ai_message(state)
        if text and self._has_sensitive(text):
            logger.warning("SensitiveWord Output blocked: text=%.80s", text)
            return {"messages": [self._build_blocked(reason="ac_automaton_output")]}
        return None

    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self.after_model(state, runtime)
