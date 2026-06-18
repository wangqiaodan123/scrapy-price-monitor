"""
数据库工具模块
提供 MySQL 连接池、MongoDB 连接、表初始化、常用查询等功能
"""

import logging
import yaml
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 加载配置
CONFIG_PATH = Path(__file__).parent.parent.parent / 'config.yaml'
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    CONFIG = yaml.safe_load(f)


class MySQLHelper:
    """
    MySQL 数据库辅助类
    提供连接池管理、表初始化、常用查询等操作
    """

    def __init__(self, config=None):
        self.config = config or CONFIG.get('database', {}).get('mysql', {})
        self.pool = None

    def init_pool(self):
        """初始化连接池"""
        try:
            from dbutils.pooled_db import PooledDB
            import pymysql

            self.pool = PooledDB(
                creator=pymysql,
                maxconnections=self.config.get('pool_size', 10),
                mincached=2,
                maxcached=5,
                blocking=True,
                maxusage=None,
                setsession=[],
                ping=1,
                host=self.config['host'],
                port=self.config.get('port', 3306),
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset=self.config.get('charset', 'utf8mb4'),
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info("MySQL 连接池初始化成功")
        except Exception as e:
            logger.error(f"MySQL 连接池初始化失败: {e}")
            raise

    def get_connection(self):
        """获取数据库连接"""
        if not self.pool:
            self.init_pool()
        return self.pool.connection()

    def init_tables(self):
        """初始化数据表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 创建商品表
            create_products_sql = """
                CREATE TABLE IF NOT EXISTS `products` (
                    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                    `product_id` VARCHAR(100) NOT NULL COMMENT '商品ID',
                    `name` VARCHAR(500) NOT NULL COMMENT '商品名称',
                    `price` DECIMAL(10,2) COMMENT '当前价格',
                    `original_price` DECIMAL(10,2) COMMENT '原价',
                    `discount` VARCHAR(50) COMMENT '折扣信息',
                    `shop` VARCHAR(200) COMMENT '店铺名称',
                    `platform` VARCHAR(50) NOT NULL COMMENT '平台 (jd/taobao/suning)',
                    `url` VARCHAR(1000) COMMENT '商品链接',
                    `image_url` VARCHAR(1000) COMMENT '图片链接',
                    `category` VARCHAR(200) COMMENT '分类',
                    `keyword` VARCHAR(100) COMMENT '搜索关键词',
                    `reviews_count` INT DEFAULT 0 COMMENT '评论数',
                    `sales_count` INT DEFAULT 0 COMMENT '销量',
                    `rating` DECIMAL(3,2) COMMENT '评分',
                    `crawl_time` DATETIME NOT NULL COMMENT '采集时间',
                    `update_time` DATETIME NOT NULL COMMENT '更新时间',
                    UNIQUE KEY `uk_product_platform` (`product_id`, `platform`),
                    INDEX `idx_platform` (`platform`),
                    INDEX `idx_keyword` (`keyword`),
                    INDEX `idx_crawl_time` (`crawl_time`),
                    INDEX `idx_price` (`price`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品数据表';
            """
            cursor.execute(create_products_sql)

            # 创建价格历史表
            create_price_history_sql = """
                CREATE TABLE IF NOT EXISTS `price_history` (
                    `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                    `product_id` VARCHAR(100) NOT NULL COMMENT '商品ID',
                    `platform` VARCHAR(50) NOT NULL COMMENT '平台',
                    `name` VARCHAR(500) COMMENT '商品名称',
                    `price` DECIMAL(10,2) NOT NULL COMMENT '价格',
                    `original_price` DECIMAL(10,2) COMMENT '原价',
                    `discount` VARCHAR(50) COMMENT '折扣',
                    `price_change` DECIMAL(10,2) DEFAULT 0 COMMENT '价格变化',
                    `price_change_pct` DECIMAL(5,2) DEFAULT 0 COMMENT '价格变化百分比',
                    `record_time` DATETIME NOT NULL COMMENT '记录时间',
                    INDEX `idx_product` (`product_id`, `platform`),
                    INDEX `idx_record_time` (`record_time`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='价格历史记录表';
            """
            cursor.execute(create_price_history_sql)

            conn.commit()
            logger.info("MySQL 数据表初始化成功")

        except Exception as e:
            logger.error(f"MySQL 数据表初始化失败: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def query_products(self, platform=None, keyword=None, limit=100):
        """
        查询商品数据

        Args:
            platform: 平台筛选
            keyword: 关键词筛选
            limit: 返回数量限制

        Returns:
            list: 商品列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            sql = "SELECT * FROM products WHERE 1=1"
            params = []

            if platform:
                sql += " AND platform = %s"
                params.append(platform)

            if keyword:
                sql += " AND keyword LIKE %s"
                params.append(f'%{keyword}%')

            sql += " ORDER BY crawl_time DESC LIMIT %s"
            params.append(limit)

            cursor.execute(sql, params)
            results = cursor.fetchall()

            return results

        except Exception as e:
            logger.error(f"查询商品失败: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def query_price_history(self, product_id, platform, days=30):
        """
        查询价格历史

        Args:
            product_id: 商品ID
            platform: 平台
            days: 查询天数

        Returns:
            list: 价格历史列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            start_time = datetime.now() - timedelta(days=days)

            sql = """
                SELECT * FROM price_history
                WHERE product_id = %s AND platform = %s AND record_time >= %s
                ORDER BY record_time ASC
            """
            cursor.execute(sql, (product_id, platform, start_time))
            results = cursor.fetchall()

            return results

        except Exception as e:
            logger.error(f"查询价格历史失败: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def get_price_statistics(self, platform=None, keyword=None, days=7):
        """
        获取价格统计信息

        Args:
            platform: 平台筛选
            keyword: 关键词筛选
            days: 统计天数

        Returns:
            dict: 统计信息
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            start_time = datetime.now() - timedelta(days=days)

            sql = """
                SELECT
                    COUNT(*) as total_products,
                    AVG(price) as avg_price,
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    COUNT(CASE WHEN price_change < 0 THEN 1 END) as price_drop_count,
                    COUNT(CASE WHEN price_change > 0 THEN 1 END) as price_rise_count
                FROM products p
                LEFT JOIN price_history h ON p.product_id = h.product_id AND p.platform = h.platform
                WHERE p.crawl_time >= %s
            """
            params = [start_time]

            if platform:
                sql += " AND p.platform = %s"
                params.append(platform)

            if keyword:
                sql += " AND p.keyword LIKE %s"
                params.append(f'%{keyword}%')

            cursor.execute(sql, params)
            result = cursor.fetchone()

            return result

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()


class MongoDBHelper:
    """
    MongoDB 数据库辅助类
    提供连接管理、集合初始化、常用查询等操作
    """

    def __init__(self, config=None):
        self.config = config or CONFIG.get('database', {}).get('mongodb', {})
        self.client = None
        self.db = None

    def connect(self):
        """建立连接"""
        try:
            import pymongo

            self.client = pymongo.MongoClient(self.config['uri'])
            self.db = self.client[self.config['database']]
            logger.info("MongoDB 连接成功")
        except Exception as e:
            logger.error(f"MongoDB 连接失败: {e}")
            raise

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB 连接已关闭")

    def init_collections(self):
        """初始化集合和索引"""
        if not self.db:
            self.connect()

        try:
            # 商品集合
            products_collection = self.config.get('collection_products', 'products')
            self.db[products_collection].create_index(
                [('product_id', 1), ('platform', 1)],
                unique=True
            )
            self.db[products_collection].create_index([('crawl_time', -1)])
            self.db[products_collection].create_index([('keyword', 1)])

            # 价格历史集合
            history_collection = self.config.get('collection_history', 'price_history')
            self.db[history_collection].create_index([('product_id', 1), ('platform', 1)])
            self.db[history_collection].create_index([('record_time', -1)])

            logger.info("MongoDB 集合索引初始化成功")

        except Exception as e:
            logger.error(f"MongoDB 集合初始化失败: {e}")
            raise

    def query_products(self, platform=None, keyword=None, limit=100):
        """
        查询商品数据

        Args:
            platform: 平台筛选
            keyword: 关键词筛选
            limit: 返回数量限制

        Returns:
            list: 商品列表
        """
        if not self.db:
            self.connect()

        try:
            products_collection = self.config.get('collection_products', 'products')
            collection = self.db[products_collection]

            query = {}
            if platform:
                query['platform'] = platform
            if keyword:
                query['keyword'] = {'$regex': keyword, '$options': 'i'}

            results = list(collection.find(query).sort('crawl_time', -1).limit(limit))

            return results

        except Exception as e:
            logger.error(f"查询商品失败: {e}")
            return []

    def query_price_history(self, product_id, platform, days=30):
        """
        查询价格历史

        Args:
            product_id: 商品ID
            platform: 平台
            days: 查询天数

        Returns:
            list: 价格历史列表
        """
        if not self.db:
            self.connect()

        try:
            history_collection = self.config.get('collection_history', 'price_history')
            collection = self.db[history_collection]

            start_time = datetime.now() - timedelta(days=days)

            query = {
                'product_id': product_id,
                'platform': platform,
                'record_time': {'$gte': start_time.isoformat()}
            }

            results = list(collection.find(query).sort('record_time', 1))

            return results

        except Exception as e:
            logger.error(f"查询价格历史失败: {e}")
            return []

    def get_price_drop_alerts(self, threshold=10, limit=50):
        """
        获取降价预警商品

        Args:
            threshold: 降价百分比阈值
            limit: 返回数量限制

        Returns:
            list: 降价商品列表
        """
        if not self.db:
            self.connect()

        try:
            history_collection = self.config.get('collection_history', 'price_history')
            collection = self.db[history_collection]

            query = {
                'price_change_pct': {'$lte': -threshold}
            }

            results = list(
                collection.find(query)
                .sort('record_time', -1)
                .limit(limit)
            )

            return results

        except Exception as e:
            logger.error(f"获取降价预警失败: {e}")
            return []


# 便捷函数
def init_mysql_tables():
    """初始化 MySQL 数据表"""
    helper = MySQLHelper()
    helper.init_tables()
    logger.info("MySQL 数据表初始化完成")


def init_mongodb_collections():
    """初始化 MongoDB 集合"""
    helper = MongoDBHelper()
    helper.init_collections()
    helper.close()
    logger.info("MongoDB 集合初始化完成")


def get_mysql_helper():
    """获取 MySQL 辅助类实例"""
    return MySQLHelper()


def get_mongodb_helper():
    """获取 MongoDB 辅助类实例"""
    return MongoDBHelper()
