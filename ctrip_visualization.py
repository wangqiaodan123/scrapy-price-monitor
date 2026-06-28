# -*- coding: utf-8 -*-
"""
携程旅游产品数据可视化仪表盘
从 MySQL 数据库读取数据，使用 pyecharts 生成交互式 HTML 页面

用法:
    python ctrip_visualization.py                          # 使用默认配置
    python ctrip_visualization.py --host 192.168.1.100     # 指定主机
    python ctrip_visualization.py --min-price 500 --max-price 5000   # 价格区间筛选
    python ctrip_visualization.py --min-score 4.5          # 只看高评分
    python ctrip_visualization.py --keyword 新疆            # 按关键词筛选
    python ctrip_visualization.py --type 跟团游             # 按产品类型筛选
    python ctrip_visualization.py --limit 100              # 限制返回条数
    python ctrip_visualization.py --query                  # 进入交互式查询模式
"""

import pandas as pd
import pymysql
import re
import os
import sys
import argparse

sys.stdout.reconfigure(encoding='utf-8')

from pyecharts import options as opts
from pyecharts.charts import (
    Bar, Pie, Scatter, Page, WordCloud, Boxplot, Liquid, Grid
)
from pyecharts.commons.utils import JsCode

# ────────────────────────────────────────────
# 1. 数据库连接与数据读取
# ────────────────────────────────────────────

# 默认数据库配置（可通过命令行参数覆盖）
DEFAULT_DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '1234',
    'database': 'ctrip_db',
    'charset': 'utf8mb4',
}

