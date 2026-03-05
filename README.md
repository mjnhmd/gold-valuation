# 黄金优惠监控系统

自动抓取京东/淘宝平台周大福等黄金饰品优惠信息，计算克价并展示的 Web 系统。

## 🚀 快速开始

### 本地开发

```bash
# 1. 设置环境
chmod +x scripts/setup.sh
./scripts/setup.sh

# 2. 启动后端 (终端1)
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# 3. 启动前端 (终端2)
cd frontend
npm run dev

# 4. 访问
open http://localhost:3000
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
GoldValuation/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/            # API 路由和数据模型
│   │   ├── models/         # SQLAlchemy 数据库模型
│   │   ├── scrapers/       # 数据抓取器（京东/淘宝）
│   │   ├── services/       # 业务逻辑（数据清洗）
│   │   ├── main.py         # FastAPI 入口
│   │   └── scheduler.py    # APScheduler 定时任务
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Vue 3 前端
│   ├── src/
│   │   ├── components/     # Vue 组件
│   │   ├── composables/    # API 调用
│   │   └── App.vue         # 主应用
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🔧 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+, FastAPI, SQLAlchemy 2.0, APScheduler |
| 前端 | Vue 3 (Composition API), Tailwind CSS, Vite |
| 数据库 | SQLite (可无缝切换至 PostgreSQL) |
| 部署 | Docker, Docker Compose, Nginx |

## 📡 API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/products` | GET | 获取商品列表，支持 `platform`, `sort_by`, `limit` 参数 |
| `/api/stats` | GET | 获取统计信息（最低克价、商品数等） |
| `/api/sync` | POST | 手动触发数据同步 |
| `/api/products/{item_id}` | GET | 获取单个商品详情 |

### 示例

```bash
# 获取克价最低的 20 个商品
curl "http://localhost:8000/api/products?sort_by=price_per_gram&limit=20"

# 只看京东商品
curl "http://localhost:8000/api/products?platform=JD"

# 获取统计信息
curl "http://localhost:8000/api/stats"
```

## 🕐 定时任务

系统自动在以下时间同步数据：
- 08:00 - 早间同步
- 12:00 - 午间同步
- 20:00 - 晚间同步

## 🔑 对接真实 API

V1 阶段使用 Mock 数据，对接真实数据需要：

### 京东联盟

1. 注册 [京东联盟](https://union.jd.com/)
2. 申请 API 权限，获取 `api_key` 和 `api_secret`
3. 修改 `backend/app/scrapers/base.py` 中的 `JDScraper`

### 阿里妈妈（淘宝）

1. 注册 [阿里妈妈](https://pub.alimama.com/)
2. 申请 API 权限，获取 `app_key` 和 `app_secret`
3. 修改 `backend/app/scrapers/base.py` 中的 `TaobaoScraper`

## 📝 克重提取逻辑

系统通过正则表达式从商品标题提取克重：

```python
# 支持格式
"约3.5g"     → 3.5 克
"3.5克"      → 3.5 克
"约 2.15 g"  → 2.15 克
"重量：5.8克" → 5.8 克
```

过滤规则：
- ❌ 一口价商品（标题含"一口价"、"定价"）
- ❌ 非纯金商品（18K金、白金、铂金等）
- ❌ 克价 > 1000 元/克的商品
- ❌ 克重不在 0.3g ~ 100g 范围内

## 📄 License

MIT
