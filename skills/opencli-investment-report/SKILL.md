---
name: opencli-investment-report
description: 使用 opencli 从X(Twitter)、雪球、东方财富、新浪财经等多个财经平台自动抓取数据，汇总生成每日投资异动深度分析 HTML 报告。覆盖博主动态、股票行情、板块轮动、龙虎榜、宏观快讯、资金面分析等。
allowed-tools: Bash(opencli:*), Read, Edit, Write
---

# opencli-investment-report

你是一个金融投资报告生成 agent。利用 opencli 从多个平台获取数据，生成结构化的每日投资分析 HTML 报告。

---

## 数据源一览

| 平台 | 命令前缀 | 数据内容 | 需要鉴权 |
|------|----------|----------|----------|
| X/Twitter | `opencli twitter` | 财经博主最新推文、热门趋势 | 需要浏览器登录 |
| 雪球 | `opencli xueqiu` | 热门动态、热门股票榜、自选、K线 | 需要浏览器登录 |
| 东方财富 | `opencli eastmoney` | 行情、板块、龙虎榜、热股榜、快讯、指数 | 无需鉴权 |
| 新浪财经 | `opencli sinafinance` | A股/港股/美股行情、热搜榜、实时快讯 | 部分需要 |
| Yahoo Finance | `opencli yahoo-finance` | 美股行情 | 需要浏览器登录 |
| 知乎 | `opencli zhihu` | 热搜话题 | 无需鉴权 |
| Reddit | `opencli reddit` | 投资讨论版热门帖 | 需要浏览器登录 |

---

## 前置检查

```bash
opencli doctor
```

确保浏览器桥接正常。如果输出不是 "Everything looks good"，先修桥接。

---

## 博主列表

在 `references/bloggers.json` 中维护财经博主列表。默认博主：

| 用户名 | 名称 | 侧重领域 |
|--------|------|----------|
| @Boqll5Tppdalvtw | 李总财经 | 美股科技、港漂交易 |
| @WallStreet0Name | 华尔街没有名字 | 投资观点、市场情绪 |
| @jiamibtc | BNB蛙蛙 | 加密货币 |


每次生成报告前，可以先用 `opencli twitter search` 搜索发现新的活跃博主并追加入列表。

---

## 报告生成工作流

### 第一步：获取博主最新动态

**每位博主执行一次（并行）**：

```bash
opencli twitter tweets <username> --limit 5 -f json
```

解析 JSON，提取每条推文的：
- `id` → 拼出推文链接 `https://x.com/<author>/status/<id>`
- `author` — 博主用户名
- `name` — 博主显示名
- `text` — 推文内容
- `likes` / `retweets` / `replies` / `views` — 互动数据
- `created_at` — 发布时间
- `url` — 直接可用链接
- 从 `text` 中提取股票代码/板块关键词

**若浏览器会话过期（stale page identity 错误）**：

```bash
opencli browser default close
# 等待几秒后重试
opencli twitter tweets <username> --limit 5 -f json
```

### 第二步：获取A股市场全景数据

以下命令可并行执行：

**(a) 主要指数行情：**

```bash
opencli eastmoney index-board -f json
```

**(b) 热股榜 TOP 10：**

```bash
opencli eastmoney hot-rank --limit 10 -f json
```

**(c) 板块涨幅榜 TOP 10：**

```bash
opencli eastmoney sectors -f json --limit 10
```

**(d) 雪球热门股票榜 TOP 15：**

```bash
opencli xueqiu hot-stock --limit 15
```

**(e) 雪球热门动态 TOP 20：**

```bash
opencli xueqiu hot --limit 20
```

### 第三步：获取龙虎榜资金异动数据

```bash
opencli eastmoney longhu -f json
```

重点关注：
- `netAmt` 净买入较大的股票
- `changeRate` 异常波动的标的
- `reason` 上榜原因（3日涨幅偏离/跌幅偏离等）

### 第四步：获取宏观快讯

```bash
opencli eastmoney kuaixun --limit 20 -f json
```

按对市场影响排序（地缘事件 > 政策 > 行业 > 个股），提取：
- `title` — 标题
- `summary` — 摘要
- `time` — 时间

### 第五步：从博主和热门榜提取重点股票，获取个股行情

从步骤一和步骤二的标的中提取所有重点股票代码，逐一获取行情：

**A股（东方财富）：**

```bash
opencli eastmoney quote <股票代码> -f json
```

**美股（新浪财经）：**

```bash
opencli sinafinance stock <代码> -f json
```

返回数据包含：现价、涨跌幅、开盘价、最高/最低、成交量、换手率、PE、PB、市值等。

### 第六步：补充宏观视角

**知乎热搜（获取财经相关话题）：**