TABLE_NAME = 'ctrip_travel_products_raw'


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='携程旅游产品数据可视化 — 从数据库读取数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python ctrip_visualization.py
  python ctrip_visualization.py --min-price 500 --max-price 5000
  python ctrip_visualization.py --keyword 新疆 --min-score 4.5
  python ctrip_visualization.py --type 自由行 --limit 200
  python ctrip_visualization.py --query
        """
    )
    # 数据库连接参数
    db_group = parser.add_argument_group('数据库连接')
    db_group.add_argument('--host', default=DEFAULT_DB_CONFIG['host'], help='数据库主机 (默认: localhost)')
    db_group.add_argument('--port', type=int, default=DEFAULT_DB_CONFIG['port'], help='数据库端口 (默认: 3306)')
    db_group.add_argument('--user', default=DEFAULT_DB_CONFIG['user'], help='数据库用户名 (默认: root)')
    db_group.add_argument('--password', default=DEFAULT_DB_CONFIG['password'], help='数据库密码 (默认: 1234)')
    db_group.add_argument('--database', default=DEFAULT_DB_CONFIG['database'], help='数据库名 (默认: ctrip_db)')

    # 数据筛选参数
    filter_group = parser.add_argument_group('数据筛选')
    filter_group.add_argument('--min-price', type=float, default=None, help='最低价格')
    filter_group.add_argument('--max-price', type=float, default=None, help='最高价格')
    filter_group.add_argument('--min-score', type=float, default=None, help='最低评分')
    filter_group.add_argument('--max-score', type=float, default=None, help='最高评分')
    filter_group.add_argument('--min-sold', type=int, default=None, help='最低销量')
    filter_group.add_argument('--keyword', type=str, default=None, help='标题关键词筛选（支持多个，逗号分隔）')
    filter_group.add_argument('--type', type=str, default=None, help='产品类型筛选（跟团游/自由行/私家团/拼小团/一日游等）')
    filter_group.add_argument('--days', type=int, default=None, help='旅游天数')
    filter_group.add_argument('--limit', type=int, default=None, help='限制返回条数')
    filter_group.add_argument('--order-by', type=str, default='sold_num',
                              choices=['price', 'score', 'comment_count', 'sold_count', 'sold_num'],
                              help='排序字段 (默认: sold_num)')
    filter_group.add_argument('--order-dir', type=str, default='DESC', choices=['ASC', 'DESC'],
                              help='排序方向 (默认: DESC)')

    # 交互模式
    parser.add_argument('--query', action='store_true', help='进入交互式查询模式')
    parser.add_argument('--sql', type=str, default=None, help='自定义 SQL 查询（SELECT 语句）')

    return parser.parse_args()


def get_db_connection(args):
    """建立数据库连接"""
    config = {
        'host': args.host,
        'port': args.port,
        'user': args.user,
        'password': args.password,
        'database': args.database,
        'charset': 'utf8mb4',
    }
    print(f"[INFO] 连接数据库: {config['user']}@{config['host']}:{config['port']}/{config['database']}")
    return pymysql.connect(**config)


def build_query(args):
    """根据筛选条件构建 SQL 查询"""
    conditions = []
    params = []

    # 价格筛选（先排除非数字价格）
    if args.min_price is not None:
        conditions.append("CAST(price AS DECIMAL(10,2)) >= %s AND price REGEXP '^[0-9]'")
        params.append(args.min_price)
    if args.max_price is not None:
        conditions.append("CAST(price AS DECIMAL(10,2)) <= %s AND price REGEXP '^[0-9]'")
        params.append(args.max_price)

    # 评分筛选
    if args.min_score is not None:
        conditions.append("CAST(score AS DECIMAL(3,1)) >= %s AND score != ''")
        params.append(args.min_score)
    if args.max_score is not None:
        conditions.append("CAST(score AS DECIMAL(3,1)) <= %s AND score != ''")
        params.append(args.max_score)

    # 关键词筛选
    if args.keyword:
        keywords = [k.strip() for k in args.keyword.split(',')]
        for kw in keywords:
            conditions.append("title LIKE %s")
            params.append(f'%{kw}%')

    # 产品类型筛选
    if args.type:
        conditions.append("title LIKE %s")
        params.append(f'%{args.type}%')

    # 天数筛选
    if args.days is not None:
        conditions.append("title REGEXP %s")
        params.append(f'{args.days}日')

    where_clause = ''
    if conditions:
        where_clause = 'WHERE ' + ' AND '.join(conditions)

    # 排序
    order_map = {
        'price': "CAST(price AS DECIMAL(10,2))",
        'score': "CAST(score AS DECIMAL(3,1))",
        'comment_count': "CAST(REPLACE(REPLACE(comment_count, '条点评', ''), '万', '0000') AS UNSIGNED)",
        'sold_count': "sold_count",
        'sold_num': """CASE
            WHEN sold_count LIKE '%%万%%' THEN CAST(REGEXP_REPLACE(sold_count, '[^0-9.]', '') AS DECIMAL(10,2)) * 10000
            WHEN sold_count LIKE '%%月销%%' THEN CAST(REGEXP_REPLACE(sold_count, '[^0-9]', '') AS UNSIGNED)
            ELSE CAST(REGEXP_REPLACE(sold_count, '[^0-9]', '') AS UNSIGNED)
        END""",
    }
    order_expr = order_map.get(args.order_by, 'id')
    order_clause = f'ORDER BY {order_expr} {args.order_dir}'

    # 限制条数
    limit_clause = ''
    if args.limit:
        limit_clause = f'LIMIT {args.limit}'

    sql = f"SELECT * FROM {TABLE_NAME} {where_clause} {order_clause} {limit_clause}"
    return sql, params


def load_data_from_db(args):
    """从数据库加载数据到 DataFrame"""
    conn = get_db_connection(args)
    try:
        if args.sql:
            # 自定义 SQL
            sql = args.sql
            params = []
            print(f"[INFO] 执行自定义 SQL: {sql[:100]}...")
        else:
            sql, params = build_query(args)
            print(f"[INFO] 查询条件: {'有筛选' if params else '无筛选 (全量数据)'}")

        df = pd.read_sql(sql, conn, params=params)
        print(f"[INFO] 查询返回 {len(df)} 条记录")

        # 打印一些统计摘要
        if len(df) > 0:
            print(f"[INFO] 列名: {list(df.columns)}")

        return df
    finally:
        conn.close()


def interactive_query(args):
    """交互式查询模式"""
    conn = get_db_connection(args)
    print("\n" + "=" * 60)
    print("  携程旅游产品 - 交互式查询模式")
    print("=" * 60)
    print("输入 SQL 查询语句，或输入以下快捷命令：")
    print("  stats        — 查看数据概览统计")
    print("  top N        — 查看销量前 N 的产品 (默认10)")
    print("  price A B    — 查看价格区间 A-B 的产品统计")
    print("  search 关键词 — 搜索标题含关键词的产品")
    print("  types        — 按产品类型统计")
    print("  dest         — 热门目的地统计")
    print("  quit / exit  — 退出查询")
    print("=" * 60)

    try:
        while True:
            try:
                cmd = input("\n> query> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n退出查询。")
                break

            if not cmd:
                continue
            if cmd.lower() in ('quit', 'exit', 'q'):
                print("退出查询。")
                break

            # 快捷命令
            if cmd.lower() == 'stats':
                cmd = f"""SELECT
                    COUNT(*) AS 总数,
                    COUNT(CASE WHEN price REGEXP '^[0-9]' THEN 1 END) AS 有价格数,
                    ROUND(AVG(CASE WHEN price REGEXP '^[0-9]' THEN CAST(price AS DECIMAL(10,2)) END), 0) AS 均价,
                    ROUND(MIN(CASE WHEN price REGEXP '^[0-9]' THEN CAST(price AS DECIMAL(10,2)) END), 0) AS 最低价,
                    ROUND(MAX(CASE WHEN price REGEXP '^[0-9]' THEN CAST(price AS DECIMAL(10,2)) END), 0) AS 最高价,
                    ROUND(AVG(CASE WHEN score != '' THEN CAST(score AS DECIMAL(3,1)) END), 2) AS 平均评分
                FROM {TABLE_NAME}"""

            elif cmd.lower().startswith('top'):
                n = 10
                parts = cmd.split()
                if len(parts) > 1:
                    try:
                        n = int(parts[1])
                    except ValueError:
                        pass
                cmd = f"""SELECT id, LEFT(title, 40) AS 产品, price AS 价格, score AS 评分,
                    sold_count AS 销量 FROM {TABLE_NAME}
                    WHERE sold_count IS NOT NULL AND sold_count != ''
                    ORDER BY CASE
                        WHEN sold_count LIKE '%%万%%' THEN CAST(REGEXP_REPLACE(sold_count, '[^0-9.]', '') AS DECIMAL(10,2)) * 10000
                        ELSE CAST(REGEXP_REPLACE(sold_count, '[^0-9]', '') AS UNSIGNED)
                    END DESC
                    LIMIT {n}"""

            elif cmd.lower().startswith('price'):
                parts = cmd.split()
                a, b = 0, 999999
                if len(parts) >= 3:
                    try:
                        a, b = int(parts[1]), int(parts[2])
                    except ValueError:
                        pass
                cmd = f"""SELECT
                    CASE
                        WHEN CAST(price AS DECIMAL(10,2)) < 100 THEN '0-100'
                        WHEN CAST(price AS DECIMAL(10,2)) < 500 THEN '100-500'
                        WHEN CAST(price AS DECIMAL(10,2)) < 1000 THEN '500-1K'
                        WHEN CAST(price AS DECIMAL(10,2)) < 3000 THEN '1K-3K'
                        WHEN CAST(price AS DECIMAL(10,2)) < 5000 THEN '3K-5K'
                        ELSE '5K+'
                    END AS 价格区间,
                    COUNT(*) AS 数量,
                    ROUND(AVG(CAST(price AS DECIMAL(10,2))), 0) AS 均价
                FROM {TABLE_NAME}
                WHERE price REGEXP '^[0-9]'
                    AND CAST(price AS DECIMAL(10,2)) BETWEEN {a} AND {b}
                GROUP BY 价格区间
                ORDER BY MIN(CAST(price AS DECIMAL(10,2)))"""

            elif cmd.lower().startswith('search'):
                parts = cmd.split(maxsplit=1)
                kw = parts[1] if len(parts) > 1 else ''
                if not kw:
                    print("用法: search 关键词")
                    continue
                cmd = f"""SELECT id, LEFT(title, 45) AS 产品, price AS 价格, score AS 评分, sold_count AS 销量
                    FROM {TABLE_NAME} WHERE title LIKE '%{kw}%' ORDER BY id LIMIT 50"""

            elif cmd.lower() == 'types':
                cmd = f"""SELECT
                    CASE
                        WHEN title LIKE '%%一日游%%' THEN '一日游'
                        WHEN title LIKE '%%半日%%' THEN '半日游'
                        WHEN title LIKE '%%亲子%%' THEN '亲子游'
                        WHEN title LIKE '%%自由行%%' THEN '自由行'
                        WHEN title LIKE '%%私家团%%' THEN '私家团'
                        WHEN title LIKE '%%拼小团%%' THEN '拼小团'
                        WHEN title LIKE '%%跟团%%' THEN '跟团游'
                        WHEN title LIKE '%%讲解%%' OR title LIKE '%%博物馆%%' THEN '讲解服务'
                        ELSE '其他'
                    END AS 产品类型,
                    COUNT(*) AS 数量,
                    ROUND(AVG(CASE WHEN price REGEXP '^[0-9]' THEN CAST(price AS DECIMAL(10,2)) END), 0) AS 均价
                FROM {TABLE_NAME}
                GROUP BY 产品类型
                ORDER BY 数量 DESC"""

            elif cmd.lower() == 'dest':
                dest_keywords = [
                    '新疆', '云南', '西藏', '四川', '北京', '海南', '三亚', '丽江',
                    '大理', '西安', '桂林', '张家界', '厦门', '成都', '青岛', '杭州',
                    '呼伦贝尔', '贵州', '敦煌', '青海', '重庆', '威海', '苏州', '南京',
                    '武汉', '长沙', '昆明', '景德镇', '恩施', '黄山',
                ]
                case_parts = []
                for d in dest_keywords:
                    case_parts.append(f"SUM(CASE WHEN title LIKE '%{d}%' THEN 1 ELSE 0 END) AS `{d}`")
                cmd = f"SELECT {', '.join(case_parts)} FROM {TABLE_NAME}"

            try:
                result = pd.read_sql(cmd, conn)
                print(f"\n返回 {len(result)} 行:\n")
                pd.set_option('display.max_columns', None)
                pd.set_option('display.width', 120)
                pd.set_option('display.max_colwidth', 50)
                print(result.to_string(index=False))
            except Exception as e:
                print(f"[ERROR] {e}")
    finally:
        conn.close()


# ────────────────────────────────────────────
# 2. 数据清洗
# ────────────────────────────────────────────

def clean_data(df):
    """清洗数据：解析价格、评分、销量等字段"""

    def parse_price(val):
        if pd.isna(val):
            return float('nan')
        val = str(val).strip()
        if val in ('', '实时计价', '暂无价格', '-'):
            return float('nan')
        val = val.replace(',', '').replace('￥', '').replace('元', '')
        try:
            return float(val)
        except ValueError:
            return float('nan')

    df['price_num'] = df['price'].apply(parse_price)

    def parse_score(val):
        if pd.isna(val):
            return float('nan')
        try:
            return float(val)
        except ValueError:
            return float('nan')

    df['score_num'] = df['score'].apply(parse_score)

    def parse_comment(val):
        if pd.isna(val):
            return 0
        val = str(val).strip()
        m = re.search(r'([\d,.]+)\s*万', val)
        if m:
            return int(float(m.group(1).replace(',', '')) * 10000)
        m = re.search(r'([\d,]+)', val)
        if m:
            return int(m.group(1).replace(',', ''))
        return 0

    df['comment_num'] = df['comment_count'].apply(parse_comment)

    def parse_sold(val):
        if pd.isna(val):
            return 0
        val = str(val).strip()
        m = re.search(r'([\d,.]+)\s*万', val)
        if m:
            return int(float(m.group(1).replace(',', '')) * 10000)
        m = re.search(r'([\d,]+)', val)
        if m:
            return int(m.group(1).replace(',', ''))
        return 0

    df['sold_num'] = df['sold_count'].apply(parse_sold)

    def parse_days(title):
        if pd.isna(title):
            return None
        m = re.search(r'(\d+)日', str(title))
        if m:
            d = int(m.group(1))
            if 1 <= d <= 30:
                return d
        return None

    df['days'] = df['title'].apply(parse_days)

    def classify_product(title):
        if pd.isna(title):
            return '其他'
        t = str(title)
        if '一日游' in t:
            return '一日游'
        if '亲子营' in t or '亲子' in t:
            return '亲子游'
        if '自由行' in t:
            return '自由行'
        if '私家团' in t:
            return '私家团'
        if '拼小团' in t:
            return '拼小团'
        if '跟团游' in t or '跟团' in t:
            return '跟团游'
        if '半日' in t:
            return '半日游'
        if '讲解' in t or '博物馆' in t:
            return '讲解服务'
        if '营' in t and ('户外' in t or '自然' in t or '名校' in t):
            return '研学营'
        return '其他'

    df['product_type'] = df['title'].apply(classify_product)

    HOT_CITIES = [
        '三亚', '丽江', '大理', '桂林', '张家界', '九寨沟', '黄山', '厦门',
        '成都', '西安', '拉萨', '敦煌', '西宁', '兰州', '呼伦贝尔', '威海',
        '青岛', '大连', '昆明', '杭州', '苏州', '南京', '武汉', '长沙',
        '重庆', '广州', '深圳', '哈尔滨', '南昌', '景德镇', '台州', '丽水',
        '温州', '汕头', '潮州', '惠州', '珠海', '呼和浩特', '乌兰布统',
        '满洲里', '额尔古纳', '阿尔山', '喀什', '伊犁', '喀纳斯', '禾木',
        '赛里木湖', '那拉提', '巴音布鲁克', '独库', '林芝', '日喀则', '纳木措',
        '珠峰', '稻城', '色达', '腾冲', '泸沽湖', '西双版纳', '香格里拉',
        '响沙湾', '茶卡盐湖', '青海湖', '莫高窟', '嘉峪关', '平遥',
        '兵马俑', '华山', '老君山', '云冈', '悬空寺', '应县木塔',
        '神农架', '恩施', '庐山', '三清山', '婺源', '雁荡山', '楠溪江',
        '仙都', '古堰画乡', '天台山', '神仙居', '南澳岛', '长岛',
        '蓬莱', '烟台', '宏村', '西递', '周庄', '乌镇', '西塘',
    ]
    PROVINCES = [
        '新疆', '西藏', '云南', '四川', '贵州', '广西', '海南', '广东',
        '福建', '浙江', '江苏', '安徽', '江西', '湖南', '湖北', '河南',
        '山东', '山西', '陕西', '甘肃', '青海', '宁夏', '内蒙古',
        '黑龙江', '吉林', '辽宁', '河北', '北京', '天津', '上海', '重庆',
    ]

    def extract_destinations(title):
        if pd.isna(title):
            return []
        t = str(title)
        found = []
        for city in HOT_CITIES:
            if city in t:
                found.append(city)
        if not found:
            for prov in PROVINCES:
                if prov in t:
                    found.append(prov)
        return found

    df['destinations'] = df['title'].apply(extract_destinations)

    return df


# ────────────────────────────────────────────
# 3. 颜色与样式主题
# ────────────────────────────────────────────

# 清新青绿配色
COLORS = [
    '#0d9488', '#14b8a6', '#06b6d4', '#0891b2', '#2dd4bf',
    '#0f766e', '#67e8f9', '#34d399', '#10b981', '#059669',
    '#99f6e4', '#a7f3d0', '#ccfbf1'
]

BG_COLOR = '#ffffff'
TITLE_COLOR = '#1e293b'
TEXT_COLOR = '#64748b'
SPLIT_LINE = '#e2e8f0'
AXIS_LINE = '#cbd5e1'


def base_title_opts(text, subtext=''):
    return opts.TitleOpts(
        title=text,
        subtitle=subtext,
        title_textstyle_opts=opts.TextStyleOpts(
            font_size=16, color=TITLE_COLOR, font_weight='bold',
            font_family='Microsoft YaHei'
        ),
        subtitle_textstyle_opts=opts.TextStyleOpts(
            font_size=11, color=TEXT_COLOR
        ),
        pos_left='center', pos_top='3%'
    )


def base_axis_opts():
    return opts.LabelOpts(color=TEXT_COLOR)


# ────────────────────────────────────────────
# 4. 图表生成函数
# ────────────────────────────────────────────

def chart_price_distribution(df):
    """价格区间分布"""
    valid_price = df[df['price_num'].notna()]
    prices = valid_price['price_num']
    bins = [0, 100, 300, 500, 1000, 2000, 3000, 5000, 8000, 15000, float('inf')]
    labels = ['0-100', '100-300', '300-500', '500-1K', '1K-2K', '2K-3K', '3K-5K', '5K-8K', '8K-15K', '15K+']
    counts = pd.cut(prices, bins=bins, labels=labels, right=False).value_counts().reindex(labels, fill_value=0)

    c = Bar(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add_xaxis(labels)
    c.add_yaxis('产品数量', counts.tolist(),
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode("""new echarts.graphic.LinearGradient(0,0,0,1,[
                        {offset:0,color:'#5eead4'},{offset:1,color:'#0d9488'}
                    ])""")
                ))
    c.set_global_opts(
        title_opts=base_title_opts('产品价格区间分布', f'共 {len(valid_price)} 个有效价格产品'),
        xaxis_opts=opts.AxisOpts(
            name='价格 (元)', axislabel_opts=base_axis_opts(),
            axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color=AXIS_LINE))
        ),
        yaxis_opts=opts.AxisOpts(
            name='数量', axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE))
        ),
        tooltip_opts=opts.TooltipOpts(trigger='axis', axis_pointer_type='shadow'),
        legend_opts=opts.LegendOpts(is_show=False),
    )
    return c


def chart_score_distribution(df):
    """评分分布"""
    valid_score = df[df['score_num'].notna()]
    scores = valid_score['score_num']
    bins_score = [0, 3.0, 3.5, 4.0, 4.3, 4.5, 4.7, 4.8, 4.9, 5.01]
    labels_score = ['<3.0', '3.0-3.5', '3.5-4.0', '4.0-4.3', '4.3-4.5', '4.5-4.7', '4.7-4.8', '4.8-4.9', '5.0']
    counts_score = pd.cut(scores, bins=bins_score, labels=labels_score, right=False).value_counts().reindex(labels_score, fill_value=0)

    c = Bar(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add_xaxis(labels_score)
    c.add_yaxis('产品数量', counts_score.tolist())
    c.set_global_opts(
        title_opts=base_title_opts('产品评分分布', f'共 {len(valid_score)} 个有评分产品'),
        xaxis_opts=opts.AxisOpts(
            name='评分', axislabel_opts=base_axis_opts(),
            axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color=AXIS_LINE))
        ),
        yaxis_opts=opts.AxisOpts(
            name='数量', axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE))
        ),
        tooltip_opts=opts.TooltipOpts(trigger='axis', axis_pointer_type='shadow'),
        legend_opts=opts.LegendOpts(is_show=False),
        visualmap_opts=opts.VisualMapOpts(
            is_show=False, dimension=1,
            pieces=[
                {"lt": 50, "color": "#67e8f9"},
                {"gte": 50, "lt": 200, "color": "#2dd4bf"},
                {"gte": 200, "lt": 500, "color": "#14b8a6"},
                {"gte": 500, "color": "#0d9488"},
            ]
        )
    )
    return c


def chart_top_sold(df):
    """销量 TOP15"""
    top = df.nlargest(15, 'sold_num')[['title', 'sold_num', 'price_num', 'score_num']].copy()
    top['short_title'] = top['title'].apply(lambda x: (x[:18] + '...') if len(str(x)) > 18 else x)
    titles = top['short_title'].tolist()[::-1]
    values = top['sold_num'].tolist()[::-1]

    c = Bar(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add_xaxis(titles)
    c.add_yaxis('销量', values,
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode("""new echarts.graphic.LinearGradient(1,0,0,0,[
                        {offset:0,color:'#5eead4'},{offset:1,color:'#0d9488'}
                    ])"""),
                    border_radius=[0, 4, 4, 0]
                ),
                label_opts=opts.LabelOpts(position='right', color=TEXT_COLOR, formatter='{c}')
                )
    c.reversal_axis()
    c.set_global_opts(
        title_opts=base_title_opts('销量 TOP15 产品'),
        xaxis_opts=opts.AxisOpts(
            type_='value', axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE))
        ),
        yaxis_opts=opts.AxisOpts(
            type_='category', axislabel_opts=opts.LabelOpts(overflow='truncate'),
            axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color=AXIS_LINE))
        ),
        tooltip_opts=opts.TooltipOpts(trigger='axis', axis_pointer_type='shadow'),
        legend_opts=opts.LegendOpts(is_show=False),
    )
    return c


def chart_top_commented(df):
    """点评数 TOP15"""
    top = df.nlargest(15, 'comment_num')[['title', 'comment_num', 'score_num']].copy()
    top['short_title'] = top['title'].apply(lambda x: (x[:18] + '...') if len(str(x)) > 18 else x)
    titles = top['short_title'].tolist()[::-1]
    values = top['comment_num'].tolist()[::-1]

    c = Bar(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add_xaxis(titles)
    c.add_yaxis('点评数', values,
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode("""new echarts.graphic.LinearGradient(1,0,0,0,[
                        {offset:0,color:'#67e8f9'},{offset:1,color:'#0891b2'}
                    ])"""),
                    border_radius=[0, 4, 4, 0]
                ),
                label_opts=opts.LabelOpts(position='right', color=TEXT_COLOR, formatter='{c}')
                )
    c.reversal_axis()
    c.set_global_opts(
        title_opts=base_title_opts('点评数 TOP15 产品'),
        xaxis_opts=opts.AxisOpts(
            type_='value', axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE))
        ),
        yaxis_opts=opts.AxisOpts(
            type_='category', axislabel_opts=opts.LabelOpts(overflow='truncate'),
            axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color=AXIS_LINE))
        ),
        tooltip_opts=opts.TooltipOpts(trigger='axis', axis_pointer_type='shadow'),
        legend_opts=opts.LegendOpts(is_show=False),
    )
    return c


def chart_product_type(df):
    """产品类型分布"""
    type_counts = df['product_type'].value_counts()
    data = [(name, int(cnt)) for name, cnt in type_counts.items()]
    data.sort(key=lambda x: x[1], reverse=True)

    c = Pie(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add('', data, radius=['35%', '65%'], center=['50%', '55%'],
          label_opts=opts.LabelOpts(color=TEXT_COLOR, font_size=11, formatter='{b}: {c} ({d}%)'))
    c.set_colors(COLORS)
    c.set_global_opts(
        title_opts=base_title_opts('旅游产品类型分布'),
        tooltip_opts=opts.TooltipOpts(
            trigger='item',
            formatter=JsCode("""function(p){return p.name+'<br/>数量: '+p.value+'<br/>占比: '+p.percent+'%'}""")
        ),
        legend_opts=opts.LegendOpts(
            is_show=True, pos_bottom='2%', pos_left='center',
            textstyle_opts=opts.TextStyleOpts(color=TEXT_COLOR, font_size=10), type_='scroll'
        ),
    )
    return c


def chart_days_distribution(df):
    """旅游天数分布"""
    days_data = df[df['days'].notna()].copy()
    days_counts = days_data['days'].value_counts().sort_index()
    days_counts = days_counts[(days_counts.index >= 1) & (days_counts.index <= 15)]
    labels = [f'{d}天' for d in days_counts.index.tolist()]

    c = Bar(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add_xaxis(labels)
    c.add_yaxis('产品数量', days_counts.values.tolist(),
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode("""new echarts.graphic.LinearGradient(0,0,0,1,[
                        {offset:0,color:'#67e8f9'},{offset:1,color:'#0d9488'}
                    ])""")
                ))
    c.set_global_opts(
        title_opts=base_title_opts('旅游天数分布', f'共 {len(days_data)} 个含天数信息产品'),
        xaxis_opts=opts.AxisOpts(
            axislabel_opts=base_axis_opts(),
            axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color=AXIS_LINE))
        ),
        yaxis_opts=opts.AxisOpts(
            name='数量', axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE))
        ),
        tooltip_opts=opts.TooltipOpts(trigger='axis', axis_pointer_type='shadow'),
        legend_opts=opts.LegendOpts(is_show=False),
    )
    return c


def chart_price_score_scatter(df):
    """价格 vs 评分散点图"""
    valid_price = df[df['price_num'].notna()]
    valid_score = valid_price[valid_price['score_num'].notna()].copy()
    scatter_df = valid_score[valid_score['price_num'] <= 20000]
    data = scatter_df[['price_num', 'score_num', 'title', 'sold_num']].values.tolist()
    scatter_data = [[row[0], row[1], row[3], row[2][:20]] for row in data]

    c = Scatter(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add_xaxis([d[0] for d in scatter_data])
    c.add_yaxis('',
                [d[1] for d in scatter_data],
                symbol_size=JsCode("""function(val){return Math.max(5, Math.min(30, Math.sqrt(val[2])*0.5))}"""),
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode("""new echarts.graphic.RadialGradient(0.5,0.5,0.5,[
                        {offset:0,color:'rgba(13,148,136,0.8)'},{offset:1,color:'rgba(103,232,249,0.3)'}
                    ])""")
                ),
                label_opts=opts.LabelOpts(is_show=False))
    c.set_global_opts(
        title_opts=base_title_opts('价格 vs 评分 关系图', '气泡大小代表销量'),
        xaxis_opts=opts.AxisOpts(
            name='价格 (元)', type_='value', axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE)),
            axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color=AXIS_LINE))
        ),
        yaxis_opts=opts.AxisOpts(
            name='评分', type_='value', min_=3.5, max_=5.1, axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE))
        ),
        tooltip_opts=opts.TooltipOpts(
            formatter=JsCode("""function(p){
                return '<b>'+p.data[3]+'</b><br/>价格: ¥'+p.data[0]+'<br/>评分: '+p.data[1]+'<br/>销量: '+p.data[2];
            }""")
        ),
        legend_opts=opts.LegendOpts(is_show=False),
    )
    return c


def chart_destination_top(df):
    """热门目的地 TOP20"""
    from collections import Counter
    all_dests = []
    for dests in df['destinations']:
        all_dests.extend(dests)
    dest_counts = Counter(all_dests).most_common(20)
    names = [d[0] for d in dest_counts][::-1]
    values = [d[1] for d in dest_counts][::-1]

    c = Bar(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add_xaxis(names)
    c.add_yaxis('出现次数', values,
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode("""new echarts.graphic.LinearGradient(1,0,0,0,[
                        {offset:0,color:'#99f6e4'},{offset:1,color:'#14b8a6'}
                    ])"""),
                    border_radius=[0, 4, 4, 0]
                ),
                label_opts=opts.LabelOpts(position='right', color=TEXT_COLOR, formatter='{c}'))
    c.reversal_axis()
    c.set_global_opts(
        title_opts=base_title_opts('热门目的地 TOP20', '基于产品标题关键词提取'),
        xaxis_opts=opts.AxisOpts(
            type_='value', axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE))
        ),
        yaxis_opts=opts.AxisOpts(
            type_='category', axislabel_opts=opts.LabelOpts(color=TEXT_COLOR),
            axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color=AXIS_LINE))
        ),
        tooltip_opts=opts.TooltipOpts(trigger='axis', axis_pointer_type='shadow'),
        legend_opts=opts.LegendOpts(is_show=False),
    )
    return c


def chart_price_type_box(df):
    """各产品类型价格箱线图"""
    valid_price = df[df['price_num'].notna()]
    box_df = valid_price[valid_price['price_num'] <= 20000].copy()
    types = box_df['product_type'].value_counts().index.tolist()[:8]
    box_data = []
    labels = []
    for t in types:
        prices = box_df[box_df['product_type'] == t]['price_num'].tolist()
        if len(prices) >= 5:
            prices_sorted = sorted(prices)
            n = len(prices_sorted)
            q1 = prices_sorted[int(n * 0.25)]
            q2 = prices_sorted[int(n * 0.5)]
            q3 = prices_sorted[int(n * 0.75)]
            iqr = q3 - q1
            low = max(prices_sorted[0], q1 - 1.5 * iqr)
            high = min(prices_sorted[-1], q3 + 1.5 * iqr)
            box_data.append([low, q1, q2, q3, high])
            labels.append(t)

    c = Boxplot(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add_xaxis(labels)
    c.add_yaxis('价格分布', box_data,
                itemstyle_opts=opts.ItemStyleOpts(color='#f0fdfa', border_color='#0d9488', border_width=2))
    c.set_global_opts(
        title_opts=base_title_opts('各产品类型价格分布箱线图'),
        xaxis_opts=opts.AxisOpts(
            axislabel_opts=base_axis_opts(),
            axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color=AXIS_LINE))
        ),
        yaxis_opts=opts.AxisOpts(
            name='价格 (元)', axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE))
        ),
        tooltip_opts=opts.TooltipOpts(trigger='item'),
        legend_opts=opts.LegendOpts(is_show=False),
    )
    return c


def chart_score_sold_relation(df):
    """评分区间与平均销量"""
    valid_score = df[df['score_num'].notna()]
    score_sold = valid_score[valid_score['sold_num'] > 0].copy()
    bins_ss = [0, 4.0, 4.5, 4.7, 4.8, 4.9, 5.01]
    labels_ss = ['<4.0', '4.0-4.5', '4.5-4.7', '4.7-4.8', '4.8-4.9', '5.0']
    score_sold['score_bin'] = pd.cut(score_sold['score_num'], bins=bins_ss, labels=labels_ss, right=False)
    grouped = score_sold.groupby('score_bin', observed=True).agg(
        avg_sold=('sold_num', 'mean'),
        median_sold=('sold_num', 'median'),
        count=('sold_num', 'count')
    ).reset_index()

    c = Bar(init_opts=opts.InitOpts(bg_color=BG_COLOR))
    c.add_xaxis(grouped['score_bin'].astype(str).tolist())
    c.add_yaxis('平均销量', grouped['avg_sold'].round(0).astype(int).tolist(),
                itemstyle_opts=opts.ItemStyleOpts(color='#0d9488'),
                label_opts=opts.LabelOpts(position='top', color=TEXT_COLOR, formatter='{c}'))
    c.add_yaxis('中位销量', grouped['median_sold'].round(0).astype(int).tolist(),
                itemstyle_opts=opts.ItemStyleOpts(color='#67e8f9'),
                label_opts=opts.LabelOpts(is_show=False))
    c.set_global_opts(
        title_opts=base_title_opts('评分区间 vs 销量对比'),
        xaxis_opts=opts.AxisOpts(
            name='评分区间', axislabel_opts=base_axis_opts(),
            axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color=AXIS_LINE))
        ),
        yaxis_opts=opts.AxisOpts(
            name='销量', axislabel_opts=base_axis_opts(),
            splitline_opts=opts.SplitLineOpts(linestyle_opts=opts.LineStyleOpts(color=SPLIT_LINE))
        ),
        tooltip_opts=opts.TooltipOpts(trigger='axis', axis_pointer_type='shadow'),
        legend_opts=opts.LegendOpts(
            pos_top='3%', pos_right='5%',
            textstyle_opts=opts.TextStyleOpts(color=TEXT_COLOR)
        ),
    )
    return c


# ────────────────────────────────────────────
# 5. 汇总统计卡片 (HTML)
# ────────────────────────────────────────────

def generate_stats_html(df):
    """生成概览统计卡片 HTML"""
    total = len(df)
    valid_price = df[df['price_num'].notna()]
    valid_score = df[df['score_num'].notna()]
    valid_sold = df[df['sold_num'] > 0]

    avg_price = valid_price['price_num'].mean()
    median_price = valid_price['price_num'].median()
    avg_score = valid_score['score_num'].mean()
    total_sold = valid_sold['sold_num'].sum()
    avg_sold = valid_sold['sold_num'].mean()
    max_sold_product = df.loc[df['sold_num'].idxmax()]
    type_counts = df['product_type'].value_counts()
    top_type = type_counts.index[0]

    cards = f'''
    <div style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;margin:20px auto;max-width:1400px;">
        <div style="background:#f0fdfa;border-radius:12px;padding:20px 28px;min-width:180px;text-align:center;border:1px solid #99f6e4;box-shadow:0 4px 16px rgba(13,148,136,0.08);">
            <div style="color:#0d9488;font-size:28px;font-weight:bold;">{total}</div>
            <div style="color:#64748b;font-size:13px;margin-top:4px;">产品总数</div>
        </div>
        <div style="background:#f0fdfa;border-radius:12px;padding:20px 28px;min-width:180px;text-align:center;border:1px solid #99f6e4;box-shadow:0 4px 16px rgba(13,148,136,0.08);">
            <div style="color:#14b8a6;font-size:28px;font-weight:bold;">¥{avg_price:,.0f}</div>
            <div style="color:#64748b;font-size:13px;margin-top:4px;">平均价格</div>
            <div style="color:#94a3b8;font-size:11px;">中位数 ¥{median_price:,.0f}</div>
        </div>
        <div style="background:#f0fdfa;border-radius:12px;padding:20px 28px;min-width:180px;text-align:center;border:1px solid #99f6e4;box-shadow:0 4px 16px rgba(13,148,136,0.08);">
            <div style="color:#0891b2;font-size:28px;font-weight:bold;">{avg_score:.2f}</div>
            <div style="color:#64748b;font-size:13px;margin-top:4px;">平均评分</div>
        </div>
        <div style="background:#f0fdfa;border-radius:12px;padding:20px 28px;min-width:180px;text-align:center;border:1px solid #99f6e4;box-shadow:0 4px 16px rgba(13,148,136,0.08);">
            <div style="color:#0f766e;font-size:28px;font-weight:bold;">{total_sold:,}</div>
            <div style="color:#64748b;font-size:13px;margin-top:4px;">总销量</div>
            <div style="color:#94a3b8;font-size:11px;">均销 {avg_sold:,.0f}</div>
        </div>
        <div style="background:#f0fdfa;border-radius:12px;padding:20px 28px;min-width:180px;text-align:center;border:1px solid #99f6e4;box-shadow:0 4px 16px rgba(13,148,136,0.08);">
            <div style="color:#06b6d4;font-size:18px;font-weight:bold;margin-top:6px;">{max_sold_product["title"][:12]}...</div>
            <div style="color:#64748b;font-size:13px;margin-top:4px;">销量冠军</div>
            <div style="color:#94a3b8;font-size:11px;">{max_sold_product["sold_num"]:,} 份</div>
        </div>
        <div style="background:#f0fdfa;border-radius:12px;padding:20px 28px;min-width:180px;text-align:center;border:1px solid #99f6e4;box-shadow:0 4px 16px rgba(13,148,136,0.08);">
            <div style="color:#0d9488;font-size:28px;font-weight:bold;">{top_type}</div>
            <div style="color:#64748b;font-size:13px;margin-top:4px;">最多类型</div>
            <div style="color:#94a3b8;font-size:11px;">{type_counts.iloc[0]} 个产品</div>
        </div>
    </div>
    '''
    return cards


# ────────────────────────────────────────────
# 6. 生成完整 HTML 仪表盘
# ────────────────────────────────────────────

# 全局变量，供 generate_dashboard 使用筛选信息
args_used = None


def generate_dashboard(df):
    """组装所有图表到单个 HTML 文件"""
    print("[INFO] 正在生成图表...")

    valid_price = df[df['price_num'].notna()]
    valid_score = df[df['score_num'].notna()]
    valid_sold = df[df['sold_num'] > 0]
    print(f"[INFO] 有效数据 - 价格: {len(valid_price)}, 评分: {len(valid_score)}, 有销量: {len(valid_sold)}")

    charts = {
        'price_dist': chart_price_distribution(df),
        'score_dist': chart_score_distribution(df),
        'top_sold': chart_top_sold(df),
        'top_commented': chart_top_commented(df),
        'product_type': chart_product_type(df),
        'days_dist': chart_days_distribution(df),
        'price_score': chart_price_score_scatter(df),
        'dest_top': chart_destination_top(df),
        'price_box': chart_price_type_box(df),
        'score_sold': chart_score_sold_relation(df),
    }

    print("[INFO] 正在组装 HTML 页面...")

    html_template = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>携程旅游产品数据可视化仪表盘</title>
    <script src="https://assets.pyecharts.org/assets/v5/echarts.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #f8fafb;
            font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            color: #1e293b;
            min-height: 100vh;
        }
        .header {
            text-align: center;
            padding: 30px 20px 10px;
            background: linear-gradient(180deg, #f0fdfa 0%, #f8fafb 100%);
        }
        .header h1 {
            font-size: 32px;
            background: linear-gradient(90deg, #0d9488, #14b8a6, #06b6d4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: 2px;
        }
        .header p { color: #64748b; font-size: 14px; margin-top: 8px; }
        .filter-info {
            text-align: center; padding: 8px; color: #0d9488; font-size: 13px; font-weight: 500;
        }
        .stats-section { margin: 10px 0; }
        .chart-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
            max-width: 1500px; margin: 20px auto; padding: 0 20px;
        }
        .chart-card {
            background: #ffffff; border-radius: 12px; padding: 12px;
            border: 1px solid #e2e8f0; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .chart-card:hover {
            transform: translateY(-2px); box-shadow: 0 8px 24px rgba(13,148,136,0.1);
            border-color: #99f6e4;
        }
        .chart-card.full-width { grid-column: 1 / -1; }
        .chart-container { width: 100%; height: 420px; }
        .chart-container.tall { height: 520px; }
        .footer {
            text-align: center; padding: 30px; color: #94a3b8; font-size: 12px;
            border-top: 1px solid #e2e8f0; margin-top: 30px;
        }
        @media (max-width: 900px) { .chart-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>携程旅游产品数据可视化仪表盘</h1>
        <p>数据来源: MySQL (TOTAL_DB) · 共 TOTAL_COUNT 个旅游产品 · 查询时间: QUERY_TIME</p>
    </div>
    FILTER_INFO
    <div class="stats-section">STATS_CARDS</div>
    <div class="chart-grid">
        <div class="chart-card"><div id="chart_price_dist" class="chart-container"></div></div>
        <div class="chart-card"><div id="chart_score_dist" class="chart-container"></div></div>
        <div class="chart-card full-width"><div id="chart_top_sold" class="chart-container tall"></div></div>
        <div class="chart-card full-width"><div id="chart_top_commented" class="chart-container tall"></div></div>
        <div class="chart-card"><div id="chart_product_type" class="chart-container"></div></div>
        <div class="chart-card"><div id="chart_days_dist" class="chart-container"></div></div>
        <div class="chart-card full-width"><div id="chart_price_score" class="chart-container tall"></div></div>
        <div class="chart-card full-width"><div id="chart_dest_top" class="chart-container tall"></div></div>
        <div class="chart-card"><div id="chart_price_box" class="chart-container"></div></div>
        <div class="chart-card"><div id="chart_score_sold" class="chart-container"></div></div>
    </div>
    <div class="footer">
        携程旅游产品数据可视化
    </div>
    <script>CHARTS_JS</script>
</body>
</html>'''

    chart_configs = [
        ('chart_price_dist', charts['price_dist']),
        ('chart_score_dist', charts['score_dist']),
        ('chart_top_sold', charts['top_sold']),
        ('chart_top_commented', charts['top_commented']),
        ('chart_product_type', charts['product_type']),
        ('chart_days_dist', charts['days_dist']),
        ('chart_price_score', charts['price_score']),
        ('chart_dest_top', charts['dest_top']),
        ('chart_price_box', charts['price_box']),
        ('chart_score_sold', charts['score_sold']),
    ]

    js_codes = []
    for dom_id, chart in chart_configs:
        option_json = chart.dump_options()
        js_codes.append(f'''
        (function() {{
            var chart = echarts.init(document.getElementById('{dom_id}'), null, {{renderer: 'canvas'}});
            var option = {option_json};
            chart.setOption(option);
            window.addEventListener('resize', function() {{ chart.resize(); }});
        }})();
        ''')

    from datetime import datetime
    query_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 构建筛选信息
    filter_parts = []
    if args_used.min_price: filter_parts.append(f'价格>={args_used.min_price}')
    if args_used.max_price: filter_parts.append(f'价格<={args_used.max_price}')
    if args_used.min_score: filter_parts.append(f'评分>={args_used.min_score}')
    if args_used.max_score: filter_parts.append(f'评分<={args_used.max_score}')
    if args_used.min_sold: filter_parts.append(f'销量>={args_used.min_sold}')
    if args_used.keyword: filter_parts.append(f'关键词: {args_used.keyword}')
    if args_used.type: filter_parts.append(f'类型: {args_used.type}')
    if args_used.days: filter_parts.append(f'天数: {args_used.days}')
    if args_used.limit: filter_parts.append(f'限制{args_used.limit}条')

    filter_html = ''
    if filter_parts:
        filter_html = f'<div class="filter-info">筛选条件: {" | ".join(filter_parts)}</div>'

    final_html = html_template
    final_html = final_html.replace('TOTAL_DB', args_used.database)
    final_html = final_html.replace('TOTAL_COUNT', str(len(df)))
    final_html = final_html.replace('QUERY_TIME', query_time)
    final_html = final_html.replace('FILTER_INFO', filter_html)
    final_html = final_html.replace('STATS_CARDS', generate_stats_html(df))
    final_html = final_html.replace('CHARTS_JS', '\n'.join(js_codes))

    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, 'ctrip_dashboard.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_html)

    print(f"[SUCCESS] 仪表盘已生成: {output_path}")
    return output_path


# ────────────────────────────────────────────
# 7. 主入口
# ────────────────────────────────────────────

if __name__ == '__main__':
    args = parse_args()
    args_used = args

    # 交互查询模式
    if args.query:
        interactive_query(args)
        sys.exit(0)

    # 正常仪表盘模式
    print("=" * 50)
    print("  携程旅游产品数据可视化仪表盘")
    print("=" * 50)

    df = load_data_from_db(args)

    if len(df) == 0:
        print("[WARN] 查询结果为空，请检查筛选条件。")
        sys.exit(1)

    df = clean_data(df)
    output = generate_dashboard(df)
    print(f"\n[完成] 请在浏览器中打开: {output}")
