"""
苏宁商品爬虫
使用 API 接口采集商品数据，避免页面解析
"""

import scrapy
import json
import re
from scrapy import Request
from price_monitor.items import ProductItem


class SuningSpider(scrapy.Spider):
    """
    苏宁商品搜索爬虫
    通过苏宁内部 API 获取商品数据，效率更高
    """
    name = 'suning'
    allowed_domains = ['suning.com', 'search.suning.com']

    # 默认配置
    default_keyword = '手机'

    # 苏宁搜索 API
    search_api = 'https://search.suning.com/emall/search/ajaxSearchProduct.do'
    # 苏宁价格 API
    price_api = 'https://p.suning.com/webapp/wcs/stores/prices/product/getPriceById'

    def __init__(self, keyword=None, max_pages=10, *args, **kwargs):
        super(SuningSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword or self.default_keyword
        self.max_pages = int(max_pages)

    def start_requests(self):
        """生成起始请求"""
        url = self._build_search_url(page=1)
        self.logger.info(f"开始采集苏宁商品，关键词: {self.keyword}")
        yield Request(url, callback=self.parse_search_results, meta={'page': 1})

    def _build_search_url(self, page=1):
        """构建搜索 API URL"""
        # 苏宁分页参数
        cp = f'1-{page}-30'  # 页码-每页数量

        params = {
            'keyword': self.keyword,
            'cityId': '025',  # 默认城市: 南京
            'storeId': '10052',
            'catId': '',
            'currentPage': str(page),
            'pageSize': '30',
            'saleChannel': '0',
            'sn': '0',
            'sc': '0',
        }

        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        return f'{self.search_api}?{query_string}'

    def parse_search_results(self, response):
        """解析搜索结果"""
        current_page = response.meta.get('page', 1)
        self.logger.info(f"解析苏宁搜索结果第 {current_page} 页")

        try:
            # 尝试解析 JSON
            data = json.loads(response.text)
        except json.JSONDecodeError:
            # 如果不是 JSON，可能是 HTML 响应，尝试提取 JSONP
            json_match = re.search(r'jsonpCallback\w*\((.*)\)', response.text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    self.logger.error(f"无法解析响应数据: {response.text[:200]}")
                    return
            else:
                self.logger.error(f"无法解析响应数据")
                return

        # 提取商品列表
        products = data.get('data', {}).get('products', [])

        if not products:
            # 尝试其他数据结构
            products = data.get('productList', [])

        if not products:
            self.logger.warning(f"第 {current_page} 页未找到商品")
            return

        for product in products:
            item = ProductItem()

            # 商品 ID
            item['product_id'] = product.get('productId') or product.get('id')

            # 商品名称
            item['name'] = product.get('title') or product.get('name')

            # 价格 (可能需要从价格 API 获取)
            price = product.get('price') or product.get('showPrice')
            item['price'] = price

            # 原价
            item['original_price'] = product.get('originPrice') or product.get('marketPrice')

            # 店铺名称
            item['shop'] = product.get('shopName') or product.get('vendorName')

            # 商品链接
            product_url = product.get('url') or product.get('productUrl')
            if product_url:
                if not product_url.startswith('http'):
                    product_url = 'https:' + product_url
                item['url'] = product_url

            # 商品图片
            image_url = product.get('image') or product.get('imgUrl') or product.get('picUrl')
            if image_url:
                if not image_url.startswith('http'):
                    image_url = 'https:' + image_url
                item['image_url'] = image_url

            # 分类
            item['category'] = product.get('categoryName')

            # 评论数
            item['reviews_count'] = product.get('commentCount') or product.get('reviewCount')

            # 设置平台信息
            item['platform'] = 'suning'
            item['keyword'] = self.keyword

            # 请求价格 API 获取最新价格
            if item.get('product_id'):
                price_url = self._build_price_url(item['product_id'])
                yield Request(
                    price_url,
                    callback=self.parse_price,
                    meta={'item': item}
                )
            else:
                yield item

        # 处理分页
        if current_page < self.max_pages and len(products) > 0:
            next_page = current_page + 1
            next_url = self._build_search_url(page=next_page)
            yield Request(
                next_url,
                callback=self.parse_search_results,
                meta={'page': next_page}
            )

    def _build_price_url(self, product_id):
        """构建价格 API URL"""
        params = {
            'productId': product_id,
            'cityId': '025',
        }
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        return f'{self.price_api}?{query_string}'

    def parse_price(self, response):
        """解析价格 API 响应"""
        item = response.meta['item']

        try:
            data = json.loads(response.text)

            # 提取价格信息
            if 'price' in data:
                price_info = data['price']
                item['price'] = price_info.get('promotionPrice') or price_info.get('price')
                item['original_price'] = price_info.get('originPrice') or price_info.get('marketPrice')

                # 折扣信息
                if price_info.get('discount'):
                    item['discount'] = price_info['discount']

            # 苏宁价格数据结构可能不同
            elif 'promotionPrice' in data:
                item['price'] = data['promotionPrice']
                item['original_price'] = data.get('originPrice')

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning(f"解析价格失败: {e}")

        yield item

    def parse_product_detail(self, response):
        """
        解析商品详情页 (可选)
        用于获取更详细的商品信息
        """
        item = response.meta.get('item')
        if not item:
            return

        try:
            # 从页面中提取结构化数据
            json_ld = response.xpath('//script[@type="application/ld+json"]/text()').get()
            if json_ld:
                data = json.loads(json_ld)
                item['rating'] = data.get('aggregateRating', {}).get('ratingValue')
                item['reviews_count'] = data.get('aggregateRating', {}).get('reviewCount')

        except (json.JSONDecodeError, AttributeError) as e:
            self.logger.debug(f"解析商品详情失败: {e}")

        yield item
