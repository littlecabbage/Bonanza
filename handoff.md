# Bonanza 重构修复开发交接

## 1. 任务目标

接手 `/Users/sync/playground/Bonanza`，修复当前模块化重构中的阻断问题，并继续完成尚未实现的 Skill，最终形成可测试、可运行、可提交 Pull Request 的版本。

本轮开发必须采用 TDD：

```text
复现缺陷
  ↓
编写只针对该行为的失败测试
  ↓
运行测试并确认以预期原因失败
  ↓
实现最小修复
  ↓
运行目标测试和全量回归
  ↓
检查 diff 并创建单一职责提交
```

禁止先写实现、再补一个永远通过的测试。

## 2. Git 与仓库状态

### 本地目录

```text
/Users/sync/playground/Bonanza
```

### 远程仓库

```text
origin   https://github.com/littlecabbage/Bonanza.git
upstream https://github.com/zhengronggui666/Bonanza.git
```

`upstream` 的 push URL 已禁用。只能向 `origin` 推送。

### 当前分支

```text
codex/modular-investment-skills
```

### 当前已提交进度

```text
0c3aea9 feat: add 5 independent collection skills
8af99b8 feat: add guide-investment-workflow skill
90c8e68 feat: define investment workflow data contracts
3ec2ea4 test: add repository validation baseline
a84dcd1 upstream/main
```

### 当前未提交改动

```text
M  README.md
D  skills/opencli-investment-report/SKILL.md
D  skills/opencli-investment-report/references/bloggers.json
D  skills/opencli-investment-report/references/report-template.html
D  skills/opencli-investment-report/references/stock-codes.json
?? skills/extract-investment-entities/
?? skills/fetch-stock-quotes/
?? handoff.md
```

这些改动来自上一轮开发。不要执行 `git reset --hard`、`git checkout --` 或删除未跟踪目录。应在现有工作树上修复。

开始前运行：

```bash
git status --short --branch
git remote -v
git log --oneline --decorate -10
```

## 3. 产品架构

目标交互模型：

```text
用户表达目标或确认下一步
          ↓
Agent 判断任务类型、检查状态、选择一个 Skill
          ↓
单点 Skill 执行一个任务并生成结构化产物
          ↓
Agent 校验产物、展示摘要、推荐最多三个下一步
```

核心约束：

1. Skill 之间不得直接调用。
2. Agent 默认每轮只执行一个任务 Skill。
3. 单点查询不强制进入完整报告流程。
4. 各 Skill 通过版本化 JSON 文件交接。
5. 外部来源失败时允许 `partial`，但必须记录错误和覆盖率。
6. 默认输出市场研究，不默认给出个性化仓位或确定性收益承诺。
7. HTML 必须由确定性脚本渲染，不能由 Agent 自由拼接。

## 4. 当前实现范围

### 已存在

```text
guide-investment-workflow
collect-blogger-updates
collect-market-overview
collect-market-sentiment
collect-capital-movements
collect-market-news
extract-investment-entities       # 未提交，存在缺陷
fetch-stock-quotes                # 未提交，存在缺陷
```

### 尚未创建

```text
analyze-investment-signals
build-investment-scenarios
render-investment-report
```

### 旧 Skill

旧 `opencli-investment-report` 当前在工作树中被删除，但新流程尚未达到功能等价。不要直接提交这组删除。

在新分析、情景、渲染和端到端流程完成前，采用以下两种方式之一：

1. 推荐：暂时恢复旧 Skill，最终再将其改成兼容导航入口。
2. 如果不恢复，必须先完成新链路并使全部测试通过，再提交删除。

不得留下“旧入口已删除、新报告又无法生成”的中间状态。

## 5. 当前失败基线

### 单元测试

命令：

```bash
python3 -m unittest discover -s tests -v
```

当前结果：

```text
Ran 24 tests
FAILED (errors=3)
```

三个错误都来自测试仍硬编码已删除的旧模板：

```text
skills/opencli-investment-report/SKILL.md
skills/opencli-investment-report/references/report-template.html
```

涉及位置：

```text
tests/test_repository.py:131-149
tests/test_repository.py:151-213
```

### 仓库验证器

命令：

```bash
python3 scripts/validate_repository.py
```

当前失败：

```text
HTML template not found
```

原因：

```text
scripts/validate_repository.py:95-107
```

仍硬编码旧模板路径。

### Diff 检查

