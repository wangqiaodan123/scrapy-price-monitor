"""
淘宝商品爬虫
使用 Selenium 处理动态内容和登录验证
支持滑块验证码检测
"""

import scrapy
import time
import re
from scrapy import Request
from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from price_monitor.items import ProductItem
from price_monitor.utils.anti_detect import random_sleep, check_captcha


class TaobaoSpider(scrapy.Spider):
    """
    淘宝商品搜索爬虫
    使用 Selenium 处理 JavaScript 渲染和登录验证
    """
    name = 'taobao'
    allowed_domains = ['taobao.com', 's.taobao.com']

    # 默认配置
    default_keyword = '手机'

    def __init__(self, keyword=None, max_pages=5, use_selenium=True, *args, **kwargs):
        super(TaobaoSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword or self.default_keyword
        self.max_pages = int(max_pages)
        self.use_selenium = use_selenium
        self.driver = None

    def start_requests(self):
        """启动 Selenium 并开始爬取"""
        if self.use_selenium:
            self._init_selenium()

        url = f'https://s.taobao.com/search?q={self.keyword}'
        self.logger.info(f"开始采集淘宝商品，关键词: {self.keyword}")
        yield Request(url, callback=self.parse_search_results, meta={'page': 1})

    def _init_selenium(self):
        """初始化 Selenium WebDriver"""
        self.logger.info("初始化 Selenium WebDriver...")

        chrome_options = Options()
        # 设置无头模式 (生产环境)
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        # 设置窗口大小
        chrome_options.add_argument('--window-size=1920,1080')

        # 禁用图片加载 (提高速度)
        prefs = {
            'profile.managed_default_content_settings.images': 2,
            'profile.default_content_setting_state.notifications': 2
        }
        chrome_options.add_experimental_option('prefs', prefs)

        # 添加随机 User-Agent
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            self.logger.info("Selenium WebDriver 初始化成功")
        except Exception as e:
            self.logger.error(f"Selenium WebDriver 初始化失败: {e}")
            raise

    def closed(self, reason):
        """爬虫关闭时清理资源"""
        if self.driver:
            self.driver.quit()
            self.logger.info("Selenium WebDriver 已关闭")

    def parse_search_results(self, response):
        """解析搜索结果页"""
        current_page = response.meta.get('page', 1)
        self.logger.info(f"解析淘宝搜索结果第 {current_page} 页")

        if self.use_selenium:
            # 使用 Selenium 获取动态内容
            html = self._fetch_with_selenium(response.url)

            # 创建新的 Response 对象
            response = HtmlResponse(
                url=response.url,
                body=html.encode('utf-8'),
                encoding='utf-8'
            )

        # 检查是否需要登录或验证码
        if self._check_login_required(response):
            self.logger.warning("需要登录或遇到验证码，暂停爬取")
            return

        # 提取商品列表
        product_list = response.xpath('//div[@class="items"]/div[@class="item"]')

        if not product_list:
            # 尝试其他选择器
            product_list = response.xpath('//div[contains(@class, "Card--doubleCardWrapper")]')

        if not product_list:
            self.logger.warning(f"第 {current_page} 页未找到商品")
            return

        for product in product_list:
            item = ProductItem()

            # 商品 ID
            item_id = product.xpath('.//@data-item-id').get()
            if not item_id:
                item_id = product.xpath('.//@data-id').get()
            item['product_id'] = item_id

            # 商品名称
            name = product.xpath('.//div[contains(@class, "title")]/text()').get()
            if not name:
                name = product.xpath('.//a[contains(@class, "title")]/span/text()').get()
            if not name:
                name = product.xpath('.//h3/text()').get()
            item['name'] = name

            # 价格
            price = product.xpath('.//div[contains(@class, "price")]/strong/text()').get()
            if not price:
                price = product.xpath('.//span[contains(@class, "Price--priceNum")]/text()').get()
            if price:
                # 提取数字部分
                price_match = re.search(r'[\d.]+', price)
                if price_match:
                    item['price'] = price_match.group()

            # 店铺名称
            shop = product.xpath('.//div[contains(@class, "shopname")]/span/text()').get()
            if not shop:
                shop = product.xpath('.//span[contains(@class, "ShopInfo--TextAndPic")]/text()').get()
            item['shop'] = shop

            # 商品链接
            url = product.xpath('.//a[contains(@class, "picLink")]/@href').get()
            if not url:
                url = product.xpath('.//a[contains(@class, "Card--doubleCardWrapper")]/@href').get()
            if url:
                if not url.startswith('http'):
                    url = 'https:' + url
                item['url'] = url

            # 商品图片
            image_url = product.xpath('.//img[contains(@class, "pic")]/@data-src').get()
            if not image_url:
                image_url = product.xpath('.//img[contains(@class, "pic")]/@src').get()
            if image_url and not image_url.startswith('http'):
                image_url = 'https:' + image_url
            item['image_url'] = image_url

            # 销量
            sales = product.xpath('.//div[contains(@class, "deal-cnt")]/text()').get()
            if not sales:
                sales = product.xpath('.//span[contains(@class, "Deal--dealCnt")]/text()').get()
            item['sales_count'] = sales

            # 设置平台信息
            item['platform'] = 'taobao'
            item['keyword'] = self.keyword

            # 只输出有效数据
            if item.get('name'):
                yield item

        # 处理分页
        if current_page < self.max_pages:
            next_page = current_page + 1
            # 淘宝分页参数: s=44*(page-1)
            s_param = (next_page - 1) * 44
            next_url = f'https://s.taobao.com/search?q={self.keyword}&s={s_param}'

            # 随机延迟，避免请求过快
            random_sleep(2, 5)

            yield Request(
                next_url,
                callback=self.parse_search_results,
                meta={'page': next_page}
            )

    def _fetch_with_selenium(self, url):
        """使用 Selenium 获取页面内容"""
        try:
            self.driver.get(url)

            # 等待页面加载
            time.sleep(3)

            # 检查是否有验证码
            if check_captcha(self.driver):
                self.logger.warning("检测到验证码，请手动处理或等待")
                # 等待一段时间，看验证码是否自动消失
                time.sleep(10)

            # 滚动页面以加载更多内容
            self._scroll_page()

            # 获取页面源码
            html = self.driver.page_source
            return html

        except Exception as e:
            self.logger.error(f"Selenium 获取页面失败: {e}")
            return ''

    def _scroll_page(self):
        """模拟滚动页面以加载懒加载内容"""
        try:
            # 滚动到页面底部
            self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(1)

            # 滚动到中间
            self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight / 2);')
            time.sleep(1)

            # 滚动到底部
            self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(1)

        except Exception as e:
            self.logger.warning(f"页面滚动失败: {e}")

    def _check_login_required(self, response):
        """检查是否需要登录"""
        # 检查常见的登录提示
        login_indicators = [
            '//div[contains(@class, "login")]',
            '//div[contains(text(), "登录")]',
            '//a[contains(text(), "请登录")]',
            '//div[contains(@class, "captcha")]',
            '//div[contains(text(), "验证码")]',
        ]

        for xpath in login_indicators:
            if response.xpath(xpath).get():
                return True

        return False

    def _handle_slider_captcha(self):
        """
        处理滑块验证码 (简化版本)
        实际生产环境中需要更复杂的滑块识别算法
        """
        try:
            # 查找滑块元素
            slider = self.driver.find_element(By.ID, 'nc_1_n1z')

            # 模拟拖动滑块
            action = webdriver.ActionChains(self.driver)
            action.click_and_hold(slider).perform()

            # 模拟人类拖动 (随机速度和停顿)
            import random
            for _ in range(30):
                offset = random.randint(10, 20)
                action.move_by_offset(offset, 0).perform()
                time.sleep(random.uniform(0.01, 0.05))

            action.release().perform()

            # 等待验证完成
            time.sleep(2)

            self.logger.info("滑块验证码处理完成")
            return True

        except NoSuchElementException:
            self.logger.debug("未找到滑块验证码")
            return False
        except Exception as e:
            self.logger.error(f"处理滑块验证码失败: {e}")
            return False
