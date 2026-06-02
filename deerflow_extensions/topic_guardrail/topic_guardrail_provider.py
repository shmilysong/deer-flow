import logging
import os

import yaml

from deerflow.guardrails.provider import GuardrailDecision, GuardrailReason, GuardrailRequest

logger = logging.getLogger(__name__)


class TopicGuardrailProvider:
    """工具调用层面的护栏：只禁止 denied_tools，其余工具全部放行。

    职责：不判断话题语义，只判断工具名是否在禁止列表中。
    敏感词内容检查由 SensitiveWordMiddleware（before_model/after_model）负责。
    """

    name = "topic_guardrail"

    def __init__(self, config_path: str = None):
        self._base_dir = os.path.dirname(os.path.abspath(__file__))
        self._denied_tools: set[str] = set()
        self._load_config(config_path)

    def _load_config(self, config_path: str | None):
        if config_path is None:
            config_path = os.path.join(self._base_dir, "topics.yaml")
        elif not os.path.isabs(config_path):
            config_path = os.path.join(self._base_dir, config_path)

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        tc = config.get("tool_control", {})
        self._denied_tools = set(tc.get("denied_tools", []))

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

        return GuardrailDecision(
            allow=True,
            reasons=[GuardrailReason(code="topic_guardrail.allowed")],
        )

    async def aevaluate(self, request: GuardrailRequest) -> GuardrailDecision:
        return self.evaluate(request)