命令：

```bash
git diff --check
```

当前失败：

```text
README.md:84: new blank line at EOF.
```

## 6. 已确认的功能缺陷

### P0：采集 Skill 使用不存在的 OpenCLI 命令

实际已通过以下命令复核：

```bash
opencli eastmoney --help
opencli twitter --help
opencli xueqiu --help
```

当前文档中的错误命令：

| Skill | 错误命令 | 应采用的真实能力 |
|---|---|---|
| `collect-blogger-updates` | `twitter blogger-tweets` | `twitter tweets` |
| `collect-market-overview` | `eastmoney index` | `eastmoney index-board` |
| `collect-market-overview` | `eastmoney hot-stocks` | `eastmoney hot-rank` |
| `collect-market-sentiment` | `xueqiu hot-topics` | `xueqiu hot` / `hot-stock` |
| `collect-market-sentiment` | `eastmoney discussions` | 当前无此命令，删除或换成真实来源 |
| `collect-capital-movements` | `eastmoney block-trades` | 当前无此命令，第一版删除 |
| `collect-capital-movements` | `eastmoney fund-flow` | `eastmoney money-flow` |
| `collect-market-news` | `eastmoney policy` | 当前无此命令 |
| `collect-market-news` | `eastmoney industry` | 当前无此命令 |

东方财富当前可用能力包括：

```text
index-board
hot-rank
sectors
longhu
kuaixun
money-flow
northbound
quote
rank
```

雪球当前可用能力包括：

```text
hot
hot-stock
comments
stock
search
feed
kline
```

第一版应缩小范围到真实存在的命令，不要在文档中虚构能力。

### P0：采集 Skill 没有确定性输出实现

五个采集 Skill 目前主要是操作说明，没有脚本将 OpenCLI 原始 JSON 规范化为对应 Schema。

单纯写“输出遵循 schema”不能保证产物符合契约。

每个采集 Skill 至少需要以下一种实现：

- 独立采集/规范化脚本。
- 共享的小型执行库和 Skill 专属入口。

优先保持实现简单，不引入工作流框架。

### P0：行情查询使用不存在的命令

文件：

```text
skills/fetch-stock-quotes/scripts/fetch_quotes.py
```

错误：

```text
opencli eastmoney hk-quote
opencli eastmoney us-quote
```

实测查询 `TSLA` 会得到：

```text
error: unknown command 'us-quote'
Did you mean quote?
```

`opencli eastmoney quote <symbols> -f json` 已支持 A 股、港股和美股，应统一使用该命令。

### P1：实体识别输出不符合 Schema

文件：

```text
skills/extract-investment-entities/scripts/extract_entities.py
schemas/investment-entities.schema.json
```

脚本输出与 Schema 的冲突：

| 脚本输出 | Schema 要求 |
|---|---|
| `code` | `symbol` |
| `confidence: 0.9` | `confidence: high/medium/low` |
| `type: industry` | `type: sector` |
| 无 `sources` | 支持并应保留来源 |
| 无时区且包含微秒 | `YYYY-MM-DDTHH:MM:SS+HH:MM` |

此外，当前脚本把任意 JSON 中所有字符串拼接后匹配，会把 URL、作者名、错误信息等非正文内容作为实体来源。至少应限定常见文本字段，或为递归提取建立清晰规则。

### P1：行情输出也可能不符合 Schema

文件：

```text
skills/fetch-stock-quotes/scripts/fetch_quotes.py
schemas/stock-quotes.schema.json
```

问题：

- `generated_at` 不带时区。
- 直接透传 OpenCLI 字段，没有做 `changePercent` 到 `change_percent` 等规范化。
- 没有测试 OpenCLI 输出是数组、对象还是 envelope。
- 空输入被标记为 `complete`，没有区分“用户确实请求空列表”和“输入解析失败”。
- 未识别代码会静默丢弃。
- `coverage.failed = requested - len(quotes)` 在重复结果或未知输出结构下可能错误。

### P1：导航状态判断错误

文件：

```text
skills/guide-investment-workflow/scripts/inspect_run.py
schemas/workflow-state.schema.json
```

缺陷一：

```python
if step.get("status") == "completed":
```

Schema 使用的是：

```text
complete
```

缺陷二：只要产物文件存在，就被加入 `completed_steps`，不检查：

- `status`
- JSON 是否有效
- Schema 版本
- 是否过期