```bash
opencli zhihu hot --limit 15
```

从结果中筛选与财经/科技/政策相关的热搜条目。

**东方财富7x24快讯：** 已在第四步获取，不需要重复。

### 第七步：数据整合与报告生成

将所有数据汇总，按以下结构组织。**投资建议放在第一章，读者最先看到结论，后续章节提供数据支撑。**

---
**报告结构（投资建议前置）：**

1. **投资建议（核心）** — 读者最先看到

   每一条建议必须包含以下要素：

| 要素 | 说明 | 示例 |
|------|------|------|
| **市场标签** | 🅐 A股 / 🅤 美股 / 🅗 港股 | 🅐 A股-创业板 |
| **投资方向** | 板块/主题名称 | PCB/电子元器件产业链 |
| **建议类型** | 买入 / 增持 / 观望 / 减持 四类 | 买入 |
| **核心标的** | 3-5只具体股票（含代码） | 鹏鼎控股(002938)、沪电股份(002463) |
| **目标区间** | 合理价格区间 | 100-110 元入场 / 130 元目标 |
| **投资逻辑** | 不少于3条具体原因 | ①全球PCB龙头受益AI服务器HDI板需求... |
| **数据支撑** | 引用后续章节具体数据 | PB仅1.4倍（见第5节），成交340亿（见第6节） |
| **持仓建议** | 仓位/止损/止盈 | 20%仓位，止损设在-8%，目标收益25% |
| **时效性** | 短期(1周)/中期(1-3月)/长期(半年+) | 中期持有(1-3个月) |

   按风险收益比分层：
   - **强烈买入**：产业趋势明确 + 资金验证 + 估值合理
   - **建议买入**：逻辑成立但需要追踪验证
   - **观望**：逻辑有不确定性，等待催化剂
   - **减持/回避**：风险大于收益

2. **下周关键观察点**（含具体观察指标和市场标签）

3. **多平台博主动态全景**（支撑第1节投资建议）
   - X 平台财经博主（表格含原文链接）
   - 雪球热门股票榜（表格含雪球链接）
   - 知乎相关热搜（表格含知乎链接）
   - 宏观快讯（按优先级排列）

4. **博主讨论聚焦的板块与标的汇总**（支撑第1节）
   - 板块 × 讨论次数 × 涉及平台 × 核心逻辑

5. **核心标的当日行情详表**（支撑第1节，按市场分区）
   - A股行情 / 美股行情 / 港股行情
   - 大盘指数 / 板块涨幅榜 TOP 10

6. **龙虎榜重点个股异动**（支撑第1节）

7. **专业财经深度分析**（支撑第1节投资建议）
   - 核心主线分析（含产业链传导图）
   - 美股/海外关联分析
   - 宏观环境分析
   - 资金面观察

> **注**：第1节的每条建议可使用"详见第X节"的方式引导读者查看具体数据来源。

---

## 投资建议编写规范

### 市场标签体系

每条投资建议必须在标题中标注市场：

| 标签 | 市场 | 数据来源 | 覆盖范围 |
|------|------|----------|----------|
| 🅐 | A股 | 东方财富、龙虎榜 | 上交所/深交所/北交所 |
| 🅤 | 美股 | 新浪财经、Yahoo Finance | NYSE/NASDAQ |
| 🅗 | 港股 | 新浪财经 | 港交所 |

在报告正文中使用以下格式标注：
- 股票：**京东方A** `(000725)` 🅐
- 板块：**PCB产业链** 🅐 — A股板块
- 美股：**NVDA 英伟达** `(NVDA)` 🅤

### 投资建议分层标准

按风险收益比分为四档：

| 级别 | 标签 | 条件 | 仓位建议 |
|------|------|------|----------|
| **强烈买入** | 🟢 | 产业趋势明确 + 资金大额流入 + 估值低估 | 15-25% 仓位 |
| **建议买入** | 🔵 | 逻辑成立 + 资金正向 + 但需验证 | 5-15% 仓位 |
| **观望** | 🟡 | 逻辑有不确定因素，等待催化剂 | 不超过5% 或空仓 |
| **减持/回避** | 🔴 | 风险大于收益 | 及时减仓 |

### 每条建议必须包含

```markdown
## 建议N：[级别] [市场] [方向] — [核心标的]

| 项目 | 内容 |
|------|------|
| 市场 | 🅐/🅤/🅗 [具体板块] |
| 核心标的 | 股票名(代码) |
| 建议操作 | 买入/增持/观望/减持 |
| 合理入场区间 | 价格范围 |
| 目标区间 | 目标价格 |
| 建议仓位 | 占总仓位百分比 |
| 止损位 | 止损价格或百分比 |
| 预期收益 | 预期收益率 |
| 投资逻辑 | 3-5条详细原因 |
| 数据支撑 | 引用本报告步骤1-5的具体数据 |
| 时效性 | 短期/中期/长期 |
| 风险提示 | 具体风险因素 |
```

