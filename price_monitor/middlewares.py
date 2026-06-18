"""
自定义下载器中间件
实现反爬虫策略：User-Agent轮换、代理池、智能重试、Referer伪装
"""

import random
import time
import logging
from scrapy import signals
from scrapy.http import Request
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)

# 真实浏览器 User-Agent 池
USER_AGENT_POOL = [
    # Chrome Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    # Chrome Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    # Firefox Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0',
    # Firefox Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:119.0) Gecko/20100101 Firefox/119.0',
    # Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    # Safari
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
    # 移动端
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
]

# Referer 来源池 (模拟从搜索引擎或平台跳转)
REFERER_POOL = [
    'https://www.baidu.com/',
    'https://www.google.com/',
    'https://www.sogou.com/',
    'https://www.so.com/',
    'https://www.bing.com/',
    'https://search.jd.com/',
    'https://s.taobao.com/',
    'https://search.suning.com/',
]


class RandomUserAgentMiddleware:
    """
    随机 User-Agent 中间件
    每次请求随机选择 User-Agent，模拟不同浏览器
    """

    def __init__(self, user_agent_pool=None):
        self.user_agent_pool = user_agent_pool or USER_AGENT_POOL

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        return middleware

    def spider_opened(self, spider):
        logger.info(f"RandomUserAgentMiddleware 已启用, User-Agent 池大小: {len(self.user_agent_pool)}")

    def process_request(self, request, spider):
        """为每个请求随机分配 User-Agent"""
        user_agent = random.choice(self.user_agent_pool)
        request.headers['User-Agent'] = user_agent
        spider.logger.debug(f"使用 User-Agent: {user_agent[:50]}...")
        return None


class ProxyMiddleware:
    """
    代理池中间件
    支持从代理API或静态列表获取代理，实现IP轮换
    """

    def __init__(self, proxy_pool=None, api_url=None, refresh_interval=60):
        self.proxy_pool = proxy_pool or []
        self.api_url = api_url
        self.refresh_interval = refresh_interval
        self.last_refresh_time = 0
        self.failed_proxies = set()

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        from price_monitor.settings import CONFIG

        proxy_config = CONFIG.get('proxy', {})
        enabled = proxy_config.get('enabled', False)

        if not enabled:
            raise NotConfigured("代理池未启用，跳过 ProxyMiddleware")

        proxy_pool = proxy_config.get('proxy_list', [])
        api_url = proxy_config.get('api_url')
        refresh_interval = proxy_config.get('refresh_interval', 60)

        middleware = cls(
            proxy_pool=proxy_pool,
            api_url=api_url,
            refresh_interval=refresh_interval
        )
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        return middleware

    def spider_opened(self, spider):
        logger.info(f"ProxyMiddleware 已启用, 代理池大小: {len(self.proxy_pool)}")

    def _get_proxy(self):
        """获取一个可用代理"""
        # 如果代理池为空且配置了 API，尝试获取新代理
        if not self.proxy_pool and self.api_url:
            self._refresh_proxy_pool()

        # 过滤掉失败的代理
        available_proxies = [p for p in self.proxy_pool if p not in self.failed_proxies]

        if not available_proxies:
            # 如果所有代理都失败，重置失败列表并重试
            self.failed_proxies.clear()
            available_proxies = self.proxy_pool

        if not available_proxies:
            return None

        return random.choice(available_proxies)

    def _refresh_proxy_pool(self):
        """从代理API刷新代理池"""
        current_time = time.time()
        if current_time - self.last_refresh_time < self.refresh_interval:
            return

        try:
            import requests
            response = requests.get(self.api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.proxy_pool.extend(data)
                elif isinstance(data, dict) and 'proxies' in data:
                    self.proxy_pool.extend(data['proxies'])
                logger.info(f"代理池已刷新，当前大小: {len(self.proxy_pool)}")
                self.last_refresh_time = current_time
        except Exception as e:
            logger.warning(f"刷新代理池失败: {e}")

    def process_request(self, request, spider):
        """为请求设置代理"""
        proxy = self._get_proxy()
        if proxy:
            request.meta['proxy'] = proxy
            spider.logger.debug(f"使用代理: {proxy}")
        return None

    def process_exception(self, request, exception, spider):
        """处理代理请求失败"""
        proxy = request.meta.get('proxy')
        if proxy:
            self.failed_proxies.add(proxy)
            spider.logger.warning(f"代理 {proxy} 请求失败: {exception}")
        return None


class RetryMiddleware:
    """
    智能重试中间件
    实现指数退避重试策略，处理临时性网络错误
    """

    def __init__(self, max_retries=3):
        self.max_retries = max_retries

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        from price_monitor.settings import CONFIG
        max_retries = CONFIG.get('crawler', {}).get('max_retries', 3)
        middleware = cls(max_retries=max_retries)
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        return middleware

    def spider_opened(self, spider):
        logger.info(f"RetryMiddleware 已启用, 最大重试次数: {self.max_retries}")

    def process_response(self, request, response, spider):
        """处理响应状态码，决定是否重试"""
        # 对于某些状态码进行重试
        retry_codes = [403, 404, 408, 429, 500, 502, 503, 504]

        if response.status in retry_codes:
            retries = request.meta.get('retry_times', 0)

            if retries < self.max_retries:
                # 指数退避: 1s, 2s, 4s, 8s...
                delay = 2 ** retries
                spider.logger.warning(
                    f"请求失败 (状态码 {response.status})，{delay}秒后重试 (第 {retries + 1} 次)"
                )

                # 等待退避时间
                time.sleep(delay)

                # 重试请求
                retry_request = request.copy()
                retry_request.meta['retry_times'] = retries + 1
                retry_request.dont_filter = True
                return retry_request
            else:
                spider.logger.error(f"请求失败，已达最大重试次数: {request.url}")

        return response

    def process_exception(self, request, exception, spider):
        """处理请求异常"""
        retries = request.meta.get('retry_times', 0)

        if retries < self.max_retries:
            delay = 2 ** retries
            spider.logger.warning(
                f"请求异常: {exception}，{delay}秒后重试 (第 {retries + 1} 次)"
            )

            time.sleep(delay)

            retry_request = request.copy()
            retry_request.meta['retry_times'] = retries + 1
            retry_request.dont_filter = True
            return retry_request

        spider.logger.error(f"请求异常，已达最大重试次数: {request.url}, 异常: {exception}")
        return None


class RefererMiddleware:
    """
    Referer 伪装中间件
    随机设置 Referer 头，模拟从搜索引擎或其他页面跳转
    """

    def __init__(self, referer_pool=None):
        self.referer_pool = referer_pool or REFERER_POOL

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        return middleware

    def spider_opened(self, spider):
        logger.info(f"RefererMiddleware 已启用, Referer 池大小: {len(self.referer_pool)}")

    def process_request(self, request, spider):
        """为请求设置随机 Referer"""
        referer = random.choice(self.referer_pool)
        request.headers['Referer'] = referer
        spider.logger.debug(f"使用 Referer: {referer}")
        return None
