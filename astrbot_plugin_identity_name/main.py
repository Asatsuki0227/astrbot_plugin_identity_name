from __future__ import annotations

from typing import Any


class IdentityNamePlugin:
    """AstrBot 插件：在 LLM 聊天前注入稳定身份锚点，减少认错人。"""

    def __init__(self, ctx: Any = None) -> None:
        self.ctx = ctx

    def _pick_first(self, obj: dict[str, Any], keys: list[str]) -> Any:
        for key in keys:
            if key in obj and obj[key] not in (None, ""):
                return obj[key]
        return None

    def _to_dict(self, event: Any) -> dict[str, Any]:
        if isinstance(event, dict):
            return event
        return getattr(event, "__dict__", {})

    def _extract_identity(self, event: Any) -> dict[str, str] | None:
        data = self._to_dict(event)

        platform = self._pick_first(data, ["platform", "adapter", "source"])
        user_id = self._pick_first(data, ["user_id", "sender_id", "uid", "from_id"])
        conversation_id = self._pick_first(
            data,
            ["conversation_id", "session_id", "chat_id", "group_id", "channel_id"],
        )

        if user_id is None:
            return None

        platform_str = str(platform or "unknown")
        user_id_str = str(user_id)
        conversation_id_str = str(conversation_id) if conversation_id is not None else "direct"

        return {
            "platform": platform_str,
            "user_id": user_id_str,
            "conversation_id": conversation_id_str,
            "session_key": f"{platform_str}:{conversation_id_str}:{user_id_str}",
        }

    async def before_llm_request(
        self,
        session: Any,
        messages: list[dict[str, str]],
        event: Any,
    ) -> list[dict[str, str]]:
        """仅在 LLM 请求前注入身份约束，不提供任何命令。"""
        identity = self._extract_identity(event)
        if not identity:
            return messages

        system_prompt = (
            "你正在与一个已锚定身份的用户对话。"
            f"身份锚点: platform={identity['platform']}, "
            f"conversation_id={identity['conversation_id']}, "
            f"user_id={identity['user_id']}, "
            f"session_key={identity['session_key']}。"
            "请只基于该身份锚点理解上下文，不要混入其他用户的信息。"
            "当对话出现身份冲突或信息不足时，先澄清身份再继续回答。"
        )

        return [{"role": "system", "content": system_prompt}, *messages]