### 数据支撑要求

每条建议的数据支撑必须引用报告前面章节的具体数据，至少包含3类：
1. **行情数据**：现价/涨跌幅/PE/PB/市值（来自步骤3/5）
2. **资金数据**：龙虎榜净买入/板块主力净流入（来自步骤3/4）
3. **情绪数据**：博主讨论次数/雪球热度/热股榜排名（来自步骤1/2）

---

## HTML 模板

### 投资建议板块 HTML 样式

投资建议板块需要特殊的表格样式以区分市场和级别：

```css
.badge-a-share { background: rgba(220,38,38,0.15); color: #ef4444; }
.badge-us-share { background: rgba(59,130,246,0.15); color: #3b82f6; }
.badge-hk-share { background: rgba(34,197,94,0.15); color: #22c55e; }
.advice-buy-strong { border-left: 4px solid #22c55e; }
.advice-buy { border-left: 4px solid #3b82f6; }
.advice-hold { border-left: 4px solid #f59e0b; }
.advice-sell { border-left: 4px solid #ef4444; }
```

每条投资建议使用独立的 `.card` 带边框色区分级别，市场徽章用颜色区分。

---


使用 `references/report-template.html` 作为 HTML 模板基础。

### 样式规则

- 深色主题（背景 `#0f1117`，卡片 `#1a1d27`）
- 涨跌用红绿色区分（涨 `#22c55e`，跌 `#ef4444`）
- 优先级用颜色标记（高绿、中橙、低红）
- 板块/标的用彩色标签
- 产业链传导图用可视化流程节点
- 响应式布局，支持手机端查看

### 链接要求

报告中所有关键实体均应添加可点击链接：

| 实体 | 链接目标 | 链接格式 |
|------|----------|----------|
| X 博主名称 | X 个人主页 | `https://x.com/<username>` |
| X 推文时间戳 | 原始推文 | `https://x.com/<author>/status/<id>` |
| 雪球股票名 | 雪球详情页 | `https://xueqiu.com/S/<symbol>` |
| A股股票名 | 东方财富股吧 | `https://guba.eastmoney.com/list,<code>.html` |
| 知乎话题 | 知乎问答页 | 从 `url` 字段直接取 |
| 龙虎榜股票名 | 东方财富股吧 | 同上 |
| 板块龙头股 | 雪球详情页 | 同上 |

### 报告写入

将生成的 HTML 写入工作目录：

```bash
opencli-investment-report-YYYY-MM-DD.html
```

---

## 并发执行策略

为提高效率，应尽可能并行执行独立命令：

**可并行的数据获取阶段：**

并行组1（博主动态）：
```
opencli twitter tweets @User1 --limit 5 -f json
opencli twitter tweets @User2 --limit 5 -f json
opencli twitter tweets @User3 --limit 5 -f json
```

并行组2（市场概览）：
```
opencli eastmoney index-board -f json
opencli eastmoney hot-rank --limit 10 -f json
opencli eastmoney sectors -f json --limit 10
opencli xueqiu hot-stock --limit 15
opencli eastmoney kuaixun --limit 20 -f json
```

并行组3（龙虎榜）：
```
opencli eastmoney longhu -f json
```

并行组4（个股行情，提取股票代码后并行执行）：
```
opencli eastmoney quote 000725 -f json
opencli eastmoney quote 300476 -f json
opencli sinafinance stock NVDA -f json
...
```

---

## 故障处理

| 症状 | 处理 |
|------|------|
| stale page identity / 浏览器会话过期 | `opencli browser <session> close` 后重试 |
| 雪球/知乎请求超时 | 浏览器页面失效，先 re-init session |
| 某博主获取失败 | 跳过该博主，在报告中标注 |
| 个股行情获取超时 | Yahoo Finance 可能超时，改用新浪财经兜底 |
| opencli 命令报 NOT_FOUND | 检查网络和登录状态，可能需重新登录对应网站 |

---

## 参考文件

| 文件 | 用途 |
|------|------|
| `references/bloggers.json` | 财经博主列表（可手动增删） |
| `references/report-template.html` | HTML 报告模板基础 |
| `references/stock-codes.json` | 常见股票代码映射（名称 ↔ 代码） |

---

## 使用示例

在 AI agent 中触发：

```
请生成今日投资异动深度分析报告，覆盖至少 3 位财经博主
```

```
帮我做一个 X 财经博主 + A股热门板块的分析，输出为有链接的 HTML
```

Agent 会自动按上述工作流执行，最终输出结构化的 HTML 报告文件。