缺陷三：虽然计算了 `is_fresh`，推荐逻辑没有使用它。一个 2020 年生成、`status=failed` 的文件仍会阻止重新采集建议。

缺陷四：读取损坏的 `workflow-state.json` 没有异常处理，会直接终止脚本。

## 7. TDD 总体策略

### 测试层级

按以下四层建立测试：

1. **单元测试**：纯函数、字段映射、状态判断。
2. **契约测试**：脚本真实输出是否符合 Schema。
3. **命令适配测试**：mock `subprocess.run`，断言实际调用的 OpenCLI 命令。
4. **场景测试**：Agent 工作流状态和下一步推荐。

真实网络或浏览器测试只作为 smoke test，不应成为离线测试的前提。

### 测试命名

测试名称必须描述行为，例如：

```text
test_failed_product_is_not_marked_complete
test_stale_product_recommends_recollection
test_us_quote_uses_eastmoney_quote
test_entity_output_matches_schema_contract
```

避免：

```text
test_script_works
test_data
test_new_feature
```

### Mock 边界

只 mock 外部边界：

- `subprocess.run`
- 当前时间
- 文件系统中的输入 fixture

不要 mock 被测脚本的核心规范化函数。

### 红灯要求

每个缺陷修复前：

1. 增加测试。
2. 只运行该测试。
3. 确认测试因目标缺陷失败，而不是 fixture 写错或 import 失败。
4. 再修改实现。

## 8. 修复实施顺序

以下顺序是依赖顺序。不要先做 HTML 或分析 Skill。

### Task 0：冻结并恢复可工作的测试基线

目标：修复“测试自身因文件缺失报错”，但不能通过跳过测试掩盖未完成能力。

先新增或调整测试：

1. 如果旧模板仍存在，验证旧模板已知缺陷。
2. 如果旧模板已迁移，验证新路径。
3. 如果渲染 Skill 尚未创建，明确断言 `render-investment-report` 缺失，而不是抛 `FileNotFoundError`。

需要修改：

```text
tests/test_repository.py
scripts/validate_repository.py
README.md
```

建议把 HTML 验证改成目标路径：

```text
skills/render-investment-report/assets/report-template.html
```

在 Task 8 完成前，仓库测试可以保留一个清晰的失败测试，但日常主分支提交不应处于异常错误状态。推荐先恢复旧模板作为兼容资产，再在 Task 8 迁移。

验收：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repository.py
git diff --check
```

建议提交：

```text
test: repair refactor validation baseline
```

### Task 1：为真实 OpenCLI 命令建立契约测试

先编写测试，扫描所有 `SKILL.md` 和脚本中的 `opencli` 命令，确保站点子命令属于允许集合。

最低允许集合：

```python
EASTMONEY = {
    "index-board", "hot-rank", "sectors", "longhu",
    "kuaixun", "money-flow", "northbound", "quote", "rank"
}
TWITTER = {"tweets", "search", "trending"}
XUEQIU = {"hot", "hot-stock", "comments", "stock", "search", "feed", "kline"}
```

不要把完整 OpenCLI 能力永久硬编码成权威 API；测试集合只覆盖本仓库实际使用的命令。

然后修正五个采集 Skill 文档和行情脚本。

验收：

```bash
python3 -m unittest tests.test_repository -v
rg -n "blogger-tweets|hot-stocks|hot-topics|block-trades|fund-flow|hk-quote|us-quote" skills
```

预期 `rg` 无结果。

建议提交：

```text
fix: align investment skills with opencli commands
```

### Task 2：修复导航状态机

先新增：

```text
tests/test_inspect_run.py
```

必须覆盖：

1. `workflow-state.json` 中 `complete` 被识别为完成。
2. `partial` 不被当作完全完成，但产物仍可供下游使用。
3. `failed` 产物不会被识别为完成。
4. 损坏 JSON 不会被识别为完成，并返回可读错误。
5. 过期产物会推荐重新采集。
6. 新鲜产物不会重复推荐。
7. 最多返回三个下一步。
8. 缺失运行目录返回结构化错误。
9. 损坏的 `workflow-state.json` 不导致 traceback。

建议把状态分为：

```text
completed_steps
usable_products
stale_products
failed_products
invalid_products
```

不要只用“文件存在”推断完成。

验收：

```bash
python3 -m unittest tests.test_inspect_run -v
python3 -m unittest discover -s tests -v
```

建议提交：

```text
fix: make workflow recommendations status aware
```

### Task 3：修复实体识别契约

先新增：

```text
tests/test_extract_entities.py
```

必须覆盖：

1. 中文股票名映射到标准 `symbol`。
2. 美股代码大小写匹配。
3. 港股代码匹配。
4. 行业输出类型为 `sector`。
5. 概念输出类型为 `concept`。
6. `confidence` 使用枚举字符串。
7. `mentions` 统计真实出现次数，而不是固定为 1。
8. 相同实体去重但保留来源。
9. 未识别文本产生合法的 `partial` 或明确设计的空成功结果。
10. 输出时间带时区且无微秒。
11. 脚本输出满足 `investment-entities.schema.json`。
12. 损坏输入 JSON 产生结构化 `failed` 结果，而不是 traceback。

建议为脚本拆出纯函数：

```python
normalize_generated_at()
extract_text_sources()
extract_entities()
build_result()
```

验收：

```bash
python3 -m unittest tests.test_extract_entities -v
python3 skills/extract-investment-entities/scripts/extract_entities.py \
  "英伟达和半导体值得关注" /tmp/investment-entities.json
