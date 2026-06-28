import pandas as pd
from scrapy import signals
# pipelines.py
import pymysql
from twisted.enterprise import adbapi
from scrapy.exceptions import NotConfigured
from . import settings


class MySQLAsyncPipeline:
    """
    使用 Twisted 异步连接池写入 MySQL，不阻塞爬虫
    """

    def open_spider(self, spider):
        """爬虫启动时创建数据库连接池"""
        # 从 settings 读取配置
        db_settings = {
            'host': settings.MYSQL_HOST,
            'user': settings.MYSQL_USER,
            'password': settings.MYSQL_PASSWORD,
            'database': settings.MYSQL_DBNAME,
            'charset': settings.MYSQL_CHARSET,
            'cursorclass': pymysql.cursors.DictCursor,  # 可选，便于调试
            'use_unicode': True,
        }
        # 创建连接池
        self.dbpool = adbapi.ConnectionPool('pymysql', **db_settings)
        print("连接池成功.")

    def close_spider(self, spider):
        """爬虫关闭时释放连接池"""
        self.dbpool.close()
        print("释放连接池成功")

    def process_item(self, item, spider):
        """
        处理每个 Item，将插入操作提交给连接池异步执行
        """
        # 使用 runInteraction 将同步插入操作放到线程池中执行
        query = self.dbpool.runInteraction(self._do_insert, item)
        # 添加错误回调
        query.addErrback(self._handle_error, item, spider)
        return item

    def _do_insert(self, cursor, item):
        """
        实际执行插入操作（原样入库，不做任何清洗）
        """
        sql = """
            INSERT IGNORE INTO ctrip_travel_products_raw (
                title, subtitle, price, score, 
                comment_count, sold_count, source_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            item.get('title'),
            item.get('subtitle'),          # 可能为 None，对应数据库 NULL
            item.get('price'),             # 原始字符串，如 '8554'
            item.get('score'),             # 原始字符串，如 '4.8'
            item.get('commentCount'),      # 原始字符串，如 '192条点评'
            item.get('soldCount'),         # 原始字符串，如 '已售675'
            item.get('source_url'),        # 你拼接的唯一产品 URL
        )
        cursor.execute(sql, values)

    def _handle_error(self, failure, item, spider):

       print("失败")

class XiechengPipeline:
    def process_item(self, item, spider):
        return item