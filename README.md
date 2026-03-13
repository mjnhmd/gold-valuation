# 黄金优惠监控系统

自动抓取京东/淘宝平台周大福等黄金饰品优惠信息，通过好单库 API 获取数据，计算克价并展示的 Web 系统。

## 🚀 快速开始

### 本地开发

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 启动后端
uvicorn app.main:app --reload --port 8000

# 3. 启动前端 (终端2)
cd frontend
npm install
npm run dev

# 4. 访问
open http://localhost:5173
```

### Docker 部署

```bash
# 一键启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 📁 项目结构

```
gold-valuation/
├── local_server.py           # 独立后端服务入口（整合版）
├── haodanku_search.py        # 好单库 API 调试脚本
├── backend/                  # 模块化后端
│   ├── app/
│   │   ├── api/              # API 路由和数据模型
│   │   ├── models/           # SQLAlchemy 数据库模型
│   │   ├── scrapers/         # 数据抓取器
│   │   ├── services/         # 业务逻辑（数据清洗）
│   │   ├── main.py           # FastAPI 入口
│   │   └── scheduler.py      # APScheduler 定时任务
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── components/       # Vue 组件
│   │   ├── composables/      # API 调用
│   │   └── App.vue           # 主应用
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── openspec/
└── README.md
```

## 🔧 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+, FastAPI, SQLAlchemy 2.0, APScheduler |
| 前端 | Vue 3 (Composition API), Tailwind CSS, Vite |
| 数据源 | 好单库 API (京东/淘宝商品搜索) |
| 数据库 | SQLite (可无缝切换至 PostgreSQL) |
| 部署 | Docker, Docker Compose, Nginx |

## 📡 API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/products` | GET | 获取商品列表，支持 platform, sort_by, limit 等参数 |
| `/api/stats` | GET | 获取统计信息（最低克价、商品数、折扣信息等） |
| `/api/sync` | POST | 手动触发数据同步 |
| `/api/products/{item_id}` | GET | 获取单个商品详情 |

### 示例

```bash
# 获取按折扣率排序的商品
curl "http://localhost:8000/api/products?sort_by=discount_rate&sort_order=desc"

# 只看京东商品
curl "http://localhost:8000/api/products?platform=JD"

# 获取统计信息
curl "http://localhost:8000/api/stats"

# 手动触发同步
curl -X POST "http://localhost:8000/api/sync"
```

## 🕐 定时任务

系统自动在以下时间同步数据：
- 08:00 - 早间同步
- 12:00 - 午间同步
- 20:00 - 晚间同步

## 🔑 好单库 API

项目使用 [好单库](https://www.haodanku.com/) API 获取数据：

### 淘宝超级搜索
- 端点：`https://v2.api.haodanku.com/supersearch`
- 用途：搜索淘宝/天猫商品

### 京东商品搜索
- 端点：`https://v3.api.haodanku.com/jd_goods_search`
- 用途：搜索京东商品

配置位置：`local_server.py` 和 `backend/app/scrapers/base.py`

## 📝 数据处理逻辑

### 克重提取
从商品标题中通过正则表达式提取克重：

```python
# 支持格式
"约3.5g"     → 3.5 克
"3.5克"      → 3.5 克
"约 2.15 g"  → 2.15 克
"重量：5.8克" → 5.8 克
```

### 过滤规则
- ❌ 一口价商品（标题含"一口价"、"定价"）
- ❌ 非纯金商品（18K金、白金、铂金等）
- ❌ 克价 > 1000 元/克的商品
- ❌ 克重不在 0.1g ~ 500g 范围内

### 数据维度
系统记录以下优惠维度：
- **price_per_gram**: 克价（元/克）
- **discount_rate**: 折扣率
- **coupon_amount**: 优惠券金额
- **discount_amount**: 降价金额
- **monthly_sales**: 月销量
- **is_price_lowest**: 是否为近期最低价

## 📄 License

MIT
