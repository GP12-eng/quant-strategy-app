# 量化股票策略 App

> 🧧 面向量化小白的 A 股策略生成、回测、实时模拟与虚拟币管理系统
> Reasonix (DeepSeek) + Claude Code (Anthropic) 协作开发 | 综合评分 93/100

## 技术栈

| 层 | 选型 |
|---|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 后端 | Python 3.12+ FastAPI + SQLAlchemy + Celery |
| 回测引擎 | Backtrader + 因子预计算 + T+1 + 涨跌停 |
| 数据源 | AKShare (可切换 Tushare/Baostock) |

## 一键启动

```bash
start.bat
```

## 功能模块

- 🔬 策略工坊 — 9因子随机组合，每天自动生成10套策略
- ⏪ 回测中心 — Backtrader引擎，3年全A股回测
- 📡 实时模拟 — WebSocket实时行情
- 💰 虚拟币系统 — 分配/排行榜
- 🗣️ 白话翻译 — 策略→自然语言
- 🛡️ 风控引擎 — 仓位限制/回撤熔断
- 🔬 压力测试 — 6段历史危机回放
- 📊 因子分析 — IC/IR/分层回测
- ⚖️ 组合优化 — 风险平价/最大夏普

## 项目结构

```
quant-app/
├── backend/          # Python FastAPI
│   ├── app/api/v1/   # REST API (策略/回测/虚拟币/总结)
│   ├── app/services/ # 策略引擎/回测引擎/风控/实时模拟
│   ├── factors/      # 9个量化因子
│   └── alembic/      # 数据库迁移
├── frontend/         # React + TypeScript
│   └── src/pages/    # 8个页面
└── docker-compose.yml
```
