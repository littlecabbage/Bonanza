---
name: fetch-stock-quotes
description: 获取股票实时行情数据。支持A股、港股、美股行情查询。输出 stock-quotes.json。
allowed-tools: Bash(opencli:*)
---

# 股票行情获取

通过 opencli 获取股票实时行情数据。

## 工作流程

1. **读取股票列表**：从参数或 investment-entities.json 获取股票代码
2. **批量查询行情**：调用 opencli 获取行情数据
3. **数据标准化**：统一输出格式
4. **输出结构化**：生成符合 schema 的 JSON 输出

## 输入格式

### 直接指定股票代码

```json
{
  "stocks": ["000001", "600519", "0700", "AAPL"]
}
```

### 从实体识别结果读取

```json
{
  "input_file": ".bonanza/runs/<run-id>/investment-entities.json"
}
```

## 执行命令

### A 股行情

```bash
opencli eastmoney quote <code1>,<code2>,... -f json
```

### 港股行情

```bash
opencli eastmoney quote <code1>,<code2>,... -f json
```

### 美股行情

```bash
opencli eastmoney quote <symbol1>,<symbol2>,... -f json
```

## 输出格式

生成 `stock-quotes.json`，符合 `stock-quotes.schema.json`：

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-07T15:00:00+08:00",
  "status": "complete",
  "source": {
    "skill": "fetch-stock-quotes",
    "commands": ["opencli eastmoney quote 000001,600519 -f json"]
  },
  "coverage": {
    "requested": 2,
    "succeeded": 2,
    "failed": 0
  },
  "errors": [],
  "data": {
    "quotes": [
      {
        "name": "平安银行",
        "code": "000001",
        "market": "a",
        "price": 12.50,
        "change": 0.35,
        "change_percent": 2.88,
        "volume": 50000000,
        "amount": 625000000
      }
    ]
  }
}
```

## 错误处理

- 单个股票查询失败：标记 partial，继续其他股票
- 所有股票查询失败：标记 failed
- 网络超时：记录错误，不重试

## 依赖

- opencli CLI 工具
- 东方财富数据接口

## 限制

- 不支持实时订阅，仅支持快照查询
- 港股和美股数据可能有延迟
