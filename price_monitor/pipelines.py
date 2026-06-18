"""
数据处理管道
实现数据清洗、去重过滤、多存储后端 (MySQL/MongoDB/CSV)
"""

import csv
import re
import os
import logging
from datetime import datetime
from scrapy.exceptions import DropItem
from itemadapter import ItemAdapter

logger = logging.getLogger(__name__)


class DataCleanPipeline:
    """
    数据清洗管道
    清洗价格字段、规范化数据格式、补全缺失字段
    """

    def __init__(self):
        self.price_pattern = re.compile(r'[\d,]+\.?\d*')

    def open_spider(self, spider):
        logger.info("数据清洗管道已启用")

    def process_item(self, item, spider):
        """清洗和规范化商品数据"""
        adapter = ItemAdapter(item)

        # 清洗价格字段
        price = adapter.get('price')
        if price:
            cleaned_price = self._clean_price(price)
            adapter['price'] = cleaned_price

        # 清洗原价
        original_price = adapter.get('original_price')
        if original_price:
            adapter['original_price'] = self._clean_price(original_price)

        # 计算折扣率
        if adapter.get('price') and adapter.get('original_price'):
            try:
                price = float(adapter['price'])
                original = float(adapter['original_price'])
                if original > 0 and original > price:
                    discount = round((price / original) * 10, 1)
                    adapter['discount'] = f"{discount}折"
            except (ValueError, TypeError):
                pass

        # 清洗商品名称 (去除多余空白)
        name = adapter.get('name')
        if name:
            adapter['name'] = re.sub(r'\s+', ' ', name).strip()

        # 清洗评论数
        reviews_count = adapter.get('reviews_count')
        if reviews_count:
            adapter['reviews_count'] = self._clean_number(reviews_count)

        # 清洗销量
        sales_count = adapter.get('sales_count')
        if sales_count:
            adapter['sales_count'] = self._clean_number(sales_count)

        # 添加采集时间
        if not adapter.get('crawl_time'):
            adapter['crawl_time'] = datetime.now().isoformat()

        # 添加更新时间
        adapter['update_time'] = datetime.now().isoformat()

        spider.logger.debug(f"数据清洗完成: {adapter.get('name', '')[:30]}...")
        return item

    def _clean_price(self, price_str):
        """清洗价格字段，提取数字部分"""
        if isinstance(price_str, (int, float)):
            return str(price_str)

        if not isinstance(price_str, str):
            return None

        # 移除货币符号和逗号
        price_str = price_str.replace('¥', '').replace('￥', '').replace(',', '').strip()

        # 提取数字
        match = self.price_pattern.search(price_str)
        if match:
            return match.group()

        return None

    def _clean_number(self, num_str):
        """清洗数字字段 (评论数、销量等)"""
        if isinstance(num_str, (int, float)):
            return int(num_str)

        if not isinstance(num_str, str):
            return 0

        # 处理 "10万+"、"1.5万" 等格式
        num_str = num_str.strip()

        if '万' in num_str:
            num_str = num_str.replace('万+', '').replace('万', '')
            try:
                return int(float(num_str) * 10000)
            except ValueError:
                return 0

        if '+' in num_str:
            num_str = num_str.replace('+', '')

        # 提取数字
        match = re.search(r'\d+', num_str)
        if match:
            return int(match.group())

        return 0


class DuplicateFilterPipeline:
    """
    去重过滤管道
    基于商品 ID 和平台过滤重复商品
    """

    def __init__(self):
        self.seen_products = set()

    def open_spider(self, spider):
        logger.info("去重过滤管道已启用")
        self.seen_products.clear()

    def process_item(self, item, spider):
        """过滤重复商品"""
        adapter = ItemAdapter(item)

        # 生成唯一标识
        product_id = adapter.get('product_id')
        platform = adapter.get('platform')

        if not product_id or not platform:
            # 如果没有商品 ID，使用名称和平台组合作为标识
            name = adapter.get('name', '')
            product_id = f"{platform}_{name}"

        unique_key = f"{platform}_{product_id}"

        if unique_key in self.seen_products:
            spider.logger.debug(f"过滤重复商品: {adapter.get('name', '')[:30]}...")
            raise DropItem(f"重复商品: {unique_key}")

        self.seen_products.add(unique_key)
        return item


