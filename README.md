# 电商商品价格监控系统

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Scrapy 2.11](https://img.shields.io/badge/scrapy-2.11-green.svg)](https://scrapy.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 项目简介

电商多平台商品价格监控与趋势分析系统。支持京东、淘宝、苏宁等主流电商平台的商品数据采集，提供分布式爬虫架构、智能反爬策略、数据清洗与价格趋势分析功能。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      调度层 (Scheduler)                       │
│              Redis 分布式任务队列 + schedule 定时任务          │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                    爬虫层 (Spiders)                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ 京东爬虫    │  │ 淘宝爬虫    │  │ 苏宁爬虫    │             │
│  │CrawlSpider │  │ Selenium   │  │ API Spider │             │
│  └────────────┘  └────────────┘  └────────────┘             │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                  中间件层 (Middlewares)                        │
│  User-Agent 轮换 │ 代理池管理 │ 智能重试 │ Referer 伪装      │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                  数据管道层 (Pipelines)                        │
│  数据清洗 → 去重过滤 → MySQL / MongoDB / CSV 存储            │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                   存储层 (Storage)                            │
│         MySQL (结构化数据)  │  MongoDB (文档数据)              │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                   分析层 (Analysis)                           │
│        价格统计  │  趋势图表  │  降价预警  │  报告导出          │
└─────────────────────────────────────────────────────────────┘
```

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 爬虫框架 | Scrapy 2.11 | 异步高性能爬虫框架 |
| 分布式调度 | Redis + scrapy-redis | 分布式任务队列与去重 |
| 动态渲染 | Selenium + ChromeDriver | 处理 JavaScript 动态页面 |
| 关系数据库 | MySQL 8.0 + PyMySQL | 结构化商品数据存储 |
| 文档数据库 | MongoDB + pymongo | 价格历史与日志存储 |
| 定时任务 | schedule | 周期性爬虫任务调度 |
| 数据分析 | pandas + matplotlib | 价格趋势分析与可视化 |
| 配置管理 | PyYAML | YAML 配置文件解析 |

## 核心功能

- **多平台采集**: 支持京东、淘宝、苏宁等电商平台
- **分布式爬虫**: 基于 Redis 的分布式任务调度，支持多节点部署
- **反爬策略**: User-Agent 轮换、代理池、智能重试、请求间隔随机化
- **数据清洗**: 自动清洗价格字段、规范化数据格式
- **价格趋势分析**: 历史价格追踪、统计分析与可视化图表
- **多存储后端**: MySQL、MongoDB、CSV 多格式数据导出

## 项目结构

```
scrapy-price-monitor/
├── README.md                  # 项目说明文档
├── requirements.txt           # Python 依赖包
├── scrapy.cfg                 # Scrapy 部署配置
├── config.yaml                # 系统配置文件
├── main.py                    # 主程序入口 (定时调度)
├── analysis.py                # 价格分析脚本
├── .gitignore                 # Git 忽略规则
└── price_monitor/             # 核心项目目录
    ├── __init__.py
    ├── settings.py            # Scrapy 全局配置
    ├── items.py               # 数据模型定义
    ├── middlewares.py         # 自定义中间件
    ├── pipelines.py           # 数据处理管道
    ├── spiders/               # 爬虫模块
    │   ├── __init__.py
    │   ├── jd_spider.py       # 京东爬虫
    │   ├── taobao_spider.py   # 淘宝爬虫
    │   └── suning_spider.py   # 苏宁爬虫
    └── utils/                 # 工具模块
        ├── __init__.py
        ├── anti_detect.py     # 反检测工具
        └── db_helper.py       # 数据库工具
```

## 快速开始

### 1. 环境要求

- Python 3.8+
- Redis 服务
- MySQL 8.0+
- MongoDB 5.0+
- Google Chrome (用于 Selenium)

### 2. 安装依赖

```bash
# 克隆项目
git clone https://github.com/your-username/scrapy-price-monitor.git
cd scrapy-price-monitor

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

编辑 `config.yaml` 文件，配置数据库连接信息和爬虫参数：

```yaml
database:
  mysql:
    host: 127.0.0.1
    port: 3306
    user: root
    password: your_password
    database: price_monitor

  mongodb:
    uri: mongodb://127.0.0.1:27017
    database: price_monitor

  redis:
    url: redis://127.0.0.1:6379/0
```

### 4. 初始化数据库

```bash
# 创建 MySQL 数据表
python -c "from price_monitor.utils.db_helper import init_mysql_tables; init_mysql_tables()"
```

### 5. 运行爬虫

```bash
# 运行单个爬虫
scrapy crawl jd

# 通过主程序运行 (带定时调度)
python main.py

# 运行价格分析
python analysis.py
```

## 使用方式

### 命令行运行

```bash
# 京东商品搜索
scrapy crawl jd -a keyword="手机"

# 淘宝商品搜索 (需要 Selenium)
scrapy crawl taobao -a keyword="笔记本"

# 苏宁商品搜索
scrapy crawl suning -a keyword="耳机"
```

### 定时任务

编辑 `main.py` 中的调度配置：

```python
schedule.every(2).hours.do(run_spider, spider_name='jd', keyword='手机')
schedule.every().day.at("10:00").do(run_spider, spider_name='taobao', keyword='笔记本')
```

### 数据分析

```bash
# 生成价格趋势报告
python analysis.py --category 手机 --days 30

# 导出 CSV 报告
python analysis.py --export csv --output report.csv
```

## 扩展开发

### 添加新平台爬虫

1. 在 `price_monitor/spiders/` 下创建新的爬虫文件
2. 继承 `scrapy.Spider` 或 `CrawlSpider`
3. 在 `items.py` 中定义所需数据字段
4. 配置 `settings.py` 中的中间件和管道

### 自定义中间件

在 `price_monitor/middlewares.py` 中添加新的中间件类，然后在 `settings.py` 中注册。

## 注意事项

- 请遵守各电商平台的 `robots.txt` 和使用条款
- 合理控制爬取频率，避免对目标服务器造成压力
- 淘宝爬虫需要登录态，建议配合 Cookie 池使用
- 生产环境建议部署代理池以提高稳定性
- 数据仅供学习研究使用，请勿用于商业用途

## License

[MIT License](LICENSE)
