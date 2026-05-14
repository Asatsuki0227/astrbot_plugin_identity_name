from __future__ import annotations
from typing import Any

try:
    from astrbot.api.plugin import Star
except ImportError:
    class Star: pass

class IdentityNamePlugin(Star):
    def __init__(self, context: Any = None, **kwargs) -> None:
        super().__init__()
        self.context = context

    def _pick_first(self, obj: dict[str, Any], keys: list[str]) -> Any:
        for key in keys:
            # 增加对字典嵌套的简单支持
            if key in obj and obj[key] not in (None, "", "null"):
                return obj[key]
        return None

    async def before_llm_request(self, session: Any, messages: list[dict[str, str]], event: Any) -> list[dict[str, str]]:
        if not isinstance(messages, list) or len(messages) == 0:
            return messages

        # 提取数据
        data = getattr(event, "__dict__", {}) if not isinstance(event, dict) else event
        
        # 1. 更加激进的昵称搜索：增加对戳一戳事件中 sender 字段的穿透
        name = self._pick_first(data, ["sender_name", "nickname", "sender", "user_name"])
        
        # 针对“戳一戳”等特殊事件，如果 name 是字典，尝试取其中的 nickname
        if isinstance(name, dict):
            name = name.get("nickname") or name.get("card") or name.get("user_id")

        if not name or str(name).isdigit(): # 如果名字全是数字，说明没抓到昵称
            uid = self._pick_first(data, ["user_id", "sender_id", "uid"])
            name = f"用户_{str(uid)[:4]}" if uid else "访客"

        # 2. 构造绝对指令
        identity_instr = (
            f"【系统级身份锁定】当前对话的用户叫“{name}”。\n"
            f"请在回复中直接称呼对方为“{name}”，禁止提到任何 QQ 号或“3907203281”。"
        )

        # 3. 注入消息
        if isinstance(messages[0], dict) and messages[0].get("role") == "system":
            messages[0]["content"] = identity_instr + "\n" + str(messages[0].get("content", ""))
        else:
            messages.insert(0, {"role": "system", "content": identity_instr})

        return messages
