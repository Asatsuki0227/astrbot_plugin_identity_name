# astrbot_plugin_user_recognizer

让 AstrBot 自动分清不同用户的桌宠。**零指令，自然语言就能学名字。**

## 它解决了什么

多个朋友的桌宠连到同一个 AstrBot，机器人分不清谁是谁，回复千篇一律。这个插件让它：

- 自动记住每个 `user_id` 对应的称呼
- 在每次 LLM 请求前，把「你现在正在跟谁说话」写进 system prompt
- **无需任何斜杠指令**，用户说「我叫小明」「叫我阿华」就自动学会

## 识人来源（优先级）

1. **自然语言学习**：从对话里抽出 `我叫XX / 我是XX / 叫我XX / my name is XX / I'm XX`，写入档案
2. **桌宠 nickname**：桌宠 `config.json` 里的 `nickname` 字段，每条消息会带在 `sender.nickname` 里，插件会自动记录
3. **平台 sender_name**：作为兜底

只要三种里有一个能拿到名字，机器人就会用这个名字称呼对方。

## 安装

1. **把整个 `astrbot_plugin_user_recognizer` 目录**复制到 AstrBot 的插件目录：

   ```
   AstrBot根目录/data/plugins/astrbot_plugin_user_recognizer/
   ├── main.py
   ├── metadata.yaml
   └── README.md
   ```

2. **重启 AstrBot**（或在 WebUI 里点"重载插件"）

3. **完成**。不需要任何配置。

## 使用

用户什么都不用做。他们正常跟桌宠聊天，插件会：

- 第一次说话时，记录 `sender.nickname`（桌宠里配的称呼）
- 任何时候只要说到「我叫XX」「叫我XX」，就更新为新名字

想验证是否生效，让不同朋友的桌宠各发一句话，然后看 AstrBot 数据目录下：

```
data/plugin_data/user_recognizer/profiles.json
```

里面应该有多条记录，每条对应一个 `user_id`。

## 让不同桌宠的 nickname 区分开

在每个朋友的桌宠 `config.json` 里，把 `nickname` 改成他们本人的称呼，例如：

```json
{
  "ws_url": "ws://xxx:6700/ws",
  "self_id": "11111",
  "user_id": "3625408198",
  "nickname": "小明"      ← 这里改成朋友的名字
}
```

这样即使他没说过"我叫小明"，AstrBot 也会知道该叫他小明。

## 档案里存了些什么

`profiles.json` 结构：

```json
{
  "3625408198": {
    "nickname": "小明",           // 桌宠 config 里的称呼
    "name": "阿华",               // 自然语言学到的（优先级更高）
    "name_source": "learned",
    "created_at": 1720000000,
    "updated_at": 1720000123
  }
}
```

需要给某个用户加特殊备注（比如「他是同事，别开黄腔」），可以直接编辑这个 JSON，加个 `note` 字段：

```json
{
  "3625408198": {
    "name": "阿华",
    "note": "工作同事，只聊技术话题"
  }
}
```

保存后重启 AstrBot 即可生效。

## 卸载

把 `astrbot_plugin_user_recognizer` 目录删掉，重启 AstrBot。档案数据在 `data/plugin_data/user_recognizer/` 下，可以选择保留或一起删掉。
