# astrbot-plugin-identity-name

一个用于 AstrBot 的插件：
- 在每次 LLM 聊天前自动识别当前账号身份
- 生成稳定身份锚点（`platform + conversation_id + user_id`）
- 注入系统约束，降低“认错人/串上下文”的概率

> 不提供任何聊天指令，全部逻辑在 LLM 请求前自动完成。

## 功能说明

1. **自动身份识别（无指令）**
   - 从事件上下文兜底提取：`platform`、`user_id`、`conversation_id`。
2. **稳定身份锚点**
   - 生成 `session_key = platform:conversation_id:user_id`。
3. **LLM 前置约束注入**
   - 自动插入 system 提示，要求模型严格基于当前身份锚点回答。
   - 若出现身份冲突或信息不足，先澄清再继续。

## 文件结构

- `main.py`：插件主逻辑
- `plugin.yaml`：插件元信息

## 注意

不同 AstrBot 版本和适配器的事件字段可能略有差异。
如果你当前版本 Hook 名称或签名不同，可在 `main.py` 中调整回调签名。