```

确认输出字段与 Schema 完全一致。

建议提交：

```text
fix: conform entity extraction to schema
```

### Task 4：修复行情查询契约

先新增：

```text
tests/test_fetch_quotes.py
```

使用 mock 的 `subprocess.run`，必须覆盖：

1. A 股、港股和美股都调用 `opencli eastmoney quote`。
2. 多代码使用一个批量命令。
3. 实体文件只读取 `type=stock` 的 `symbol`。
4. 用户输入去重。
5. 未识别代码形成错误或失败覆盖，不静默丢弃。
6. OpenCLI 数组输出能被解析。
7. OpenCLI envelope 输出能被解析。
8. camelCase 字段被规范化为 Schema 字段。
9. 单个结果缺失时状态为 `partial`。
10. 所有请求失败时状态为 `failed`。
11. 空输入和输入解析错误有明确状态。
12. 输出时间带时区且无微秒。
13. 输出满足 `stock-quotes.schema.json`。

不要按市场拆成三个不存在的命令。市场信息从返回数据或参考映射中规范化。

验收：

```bash
python3 -m unittest tests.test_fetch_quotes -v
opencli eastmoney quote 000725,NVDA -f json
```

真实 smoke test 的输出不应提交到仓库。

建议提交：

```text
fix: normalize multi-market quote collection
```

### Task 5：为五个采集 Skill 添加确定性脚本

一次只实现一个 Skill，并为每个 Skill 独立提交。

建议文件：

```text
skills/collect-blogger-updates/scripts/collect.py
skills/collect-market-overview/scripts/collect.py
skills/collect-market-sentiment/scripts/collect.py
skills/collect-capital-movements/scripts/collect.py
skills/collect-market-news/scripts/collect.py
```

每个脚本的测试必须覆盖：

- 正确 OpenCLI 命令。
- 原始字段规范化。
- `source.commands` 记录真实命令。
- 单来源失败时 `partial`。
- 全部失败时 `failed`。
- 空但请求成功的响应如何定性。
- `coverage` 数值一致。
- 输出满足对应 Schema。
- 输出目录自动创建。

第一版真实数据源：

| Skill | 命令 |
|---|---|
| 博主动态 | `twitter tweets <username> --limit N -f json` |
| 市场概览 | `eastmoney index-board`、`hot-rank`、`sectors` |
| 市场情绪 | `xueqiu hot`、`hot-stock` |
| 资金异动 | `eastmoney longhu`、`money-flow`、可选 `northbound` |
| 市场新闻 | `eastmoney kuaixun` |

不要为了满足旧文档而调用不存在的政策、行业或大宗交易命令。

建议提交：

```text
feat: add deterministic blogger collection
feat: add deterministic market overview collection
feat: add deterministic market sentiment collection
feat: add deterministic capital movement collection
feat: add deterministic market news collection
```

### Task 6：实现综合信号分析 Skill

创建：

```text
skills/analyze-investment-signals/
├── SKILL.md
├── agents/openai.yaml
├── references/methodology.md
└── scripts/analyze_signals.py
```

先新增：

```text
tests/test_analyze_signals.py
```

必须覆盖：

1. 只有市场概览也能产生低覆盖分析。
2. 概览加资金提高覆盖率。
3. 完整输入生成行情、资金、情绪、事件四维证据。
4. 相互矛盾的数据同时进入支持证据和反对证据。
5. 缺失数据被列出。
6. 每个结论能追溯到源文件或来源 URL。
7. 不输出“强烈买入”、个性化仓位或收益承诺。
8. 输出符合 `investment-signals.schema.json`。

建议提交：

```text
feat: add evidence-based signal analysis
```

### Task 7：实现可选情景推演 Skill

创建：

```text
skills/build-investment-scenarios/
├── SKILL.md
├── agents/openai.yaml
└── scripts/build_scenarios.py
```

先新增：

```text
tests/test_build_scenarios.py
```

必须覆盖：

1. 生成看多、中性和看空三个情景。
2. 每个情景包含触发条件、观察指标、失效条件和风险。
3. 缺少时间范围时返回结构化错误。
4. 缺少最新行情时不生成具体价格区间。
5. 未提供用户风险约束时不生成个性化仓位。
6. 输出符合 `investment-scenarios.schema.json`。

建议提交：

```text
feat: add optional investment scenarios
```

### Task 8：实现确定性 HTML 渲染

创建：

```text
skills/render-investment-report/
├── SKILL.md
├── agents/openai.yaml
├── assets/report-template.html
└── scripts/render_report.py
```

先新增：

```text
tests/test_render_report.py
```

必须覆盖：

1. 模板中没有重复 `<h2>`。
2. 所有外部字符串执行 HTML 转义。
3. 恶意文本不能注入 `<script>`。
4. 空数据章节不渲染空卡片。
5. 没有情景数据时首章为“市场观察摘要”。
6. 有情景数据时显示条件化情景，不显示收益承诺。
7. 来源链接存在。
8. 生成时间和覆盖率存在。
9. 最终 HTML 不含 `{{...}}`。
10. 输出文件可离线打开。

完成后更新：

```text
tests/test_repository.py
scripts/validate_repository.py
```

使其检查新模板路径。

建议提交：

```text
feat: add deterministic report renderer
```

### Task 9：端到端场景测试

创建：

```text
tests/test_workflow_scenarios.py
tests/fixtures/scenarios/
```

覆盖：

1. 只查询市场概览。
2. 只采集指定博主。
3. 直接查询股票行情。
4. 从零开始逐步生成完整报告。
5. 跳过博主数据后继续分析。
6. 登录型来源失败但以 `partial` 继续。
7. 从已有运行目录恢复。
8. 仅把已有 JSON 渲染为 HTML。
9. Agent 每轮只推荐和执行一个任务 Skill。
10. 推荐项不超过三个。

建议提交：

```text
test: add modular workflow scenarios
```

### Task 10：迁移旧入口并收口文档

只有 Task 0-9 全部通过后执行。

最终选择：

- 将 `opencli-investment-report` 改为兼容导航 Skill；或
- 如果上游明确接受 breaking change，再删除旧入口。

推荐保留一个精简兼容入口，用于旧触发词，并引导 Agent 调用 `guide-investment-workflow`。

更新：

```text
README.md
.gitignore
scripts/validate_repository.py
```

README 不得将未实现能力标成已完成。

建议提交：

```text
refactor: finalize modular investment workflow
```

## 9. Schema 验证策略

仓库已有 `schemas/*.schema.json`，但当前测试主要检查 fixture 顶层字段，没有验证脚本真实输出。

必须增加“执行脚本后验证产物”的契约测试。

如果不引入第三方 `jsonschema`，至少实现轻量验证器，覆盖：

- required 字段
- const
- enum
- type
- 日期格式
- 数组 item 必需字段

不要宣称“符合 JSON Schema”，但只检查七个顶层字段。

如果决定引入 `jsonschema`：

1. 先检查仓库是否允许新增依赖。
2. 明确依赖安装方式。
3. 不让测试依赖未声明的全局包。

## 10. 时间格式

所有业务产物统一使用带时区、无微秒的 ISO 8601：

```python
datetime.now().astimezone().replace(microsecond=0).isoformat()
```

示例：

```text
2026-06-07T20:30:00+08:00
```

不要使用：

```python
datetime.now().isoformat()
```

它可能没有时区并包含微秒。

## 11. 错误与覆盖率语义

### `complete`

- 所有必要请求成功。
- 可以存在合法空数据，但必须由来源成功响应证明。

### `partial`

- 至少有一个可用结果。
- 同时存在失败请求或缺失数据。
- `errors` 非空，或 `coverage.succeeded < coverage.requested`。

### `failed`

- 没有可供下游使用的数据。
- `errors` 必须说明原因。

覆盖率要求：

```text
requested = succeeded + failed
```

如果一个请求返回多个记录，`succeeded` 统计成功请求数，不统计记录行数。所有 Skill 必须采用一致口径。

## 12. 测试与提交纪律

每个任务遵循：

```bash
# 1. 写测试后，只运行目标测试
python3 -m unittest tests.test_<module> -v

# 2. 确认失败原因正确

# 3. 实现最小修复

# 4. 目标测试
python3 -m unittest tests.test_<module> -v

# 5. 全量回归
python3 -m unittest discover -s tests -v

# 6. 仓库验证
python3 scripts/validate_repository.py

# 7. Diff 检查
git diff --check
git status --short
```

提交前检查：

```bash
git diff --cached --stat
git diff --cached
```

不要将真实 `.bonanza/runs/`、浏览器状态、登录凭据或 smoke test 输出提交到仓库。

## 13. Skill 结构验证

每个 Skill 完成后运行：

```bash
python3 /Users/sync/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  skills/<skill-name>
```

注意：`quick_validate.py` 只证明目录和 frontmatter 基本合法，不证明：

- OpenCLI 命令存在。
- 脚本能运行。
- 输出符合 Schema。
- Agent 推荐逻辑正确。

不能把 quick validation 作为唯一验收。

## 14. 最终验收

在推送和创建 PR 前必须全部通过：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_repository.py
git diff --check
```

逐个 Skill：

```bash
for d in skills/*; do
  if [ -f "$d/SKILL.md" ]; then
    python3 /Users/sync/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$d"
  fi
done
```

最低真实 smoke test：

```bash
opencli eastmoney index-board -f json
opencli eastmoney hot-rank --limit 3 -f json
opencli eastmoney quote 000725,NVDA -f json
```

登录型来源仅在已有有效会话时测试；未登录必须形成结构化失败，而不是 traceback。

完成定义：

- 所有目标 Skill 已存在并通过结构、行为和契约测试。
- 五个采集 Skill 使用真实 OpenCLI 命令。
- 所有业务脚本输出符合对应 Schema。
- 导航正确区分 complete、partial、failed、stale 和 invalid。
- Agent 默认每轮只执行一个 Skill。
- 分析输出包含证据、反证、覆盖率和风险。
- 情景推演不会产生无约束的个性化建议。
- HTML 渲染安全、确定、无残留占位符。
- 旧入口迁移不产生功能真空。
- README 与实际实现一致。
- 工作树中没有意外生成物。

## 15. PR 流程

全部完成后：

```bash
git push -u origin codex/modular-investment-skills
```

创建 Draft PR：

```text
base: zhengronggui666/Bonanza:main
head: littlecabbage/Bonanza:codex/modular-investment-skills
```

PR 描述至少包含：

- 为什么从单体 Skill 拆分。
- 人、Agent、Skill 的职责边界。
- 新增的 Skill 列表。
- JSON 契约和运行目录。
- 旧入口迁移策略。
- 自动测试结果。
- OpenCLI smoke test 结果。
- 已知限制和后续工作。

## 16. 禁止事项

不得：

- 重置或覆盖当前未提交改动。
- 先删旧入口再留下不可运行的新链路。
- 继续使用已确认不存在的 OpenCLI 命令。
- 通过跳过测试或删除断言获得绿色测试。
- 只测试 fixture，不测试脚本真实输出。
- 把“文件存在”等同于“步骤完成”。
- 吞掉外部命令错误。
- 在缺少数据时伪造默认市场结论。
- 默认输出个性化仓位、强烈买入或收益承诺。
- 引入数据库、服务端或复杂工作流框架。
- 推送到 `upstream`。

## 17. 下一个 Agent 的第一步

直接执行：

```text
阅读 handoff.md 后，从 Task 0 开始。
先为当前测试/验证器的旧路径问题编写或调整失败测试，
恢复可工作的测试基线；不要直接实现剩余三个 Skill，
也不要提交当前旧 Skill 删除。
```

当前状态不是“重构完成后的少量修补”，而是“模块化基础已建立，但命令适配、契约执行、导航状态机和后半段流程仍需按 TDD 完成”。
