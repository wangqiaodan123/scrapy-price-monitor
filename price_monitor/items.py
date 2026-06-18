"""
Scrapy Items 定义
定义商品数据和价格历史数据的结构化模型
"""

import scrapy
from scrapy import Field


class ProductItem(scrapy.Item):
    """
    商品数据模型
    存储从各电商平台采集的商品基本信息
    """
    # 商品基本信息
    product_id = Field()          # 商品 ID (平台唯一标识)
    name = Field()                # 商品名称
    price = Field()               # 当前价格 (清洗后的浮点数)
    original_price = Field()      # 原始价格 (划线价)
    discount = Field()            # 折扣信息
    shop = Field()                # 店铺名称
    platform = Field()            # 来源平台 (jd/taobao/suning)
    url = Field()                 # 商品详情页链接
    image_url = Field()           # 商品主图链接
    category = Field()            # 商品分类
    keyword = Field()             # 搜索关键词

    # 统计信息
    reviews_count = Field()       # 评论数
    sales_count = Field()         # 销量
    rating = Field()              # 评分

    # 元数据
    crawl_time = Field()          # 采集时间 (ISO 8601 格式)
    update_time = Field()         # 更新时间

    def __repr__(self):
        """简洁的输出格式用于调试"""
        return f"<ProductItem: {self.get('name', 'N/A')[:30]}... ¥{self.get('price', 'N/A')}>"


class PriceHistoryItem(scrapy.Item):
    """
    价格历史记录模型
    追踪商品价格变化，用于趋势分析
    """
    # 商品标识
    product_id = Field()          # 商品 ID
    platform = Field()            # 来源平台
    name = Field()                # 商品名称

    # 价格信息
    price = Field()               # 当前价格
    original_price = Field()      # 原始价格
    discount = Field()            # 折扣信息

    # 时间戳
    record_time = Field()         # 记录时间 (ISO 8601 格式)

    # 价格变化
    price_change = Field()        # 价格变化金额 (相对上一次记录)
    price_change_pct = Field()    # 价格变化百分比

    def __repr__(self):
        """简洁的输出格式用于调试"""
        return (
            f"<PriceHistoryItem: {self.get('name', 'N/A')[:20]}... "
            f"¥{self.get('price', 'N/A')} ({self.get('record_time', 'N/A')})>"
        )
