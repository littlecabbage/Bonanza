# Bonanza - 模块化投资分析工作流

将投资分析从单体 Skill 拆分为 11 个独立模块化 Skill，通过编排器协调执行。

## 架构

```
用户请求 → 编排器（guide-investment-workflow）→ 模块化 Skill → JSON 输出 → HTML 报告
```

每个 Skill 独立职责，通过 JSON 契约交接数据，支持灵活编排。

## 用法

### 项目内快速验证 Skill

Claude Code 会从 `.claude/skills/` 目录加载 Skill。通过软连接，可以让项目内的 `skills/` 目录直接被 Claude Code 识别，无需复制到 `~/.claude/skills/`，实现开发即验证：

```bash
# 创建 .claude 目录并软连接 skills
mkdir -p .claude
ln -s ../skills .claude/skills
```

完成后项目结构如下：

```
.claude/
└── skills -> ../skills        # 软连接指向项目 skills/
skills/
├── collect-market-overview/
│   ├── SKILL.md
│   ├── market-overview.schema.json
│   └── scripts/
├── analyze-investment-signals/
│   ├── SKILL.md
│   ├── investment-signals.schema.json
│   └── scripts/
└── ...
```

**优势**：
- 修改 Skill 后立即可用，无需手动同步到 `~/.claude/skills/`
- 多项目间互不干扰，每个项目独立维护自己的 Skill 集
- Git 跟踪软连接，团队共享同一套配置

## 11 个模块化 Skill

### 数据采集（5 个）

| Skill | 职责 | 数据源 |
|-------|------|--------|
| `collect-blogger-updates` | 博主动态 | Twitter |
| `collect-market-overview` | 市场概览 | 东方财富（index-board, hot-rank, sectors） |
| `collect-market-sentiment` | 市场情绪 | 雪球（hot-stock, hot） |
| `collect-capital-movements` | 资金异动 | 东方财富（longhu, money-flow, northbound） |
| `collect-market-news` | 市场新闻 | 东方财富（kuaixun）、知乎（hot） |

### 数据处理（2 个）

| Skill | 职责 |
|-------|------|
| `extract-investment-entities` | 从文本识别股票/板块实体 |
| `fetch-stock-quotes` | 查询行情数据（A股/港股/美股统一使用 eastmoney quote） |

### 分析推理（2 个）

| Skill | 职责 |
|-------|------|
| `analyze-investment-signals` | 综合信号分析（价格、资金、情绪、事件四维度） |
| `build-investment-scenarios` | 情景推演（bullish/neutral/bearish） |

### 输出（1 个）

| Skill | 职责 |
|-------|------|
| `render-investment-report` | 确定性 HTML 报告渲染 |

### 编排（1 个）

| Skill | 职责 |
|-------|------|
| `guide-investment-workflow` | 状态感知工作流导航、下一步推荐 |

## 数据契约

所有 Skill 输出遵循统一 JSON Schema（各 `skills/<skill-name>/*.schema.json`）：

```json
{
  "schema_version": "1.0",
  "generated_at": "ISO-8601 with timezone",
  "status": "complete | partial | failed",
  "source": {"skill": "...", "commands": [...]},
  "coverage": {"requested": N, "succeeded": N, "failed": N},
  "errors": [...],
  "data": {...}
}
```

状态语义：
- `complete`: 所有必需请求成功
- `partial`: 部分成功，有可用数据
- `failed`: 全部失败，无可用数据

覆盖率：`requested = succeeded + failed`（按请求数，不按记录数）

## 测试

192 个测试覆盖：
- 结构测试：frontmatter、JSON 有效性、HTML 模板
- 命令契约测试：opencli 命令验证
- 行为测试：每个 Skill 的输入/输出/错误处理
- 集成测试：工作流编排、状态机、端到端场景

运行测试：
```bash
python3 -m unittest discover -s tests -v
```

验证仓库结构：
```bash
python3 scripts/validate_repository.py
```

## 工作流示例

完整报告流程：
1. `guide-investment-workflow` → 推荐从市场概览开始
2. `collect-market-overview` → `market-overview.json`
3. `extract-investment-entities` → `investment-entities.json`
4. `fetch-stock-quotes` → `stock-quotes.json`
5. `collect-blogger-updates` → `blogger-updates.json`
6. `collect-market-sentiment` → `market-sentiment.json`
7. `collect-capital-movements` → `capital-movements.json`
8. `collect-market-news` → `market-news.json`
9. `analyze-investment-signals` → `investment-signals.json`
10. `build-investment-scenarios` → `investment-scenarios.json`
11. `render-investment-report` → `investment-report.html`

编排器根据数据新鲜度（4 小时阈值）和状态动态推荐下一步，最多 3 个选项。

## 关键设计决策

1. **状态感知导航**：不仅检查文件存在，还验证状态、新鲜度、Schema 版本
2. **统一命令**：所有市场行情统一使用 `eastmoney quote`，不再区分市场
3. **Schema 一致性**：实体识别输出 `symbol`（非 `code`）、`confidence` 枚举（非浮点数）、`sector`（非 `industry`）
4. **时间格式**：统一 ISO-8601 带时区、无微秒
5. **确定性渲染**：HTML 由模板生成，不由 Agent 自由拼接

## 旧单体 Skill 处理

`skills/opencli-investment-report` 已删除：
- 功能已拆分到 11 个模块化 Skill
- 参考文件（bloggers.json, stock-codes.json）已复制到对应 Skill
- HTML 模板（report-template.html）问题已在 `render-investment-report` 中修复

## 开发完成清单

- [x] 5 个采集 Skill 脚本实现（mock opencli 调用）
- [x] 实体识别和行情查询修复（Schema 对齐、统一命令）
- [x] 综合信号分析（四维度证据收集）
- [x] 情景推演（三情景构建）
- [x] HTML 报告渲染（确定性模板）
- [x] 工作流编排（状态感知导航）
- [x] 192 个测试全部通过
- [x] 仓库结构验证通过
- [x] opencli 命令契约验证通过

## 后续工作

- 集成真实 opencli 命令（当前为 mock 实现）
- 添加并发执行策略
- 实现增量更新（仅重新采集过期数据）
- 添加用户配置（数据源优先级、阈值）
