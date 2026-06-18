"""
京东商品爬虫
使用 CrawlSpider 采集京东搜索结果页商品数据
"""

import scrapy
import re
import json
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy.http import Request
from price_monitor.items import ProductItem


class JDSpider(CrawlSpider):
    """
    京东商品搜索爬虫
    支持关键词搜索、分页处理、商品详情解析
    """
    name = 'jd'
    allowed_domains = ['jd.com', 'search.jd.com']

    # 默认搜索关键词
    default_keyword = '手机'
    # 每页商品数
    page_size = 30

    def __init__(self, keyword=None, max_pages=10, *args, **kwargs):
        super(JDSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword or self.default_keyword
        self.max_pages = int(max_pages)
        self.current_page = 1

    def start_requests(self):
        """生成起始请求"""
        # 京东搜索 URL 格式
        url = f'https://search.jd.com/Search?keyword={self.keyword}&enc=utf-8'
        self.logger.info(f"开始采集京东商品，关键词: {self.keyword}")
        yield Request(url, callback=self.parse_search_results, meta={'page': 1})

    def parse_search_results(self, response):
        """解析搜索结果页"""
        current_page = response.meta.get('page', 1)
        self.logger.info(f"解析京东搜索结果第 {current_page} 页")

        # 提取商品列表
        product_list = response.xpath('//li[@class="gl-item"]')

        if not product_list:
            self.logger.warning(f"第 {current_page} 页未找到商品，可能触发了反爬")
            return

        for product in product_list:
            item = ProductItem()

            # 商品 ID
            sku_id = product.xpath('.//div[@class="gl-i-wrap"]/@data-sku').get()
            item['product_id'] = sku_id

            # 商品名称
            name = product.xpath('.//div[@class="p-name"]/a/em/text()').get()
            if not name:
                name = product.xpath('.//div[@class="p-name"]/a/@title').get()
            item['name'] = name

            # 价格 (京东价格通过 JS 动态加载，这里获取占位符)
            price = product.xpath('.//div[@class="p-price"]/strong/i/text()').get()
            item['price'] = price

            # 店铺名称
            shop = product.xpath('.//div[@class="p-shop"]/span/a/text()').get()
            item['shop'] = shop

            # 商品链接
            url = product.xpath('.//div[@class="p-name"]/a/@href').get()
            if url:
                if not url.startswith('http'):
                    url = 'https:' + url
                item['url'] = url

            # 商品图片
            image_url = product.xpath('.//div[@class="p-img"]/a/img/@data-lazy-img').get()
            if not image_url:
                image_url = product.xpath('.//div[@class="p-img"]/a/img/@src').get()
            if image_url and not image_url.startswith('http'):
                image_url = 'https:' + image_url
            item['image_url'] = image_url

            # 评论数
            comments = product.xpath('.//div[@class="p-commit"]/strong/a/text()').get()
            item['reviews_count'] = comments

            # 设置平台信息
            item['platform'] = 'jd'
            item['keyword'] = self.keyword

            # 如果有商品 ID，请求价格 API
            if sku_id:
                yield Request(
                    url=f'https://p.3.cn/prices/mgets?skuIds=J_{sku_id}',
                    callback=self.parse_price,
                    meta={'item': item}
                )
            else:
                yield item

        # 处理分页
        if current_page < self.max_pages:
            next_page = current_page + 1
            # 京东分页参数: page=2*s-1 (s 为页码)
            page_param = next_page * 2 - 1
            next_url = f'https://search.jd.com/Search?keyword={self.keyword}&enc=utf-8&page={page_param}'
            yield Request(
                next_url,
                callback=self.parse_search_results,
                meta={'page': next_page}
            )

    def parse_price(self, response):
        """解析价格 API 响应"""
        item = response.meta['item']

        try:
            # 价格 API 返回 JSON 数组
            data = json.loads(response.text)
            if data and len(data) > 0:
                price_info = data[0]
                item['price'] = price_info.get('p')  # 当前价格
                item['original_price'] = price_info.get('m')  # 原价
                item['discount'] = price_info.get('op')  # 折扣价
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            self.logger.warning(f"解析价格失败: {e}")

        yield item

    def parse_product_detail(self, response):
        """
        解析商品详情页 (可选，用于获取更多信息)
        通过 CrawlSpider Rule 自动触发
        """
        item = response.meta.get('item')
        if not item:
            return

        # 提取商品分类
        category = response.xpath('//div[@class="crumb-wrap"]/div/a/text()').getall()
        if category:
            item['category'] = ' > '.join(category)

        # 提取评分
        rating = response.xpath('//span[@class="percent-con"]/text()').get()
        if rating:
            item['rating'] = rating.replace('%', '')

        yield item