class MySQLPipeline:
    """
    MySQL 存储管道
    批量插入商品数据到 MySQL 数据库
    """

    def __init__(self, mysql_config):
        self.mysql_config = mysql_config
        self.connection = None
        self.cursor = None
        self.batch_size = 100
        self.items_buffer = []

    @classmethod
    def from_crawler(cls, crawler):
        from price_monitor.settings import CONFIG
        mysql_config = CONFIG.get('database', {}).get('mysql', {})

        if not mysql_config.get('host'):
            raise ValueError("MySQL 配置缺失")

        return cls(mysql_config)

    def open_spider(self, spider):
        """建立数据库连接"""
        try:
            import pymysql

            self.connection = pymysql.connect(
                host=self.mysql_config['host'],
                port=self.mysql_config.get('port', 3306),
                user=self.mysql_config['user'],
                password=self.mysql_config['password'],
                database=self.mysql_config['database'],
                charset=self.mysql_config.get('charset', 'utf8mb4'),
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.connection.cursor()
            logger.info("MySQL 连接成功")
        except Exception as e:
            logger.error(f"MySQL 连接失败: {e}")
            raise

    def close_spider(self, spider):
        """关闭数据库连接"""
        # 处理剩余缓冲数据
        if self.items_buffer:
            self._batch_insert()

        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

        logger.info("MySQL 连接已关闭")

    def process_item(self, item, spider):
        """处理商品数据"""
        adapter = ItemAdapter(item)

        # 只处理 ProductItem
        if 'crawl_time' in adapter.asdict():
            self.items_buffer.append(adapter.asdict())

            # 达到批量大小时执行插入
            if len(self.items_buffer) >= self.batch_size:
                self._batch_insert()

        return item

    def _batch_insert(self):
        """批量插入数据"""
        if not self.items_buffer:
            return

        try:
            # SQL 插入语句 (使用 INSERT ... ON DUPLICATE KEY UPDATE)
            sql = """
                INSERT INTO products (
                    product_id, name, price, original_price, discount,
                    shop, platform, url, image_url, category, keyword,
                    reviews_count, sales_count, rating, crawl_time, update_time
                ) VALUES (
                    %(product_id)s, %(name)s, %(price)s, %(original_price)s, %(discount)s,
                    %(shop)s, %(platform)s, %(url)s, %(image_url)s, %(category)s, %(keyword)s,
                    %(reviews_count)s, %(sales_count)s, %(rating)s, %(crawl_time)s, %(update_time)s
                )
                ON DUPLICATE KEY UPDATE
                    price = VALUES(price),
                    original_price = VALUES(original_price),
                    discount = VALUES(discount),
                    reviews_count = VALUES(reviews_count),
                    sales_count = VALUES(sales_count),
                    update_time = VALUES(update_time)
            """

            self.cursor.executemany(sql, self.items_buffer)
            self.connection.commit()

            logger.info(f"MySQL 批量插入成功: {len(self.items_buffer)} 条记录")
            self.items_buffer.clear()

        except Exception as e:
            logger.error(f"MySQL 批量插入失败: {e}")
            self.connection.rollback()
            self.items_buffer.clear()


class MongoDBPipeline:
    """
    MongoDB 存储管道
    存储商品数据和价格历史记录
    """

    def __init__(self, mongo_config):
        self.mongo_config = mongo_config
        self.client = None
        self.db = None
        self.collection_products = None
        self.collection_history = None

    @classmethod
    def from_crawler(cls, crawler):
        from price_monitor.settings import CONFIG
        mongo_config = CONFIG.get('database', {}).get('mongodb', {})

        if not mongo_config.get('uri'):
            raise ValueError("MongoDB 配置缺失")

        return cls(mongo_config)

    def open_spider(self, spider):
        """建立 MongoDB 连接"""
        try:
            import pymongo

            self.client = pymongo.MongoClient(self.mongo_config['uri'])
            self.db = self.client[self.mongo_config['database']]

            # 商品集合
            products_collection = self.mongo_config.get('collection_products', 'products')
            self.collection_products = self.db[products_collection]

            # 价格历史集合
            history_collection = self.mongo_config.get('collection_history', 'price_history')
            self.collection_history = self.db[history_collection]

            # 创建索引
            self.collection_products.create_index([('product_id', 1), ('platform', 1)], unique=True)
            self.collection_history.create_index([('product_id', 1), ('record_time', -1)])

            logger.info("MongoDB 连接成功")
        except Exception as e:
            logger.error(f"MongoDB 连接失败: {e}")
            raise

    def close_spider(self, spider):
        """关闭 MongoDB 连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB 连接已关闭")

    def process_item(self, item, spider):
        """处理商品数据"""
        adapter = ItemAdapter(item)
        data = adapter.asdict()

        try:
            # 插入或更新商品数据
            if 'crawl_time' in data:
                filter_query = {
                    'product_id': data.get('product_id'),
                    'platform': data.get('platform')
                }
                self.collection_products.update_one(
                    filter_query,
                    {'$set': data},
                    upsert=True
                )

                # 记录价格历史
                self._record_price_history(data)

        except Exception as e:
            logger.error(f"MongoDB 插入失败: {e}")

        return item

    def _record_price_history(self, product_data):
        """记录价格历史"""
        try:
            # 查询上一次价格记录
            last_record = self.collection_history.find_one(
                {
                    'product_id': product_data.get('product_id'),
                    'platform': product_data.get('platform')
                },
                sort=[('record_time', -1)]
            )

            # 构建历史记录
            history = {
                'product_id': product_data.get('product_id'),
                'platform': product_data.get('platform'),
                'name': product_data.get('name'),
                'price': product_data.get('price'),
                'original_price': product_data.get('original_price'),
                'discount': product_data.get('discount'),
                'record_time': datetime.now().isoformat(),
            }

            # 计算价格变化
            if last_record and last_record.get('price'):
                try:
                    old_price = float(last_record['price'])
                    new_price = float(product_data.get('price', 0))
                    price_change = new_price - old_price
                    price_change_pct = (price_change / old_price) * 100 if old_price > 0 else 0

                    history['price_change'] = price_change
                    history['price_change_pct'] = round(price_change_pct, 2)
                except (ValueError, TypeError):
                    history['price_change'] = 0
                    history['price_change_pct'] = 0

            self.collection_history.insert_one(history)

        except Exception as e:
            logger.error(f"记录价格历史失败: {e}")


class CSVPipeline:
    """
    CSV 导出管道
    将商品数据导出为 CSV 文件用于分析
    """

    def __init__(self, output_dir='./data/csv'):
        self.output_dir = output_dir
        self.file = None
        self.writer = None
        self.fieldnames = [
            'product_id', 'name', 'price', 'original_price', 'discount',
            'shop', 'platform', 'url', 'category', 'keyword',
            'reviews_count', 'sales_count', 'crawl_time'
        ]

    @classmethod
    def from_crawler(cls, crawler):
        from price_monitor.settings import CONFIG
        output_dir = CONFIG.get('storage', {}).get('csv_output_dir', './data/csv')
        return cls(output_dir)

    def open_spider(self, spider):
        """创建 CSV 文件"""
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

        # 生成文件名 (带时间戳)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(self.output_dir, f'products_{timestamp}.csv')

        self.file = open(filename, 'w', newline='', encoding='utf-8-sig')
        self.writer = csv.DictWriter(self.file, fieldnames=self.fieldnames, extrasaction='ignore')
        self.writer.writeheader()

        logger.info(f"CSV 文件已创建: {filename}")

    def close_spider(self, spider):
        """关闭 CSV 文件"""
        if self.file:
            self.file.close()
            logger.info("CSV 文件已关闭")

    def process_item(self, item, spider):
        """写入 CSV"""
        adapter = ItemAdapter(item)
        data = adapter.asdict()

        # 只写入包含必要字段的数据
        if 'crawl_time' in data:
            self.writer.writerow(data)

        return item
