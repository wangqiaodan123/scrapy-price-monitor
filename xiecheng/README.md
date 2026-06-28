# Ctrip Travel Data Crawler & Visualization Dashboard

> 基于 Scrapy + Selenium 的携程旅游产品数据采集与可视化分析系统

## 项目简介

本项目以 [携程度假频道](https://vacations.ctrip.com) 为数据源，通过 Scrapy 爬虫框架结合 Selenium 动态渲染技术，实现对跟团游、自由行、私家团、拼小团、一日游等多品类旅游产品的全量数据采集。后端采用 MySQL 异步连接池持久化存储，前端基于 pyecharts 构建交互式数据可视化仪表盘，形成 **采集 → 存储 → 清洗 → 分析 → 展示** 的完整数据链路。

## 核心特性

- **动态渲染抓取** — Selenium WebDriver 驱动 Chrome 浏览器，解决 JS 动态渲染页面无法直接解析的难题
- **反爬对抗** — CDP 协议隐藏 `webdriver` 特征 + 随机翻页延时 + 自定义 User-Agent
- **异步数据入库** — Twisted adbapi 连接池，IO 操作不阻塞爬虫主线程
- **数据库去重** — `INSERT IGNORE` 基于 `source_url` 唯一索引自动去重
- **交互式仪表盘** — 单文件 HTML，10 个 ECharts 图表，支持命令行多维筛选
- **交互式 SQL 查询** — 内置快捷命令与自定义 SQL 模式

## 技术栈

| 模块 | 技术 |
|------|------|
| 爬虫框架 | Scrapy 2.x |
| 动态渲染 | Selenium WebDriver + Chrome |
| 数据存储 | MySQL + pymysql |
| 异步连接池 | Twisted adbapi |
| 数据分析 | pandas |
| 可视化 | pyecharts (ECharts 5) |
| 静态图表 | matplotlib + seaborn |

## 项目结构

```
xiecheng/
├── scrapy.cfg                  # Scrapy 项目配置
├── xiecheng/
│   ├── spiders/
│   │   └── ctrip.py            # 核心爬虫：Selenium + XPath 解析
│   ├── items.py                # 数据模型定义（7 个字段）
│   ├── middlewares.py          # 中间件（SeleniumMiddleware）
│   ├── pipelines.py            # 数据管道（MySQL 异步连接池）
│   └── settings.py             # 项目配置（数据库、UA、管道）
├── ctrip_visualization.py      # 可视化仪表盘生成脚本
├── test.py                     # matplotlib 静态分析图表
└── README.md
```

## 环境准备

### 依赖安装

```bash
pip install scrapy selenium pymysql twisted pandas pyecharts openpyxl matplotlib seaborn
```

### Chrome WebDriver

项目使用 Selenium 驱动 Chrome 浏览器，请确保：

1. 已安装 [Google Chrome](https://www.google.com/chrome/)
2. 已安装 [ChromeDriver](https://chromedriver.chromium.org/)，版本需与 Chrome 匹配

> 推荐使用 `webdriver-manager` 自动管理：
> ```bash
> pip install webdriver-manager
> ```

### 数据库准备

```sql
CREATE DATABASE ctrip_db DEFAULT CHARACTER SET utf8mb4;

USE ctrip_db;

CREATE TABLE ctrip_travel_products_raw (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(500),
    subtitle TEXT,
    price VARCHAR(50),
    score VARCHAR(20),
    comment_count VARCHAR(50),
    sold_count VARCHAR(50),
    source_url VARCHAR(500) UNIQUE
);
```

## 快速开始

### 1. 运行爬虫

```bash
cd xiecheng
scrapy crawl ctrip
```

爬虫将自动打开 Chrome 浏览器，从携程度假列表页开始逐页抓取产品数据，并通过异步连接池写入 MySQL。

### 2. 生成可视化仪表盘

```bash
# 全量数据
python ctrip_visualization.py

# 按条件筛选
python ctrip_visualization.py --min-price 500 --max-price 5000
python ctrip_visualization.py --keyword 新疆 --min-score 4.5
python ctrip_visualization.py --type 自由行 --limit 200

# 交互式查询模式
python ctrip_visualization.py --query
```

生成的仪表盘文件位于项目根目录：`ctrip_dashboard.html`，用浏览器打开即可查看。

## 数据模型

每条记录包含以下 7 个核心字段：

| 字段 | 说明 | 示例 |
|------|------|------|
| `title` | 产品标题 | 新疆乌鲁木齐+伊犁+赛里木湖6日跟团游 |
| `subtitle` | 副标题/卖点 | 含接送机·纯玩无购物 |
| `price` | 价格（元） | 4580 |
| `score` | 评分 | 4.8 |
| `comment_count` | 点评数 | 192条点评 |
| `sold_count` | 销量 | 已售675 |
| `source_url` | 详情页链接 | https://vacations.ctrip.com/travel/detail/p... |

## 可视化图表

仪表盘包含以下 10 个交互式图表：

1. **价格区间分布** — 柱状图，10 个价格区间
2. **评分分布** — 柱状图，按评分段统计
3. **销量 TOP15** — 横向柱状图
4. **点评数 TOP15** — 横向柱状图
5. **产品类型分布** — 环形饼图（跟团游/自由行/私家团等 8 大类）
6. **旅游天数分布** — 柱状图（1~15天）
7. **价格 vs 评分散点图** — 气泡大小代表销量
8. **热门目的地 TOP20** — 横向柱状图（覆盖 80+ 城市/省份）
9. **产品类型价格箱线图** — 各品类的价格分布
10. **评分区间 vs 销量对比** — 分组柱状图

### 命令行筛选参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--min-price` | 最低价格 | `--min-price 500` |
| `--max-price` | 最高价格 | `--max-price 5000` |
| `--min-score` | 最低评分 | `--min-score 4.5` |
| `--keyword` | 标题关键词 | `--keyword 新疆,西藏` |
| `--type` | 产品类型 | `--type 自由行` |
| `--days` | 旅游天数 | `--days 5` |
| `--limit` | 限制条数 | `--limit 200` |

### 交互式查询命令

进入 `--query` 模式后支持以下快捷命令：

| 命令 | 说明 |
|------|------|
| `stats` | 数据概览统计 |
| `top N` | 销量前 N 的产品 |
| `price A B` | 价格区间统计 |
| `search 关键词` | 标题搜索 |
| `types` | 按产品类型统计 |
| `dest` | 热门目的地统计 |

## 数据清洗管道

可视化脚本内置了完整的数据清洗流程：

- **价格解析** — 过滤非数字值（"实时计价""暂无价格"等），统一转为浮点数
- **评分归一** — 字符串转浮点，处理空值
- **销量/点评数解析** — 识别"万"单位，自动换算（如"1.2万" → 12000）
- **旅游天数提取** — 正则匹配"N日"格式
- **产品类型分类** — 关键词规则引擎，自动分为跟团游/自由行/私家团/拼小团/一日游/亲子游/研学营/讲解服务 8 大类
- **目的地提取** — 基于 80+ 热门城市 + 32 个省份的关键词库智能匹配

## License

MIT
