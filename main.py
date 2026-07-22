"""
AstrBot 插件：user_recognizer
--------------------------------
让 AstrBot 分清不同用户的桌宠，无需任何斜杠指令。

识人来源（优先级从高到低）：
  1. 手动档案：档案文件里保存的 name（可通过自然语言更新）
  2. 桌宠 config.json 里的 nickname：桌宠发消息时会带在 sender.nickname 里
  3. 平台 sender_name：兜底

自动学习：
  监听每条用户消息，用正则匹配"我叫XX / 我是XX / 叫我XX / 你可以叫我XX"，
  自动把名字写进档案，之后 LLM 就会用这个名字称呼 ta。

注入方式：
  在 on_llm_request 阶段，把身份信息追加到 system_prompt。
"""

import json
import os
import re
import time
from typing import Dict, Any, Optional

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.provider import ProviderRequest


# ------------------------------------------------------------------
# 档案存储
# ------------------------------------------------------------------
class ProfileStore:
    """JSON 文件存档，量小时够用"""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.warning(f"[user_recognizer] 档案加载失败：{e}")
                self._data = {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[user_recognizer] 档案保存失败：{e}")

    def get(self, uid: str) -> Dict[str, Any]:
        return self._data.get(str(uid), {})

    def upsert(self, uid: str, **fields):
        uid = str(uid)
        prof = self._data.get(uid, {})
        prof.update({k: v for k, v in fields.items() if v is not None})
        prof["updated_at"] = int(time.time())
        if "created_at" not in prof:
            prof["created_at"] = int(time.time())
        self._data[uid] = prof
        self._save()


# ------------------------------------------------------------------
# 自然语言里的自我介绍抽取
# ------------------------------------------------------------------
# 名字通常是 1~10 个中英字符/数字，禁止吃到标点或语气词
_NAME_CHARS = r"[\u4e00-\u9fa5A-Za-z0-9_·\-]{1,10}"

# 各种表达"我叫/我是/叫我"的方式
_INTRO_PATTERNS = [
    re.compile(rf"(?:^|[^\w])(?:我(?:的名字)?(?:叫做?|是|名字?叫))\s*({_NAME_CHARS})"),
    re.compile(rf"(?:^|[^\w])(?:你可以)?叫我\s*({_NAME_CHARS})"),
    re.compile(rf"(?:^|[^\w])请?叫我\s*({_NAME_CHARS})"),
    re.compile(rf"(?:^|[^\w])my name is\s+({_NAME_CHARS})", re.IGNORECASE),
    re.compile(rf"(?:^|[^\w])i(?:'m| am)\s+({_NAME_CHARS})", re.IGNORECASE),
]

# 一些容易误匹配的词，避免把这些当成"名字"
_NAME_BLACKLIST = {
    "谁", "你", "我", "他", "她", "它", "谁啊", "哪位",
    "不", "不是", "没", "没有", "什么", "啥", "谁呀", "个",
    "很", "有", "在", "的", "了",
}


def extract_name_from_text(text: str) -> Optional[str]:
    """从自然语言里抽出用户名字；抽不到就返回 None"""
    if not text:
        return None
    for pat in _INTRO_PATTERNS:
        m = pat.search(text)
        if m:
            name = m.group(1).strip()
            if name and name not in _NAME_BLACKLIST:
                return name
    return None


# ------------------------------------------------------------------
# 主体
# ------------------------------------------------------------------
@register(
    "user_recognizer",
    "KanadePet",
    "无指令识人：从桌宠 nickname + 自然语言里学习用户身份，并在 LLM 请求前注入上下文",
    "1.1.0",
)
class UserRecognizer(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        data_dir = os.path.join("data", "plugin_data", "user_recognizer")
        self.store = ProfileStore(os.path.join(data_dir, "profiles.json"))
        logger.info("[user_recognizer] 加载完成")

    # -------------------- 消息前钩子：自然语言学习 --------------------
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def learn_from_message(self, event: AstrMessageEvent):
        """
        每收到一条用户消息就调用一次。
        - 记录 sender.nickname（桌宠 config 里配的那个称呼）作为 nickname 字段
        - 从消息文本里尝试抽名字（"我叫小明"这种），抽到就写入 name 字段
        不产生任何回复（该协程不 yield 结果）。
        """
        uid = str(event.get_sender_id())
        sender_nick = event.get_sender_name() or ""
        text = event.message_str or ""

        updates: Dict[str, Any] = {}
        prof = self.store.get(uid)

        # 桌宠传来的 nickname —— 每次都刷新一下（用户可能改了 config）
        if sender_nick and prof.get("nickname") != sender_nick:
            updates["nickname"] = sender_nick

        # 自然语言里抽名字（优先级更高，覆盖 name 字段）
        name = extract_name_from_text(text)
        if name and prof.get("name") != name:
            updates["name"] = name
            updates["name_source"] = "learned"
            logger.info(f"[user_recognizer] 学到 {uid} 叫「{name}」")

        if updates:
            self.store.upsert(uid, **updates)

    # -------------------- LLM 请求前：注入身份上下文 --------------------
    @filter.on_llm_request()
    async def inject_identity(self, event: AstrMessageEvent, req: ProviderRequest):
        uid = str(event.get_sender_id())
        prof = self.store.get(uid)

        # 决定该怎么称呼对方
        addr = (
            prof.get("name")
            or prof.get("nickname")
            or event.get_sender_name()
            or f"user_{uid}"
        )

        lines = [
            "【当前正在与你对话的人】",
            f"- 内部标识 user_id: {uid}",
            f"- 你应当称呼 ta 为: {addr}",
        ]
        if prof.get("nickname") and prof.get("nickname") != addr:
            lines.append(f"- ta 的桌宠里自称: {prof['nickname']}")
        if prof.get("about"):
            lines.append(f"- 关于 ta: {prof['about']}")
        if prof.get("note"):
            lines.append(f"- 你的私人备注: {prof['note']}")

        lines.append(
            "重要：不同的 user_id 是完全不同的人，请不要把他们的记忆、称呼、"
            "喜好混在一起。回复时自然地使用上面提到的称呼即可。"
        )

        block = "\n".join(lines)
        if req.system_prompt:
            req.system_prompt = req.system_prompt.rstrip() + "\n\n" + block
        else:
            req.system_prompt = block

    async def terminate(self):
        logger.info("[user_recognizer] 卸载")
