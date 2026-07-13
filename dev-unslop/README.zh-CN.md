# Dev-Unslop

[English](README.md)

一个 Claude Code 插件，用于清除技术文档中的 AI 水话（slop）——包括文档、PR 回复、代码注释、README 和提交信息。

## 功能

检测并移除 AI 生成文本的常见模式：

- **清嗓子式开场** — 删除无信息量的前置铺垫
- **空洞形容词** — 用具体数字替换模糊修饰词（"鲁棒"、"无缝"）
- **结构性臃肿** — 打破"三段式"模板，让内容自然流动
- **AI 水印词** — "赋能"、"利用"、"不仅是 X 更是 Y"等 30+ 个高频信号
- **PR 过度客套** — 去掉"Great question!"等社交填充，直接进入技术讨论

遵循资深工程师的文字审美：不承载信息的句子，一律删除。

## 安装

```bash
# 复制到 Claude Code 插件目录
cp -r dev-unslop/ ~/.claude/plugins/dev-unslop/
```

## 使用

通过以下短语触发：

- "Clean up this README — remove the AI slop"
- "Unslop this PR description"
- "Rewrite this like a senior engineer"
- "Tighten up these code comments"
- "去水 — 把这个文档精炼一下"

Skill 会读取目标文本，剥离所有非核心内容，输出精炼版本并附上修改摘要。

## 不会做的事

- 不会添加新内容或展开论述
- 不会用一个水词替换另一个水词
- 不会把陈述句改成反问句
- 不会给已经足够简短的文本加总结
