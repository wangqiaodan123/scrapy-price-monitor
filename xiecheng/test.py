import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re

# ================== 1. 设置中文字体（解决中文乱码） ==================
# Windows 一般用 SimHei 或 Microsoft YaHei
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False   # 解决负号显示为方块的问题

# ================== 2. 读取数据（请修改为你的实际路径） ==================
# 使用原始字符串（r''）避免转义符警告
df = pd.read_csv(r'D:\mianshi\可视化\ctrip_travel_products_raw.csv')

# ================== 3. 数据清洗 ==================

# 3.1 解析销量字段（统一转为数值）
def parse_sold(s):
    if pd.isna(s):
        return None
    s = str(s).replace('已售', '').replace('月销', '').replace('+份', '').replace('份', '').strip()
    if 'K' in s:
        s = s.replace('K', '')
        try:
            return float(s) * 1000
        except:
            return None
    try:
        return float(s)
    except:
        return None

df['sold_num'] = df['sold_count'].apply(parse_sold)

# 3.2 提取目的地（简单提取，取标题中第一个地名，可根据需求优化）
# 这里用正则匹配：标题开头到第一个数字或“日”之前的内容
df['destination'] = df['title'].str.extract(r'^(.*?)[0-9日]', expand=False).str.strip()

# 3.3 提取产品类型（根据关键词匹配）
type_keywords = {
    '拼小团': '拼小团',
    '私家团': '私家团',
    '跟团游': '跟团游',
    '自由行': '自由行',
    '一日游': '一日游',
    '亲子营': '亲子营'
}
def extract_type(title):
    if pd.isna(title):
        return '其他'
    for k, v in type_keywords.items():
        if k in str(title):
            return v
    return '其他'
df['product_type'] = df['title'].apply(extract_type)

# ================== 4. 绘制可视化图表 ==================
plt.figure(figsize=(16, 10))   # 增大画布，避免布局拥挤

# 4.1 价格分布直方图
plt.subplot(2, 3, 1)
df['price'].dropna().hist(bins=50, color='skyblue', edgecolor='black')
plt.title('价格分布')
plt.xlabel('价格（元）')
plt.ylabel('频数')

# 4.2 评分分布柱状图
plt.subplot(2, 3, 2)
score_counts = df['score'].value_counts().sort_index()
score_counts.plot(kind='bar', color='lightgreen')
plt.title('评分分布')
plt.xlabel('评分')
plt.ylabel('产品数量')

# 4.3 销量 Top10 产品（去掉 palette，使用默认颜色）
plt.subplot(2, 3, 3)
top_sold = df.nlargest(10, 'sold_num')
sns.barplot(x='sold_num', y='title', data=top_sold)
plt.title('销量 Top10 产品')
plt.xlabel('销量')
plt.ylabel('产品名称')

# 4.4 目的地产品数量 Top15（同样去掉 palette）
plt.subplot(2, 3, 4)
dest_counts = df['destination'].value_counts().head(15)
sns.barplot(x=dest_counts.values, y=dest_counts.index)
plt.title('目的地产品数量 Top15')
plt.xlabel('产品数')
plt.ylabel('目的地')

# 4.5 价格 vs 评分散点图
plt.subplot(2, 3, 5)
sns.scatterplot(data=df, x='price', y='score', alpha=0.3, color='coral')
plt.title('价格 vs 评分')
plt.xlabel('价格（元）')
plt.ylabel('评分')

# 4.6 产品类型占比饼图
plt.subplot(2, 3, 6)
type_counts = df['product_type'].value_counts()
type_counts.plot(kind='pie', autopct='%1.1f%%', startangle=90)
plt.title('产品类型分布')
plt.ylabel('')   # 去掉默认的 'product_type' 标签

# 调整布局并保存
plt.tight_layout()
plt.savefig('travel_analysis.png', dpi=300)
plt.show()

print("图表已保存为 travel_analysis.png")