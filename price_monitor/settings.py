"""
Scrapy 全局配置文件
电商商品价格监控系统
"""

import os
import yaml
from pathlib import Path

# 加载外部配置文件
CONFIG_PATH = Path(__file__).parent.parent / 'config.yaml'
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    CONFIG = yaml.safe_load(f)

# ============================================================================
# 基础配置
# ============================================================================

BOT_NAME = 'price_monitor'
SPIDER_MODULES = ['price_monitor.spiders']
NEWSPIDER_MODULE = 'price_monitor.spiders'

# ============================================================================
# 请求头配置
# ============================================================================

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# ============================================================================
# 中间件配置
# ============================================================================

DOWNLOADER_MIDDLEWARES = {
    # 禁用默认 User-Agent 中间件
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    # 自定义中间件
    'price_monitor.middlewares.RandomUserAgentMiddleware': 400,
    'price_monitor.middlewares.ProxyMiddleware': 410,
    'price_monitor.middlewares.RetryMiddleware': 420,
    'price_monitor.middlewares.RefererMiddleware': 430,
}

# ============================================================================
# 数据管道配置
# ============================================================================

ITEM_PIPELINES = {
    'price_monitor.pipelines.DataCleanPipeline': 100,
    'price_monitor.pipelines.DuplicateFilterPipeline': 200,
    'price_monitor.pipelines.MySQLPipeline': 300,
    'price_monitor.pipelines.MongoDBPipeline': 400,
    'price_monitor.pipelines.CSVPipeline': 500,
}

# ============================================================================
# 爬取行为配置
# ============================================================================

# 遵守 robots.txt
ROBOTSTXT_OBEY = False

# 并发请求数
CONCURRENT_REQUESTS = CONFIG.get('crawler', {}).get('concurrent_requests', 8)
CONCURRENT_REQUESTS_PER_DOMAIN = CONFIG.get('crawler', {}).get('concurrent_requests_per_domain', 4)

# 下载延迟
DOWNLOAD_DELAY = CONFIG.get('crawler', {}).get('download_delay', 2)
RANDOMIZE_DOWNLOAD_DELAY = True

# 请求超时
DOWNLOAD_TIMEOUT = CONFIG.get('crawler', {}).get('timeout', 30)

# Cookie 配置
COOKIES_ENABLED = True
COOKIES_DEBUG = False

# ============================================================================
# 自动限速配置 (AutoThrottle)
# ============================================================================

AUTOTHROTTLE_ENABLED = CONFIG.get('crawler', {}).get('autothrottle', {}).get('enabled', True)
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MIN_DELAY = CONFIG.get('crawler', {}).get('autothrottle', {}).get('min_delay', 1)
AUTOTHROTTLE_MAX_DELAY = CONFIG.get('crawler', {}).get('autothrottle', {}).get('max_delay', 10)
AUTOTHROTTLE_TARGET_CONCURRENCY = CONFIG.get('crawler', {}).get('autothrottle', {}).get('target_concurrency', 2.0)
AUTOTHROTTLE_DEBUG = False

# ============================================================================
# 重试配置
# ============================================================================

RETRY_ENABLED = True
RETRY_TIMES = CONFIG.get('crawler', {}).get('max_retries', 3)
RETRY_HTTP_CODES = [403, 404, 408, 429, 500, 502, 503, 504]

# ============================================================================
# 缓存配置
# ============================================================================

HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 0
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# ============================================================================
# 分布式爬虫配置 (scrapy-redis)
# ============================================================================

# 使用 Redis 调度器
SCHEDULER = 'scrapy_redis.scheduler.Scheduler'
SCHEDULER_PERSIST = True

# 使用 Redis 去重过滤器
DUPEFILTER_CLASS = 'scrapy_redis.dupefilter.RFPDupeFilter'

# Redis 连接配置
REDIS_URL = CONFIG.get('database', {}).get('redis', {}).get('url', 'redis://127.0.0.1:6379/0')
REDIS_PARAMS = {
    'retry_on_timeout': True,
    'socket_timeout': 5,
}

# Redis 键前缀
SCHEDULER_QUEUE_KEY = CONFIG.get('database', {}).get('redis', {}).get('queue_key', 'price_monitor:requests')
SCHEDULER_DUPEFILTER_KEY = CONFIG.get('database', {}).get('redis', {}).get('dupefilter_key', 'price_monitor:dupefilter')

# 调度队列类型
SCHEDULER_QUEUE_CLASS = 'scrapy_redis.queue.PriorityQueue'

# ============================================================================
# 日志配置
# ============================================================================

LOG_LEVEL = CONFIG.get('logging', {}).get('level', 'INFO')
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

# 日志文件输出
LOG_FILE = CONFIG.get('logging', {}).get('file', './logs/price_monitor.log')

# 确保日志目录存在
log_dir = os.path.dirname(LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)

# ============================================================================
# 扩展配置
# ============================================================================

EXTENSIONS = {
    'scrapy.extensions.telnet.TelnetConsole': None,  # 禁用 Telnet 控制台
    'scrapy.extensions.corestats.CoreStats': 0,
    'scrapy.extensions.logstats.LogStats': 0,
}

# ============================================================================
# 其他配置
# ============================================================================

# 请求指纹去重
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'
TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'
FEED_EXPORT_ENCODING = 'utf-8'

# 关闭某些不需要的中间件
DOWNLOAD_HANDLERS = {
    'http': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
    'https': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
}
