---
name: tech-summary
description: 为技术文章或开源项目生成结构化中文摘要
allowed-tools:
  - Read
  - Write
---

# 技术摘要生成技能

## 触发条件

当需要为原始数据条目生成摘要和标签时激活。

## 执行步骤

1. 读取原始条目的标题、描述、元数据
2. 生成 2-3 句话的中文摘要
3. 自动打标签（从预定义标签集中选择）
4. 计算相关性评分（0.0-1.0）

## 标签集

`llm`, `agent`, `rag`, `mcp`, `reasoning`, `fine-tuning`, `multimodal`, `code-gen`, `evaluation`, `deployment`

## 摘要规范

- 语言：中文
- 长度：50-150 字
- 结构：一句话概括 + 关键技术点 + 适用场景
- 避免主观评价（"很好""不错"），使用客观描述
