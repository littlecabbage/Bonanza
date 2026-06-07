# Bonanza

**模块化投资研究 Skill 集合** — 由 Agent 编排的多步投资分析工具。

> money loves me

## 当前状态

正在进行从单体 Skill 到模块化 Skill 的重构。当前仓库同时包含：
- 旧单体入口 `opencli-investment-report`
- 新模块化 Skill（逐步迁移中）

### 当前 Skill 结构

```text
skills/
└── opencli-investment-report/      ← 旧单体 Skill（迁移中）
    ├── SKILL.md
    └── references/
        ├── bloggers.json
        ├── report-template.html
        └── stock-codes.json
```

### 目标 Skill 结构

重构完成后将包含 11 个单点 Skill：

```text
skills/
├── guide-investment-workflow/      ← 流程导航
├── collect-blogger-updates/        ← 博主动态采集
├── collect-market-overview/        ← 市场概览采集
├── collect-market-sentiment/       ← 市场情绪采集
├── collect-capital-movements/      ← 资金异动采集
├── collect-market-news/            ← 财经快讯采集
├── extract-investment-entities/    ← 实体识别
├── fetch-stock-quotes/             ← 行情查询
├── analyze-investment-signals/     ← 综合信号分析
├── build-investment-scenarios/     ← 可选情景推演
├── render-investment-report/       ← 确定性 HTML 渲染
└── opencli-investment-report/      ← 旧兼容入口（迁移后只保留引导）
```

每个 Skill 只完成一个明确任务，Agent 每轮默认只调用一个 Skill。

## 验证命令

```bash
# 仓库级测试
python3 -m unittest discover -s tests -v

# 仓库结构验证
python3 scripts/validate_repository.py

# 单个 Skill 验证
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>
```

## 已知基线问题

当前旧模板存在以下问题（将在 Task 8 修复）：

1. **重复章节**：`<h2>一、投资建议（核心）</h2>` 在模板中出现两次
2. **CSS 类名不一致**：SKILL.md 使用 `.advice-buy-strong`，HTML 模板使用 `.advice-strong-buy`
3. **残留占位符**：模板包含约 30+ 个 `{{PLACEHOLDER}}` 占位符（模板本身正常，渲染后必须为零）

## 数据契约

所有 JSON 产物遵循统一顶层契约：

```json
{
  "schema_version": "1.0",
  "generated_at": "<ISO 8601 with timezone>",
  "status": "complete | partial | failed",
  "source": { "skill": "<skill-name>", "commands": [] },
  "coverage": { "requested": 0, "succeeded": 0, "failed": 0 },
  "errors": [],
  "data": {}
}
```

## 运行产物目录

完整报告流程默认写入：

```text
.bonanza/runs/<YYYY-MM-DD>-<run-id>/
```

单点任务允许用户指定其他输出路径。