import json
import random
import time
import scrapy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from xiecheng.items import XiechengItem
from scrapy.selector import Selector
class CtripSpider(scrapy.Spider):
    name = "ctrip"
    allowed_domains = ["vacations.ctrip.com"]
    start_urls = ["https://vacations.ctrip.com/list/whole/sc201.html?sv=%E4%B8%AD%E5%9B%BD&st=%E4%B8%AD%E5%9B%BD&startcity=201"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 1. 先创建浏览器选项
        options = webdriver.ChromeOptions()

        # 2. 开启必要的反检测参数（之前被注释了，现在启用）
        # options.add_argument("--disable-blink-features=AutomationControlled")
        # # options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # options.add_experimental_option("useAutomationExtension", False)
        # 如果运行在服务器上，可添加无头模式（调试时注释掉）
        options.add_argument("--headless")
        # options.add_argument("--no-sandbox")
        # options.add_argument("--disable-dev-shm-usage")
        options.add_argument('--disable-gpu')
        # 3. 创建 driver 实例
        self.driver = webdriver.Chrome(options=options)

        # 4. 在 driver 加载任何页面之前，执行 CDP 命令隐藏 webdriver 特征
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
        })

        # 5. 现在再加载目标页面
        self.driver.get(self.start_urls[0])
        # 初始化浏览器驱动（整个爬虫生命周期只创建一次）
        # 在创建 driver 之前执行

    # def start_requests(self):
    # 只发起一个虚拟请求，让 Scrapy 调用 parse
    # 我们实际数据由 driver 获取，不依赖 response
    # yield scrapy.Request(url=self.start_urls[0], callback=self.parse, dont_filter=True)

    def parse(self, response):
        driver = self.driver
        page_num = 1
        i=0
        while True:
            self.logger.info(f"正在抓取第 {page_num} 页")

            # ---------- 1. 解析当前页 ----------
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'list_product_right')]"))
                )
            except TimeoutException:
                driver.get(driver.current_url)
                self.logger.warning("可能已到最后")
                continue
            html = driver.page_source
            sel = Selector(text=html)
            node_list  = sel.xpath("//div[contains(@class, 'list_product_right')]")
            if not node_list:
                self.logger.warning("可能页面结构变化")
                break
            i+=len(node_list)

            for node in node_list:
                temp = XiechengItem()
                temp['title']=node.xpath("./p[1]/span/text()").extract_first()
                temp['subtitle']=node.xpath("./p[2]/text()").extract_first()
                temp['score']=node.xpath("./div[2]/span[1]/span/text()").extract_first()
                temp['soldCount']=node.xpath("./div[2]/span[2]/text()").extract_first()
                temp['commentCount']=node.xpath("./div[2]/span[4]/text()[1]").extract_first()
                temp['price']=node.xpath("./div[3]/div[2]/div/div[1]/strong/text()").extract_first()
                s_url= node.xpath("./ancestor::div[contains(@class, 'list_product_box')]/@data-track-product-id").extract_first()
                temp['source_url']="https://vacations.ctrip.com/travel/detail/p"+s_url+"/?city=201"
                yield temp
            print("现在有{}条信息".format(i))
            # ---------- 2. 尝试点击下一页 ----------
            try:
                # 等待下一页按钮可点击
                next_btn = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, '//div[@class="down paging_item"]'))
                )
                # 检查是否被禁用
                if "disabled" in next_btn.get_attribute("class"):
                    self.logger.info("下一页按钮不可用，已达最后一页")
                    break

                # 点击翻页
                next_btn.click()
                delay = random.uniform(2, 4)
                time.sleep(delay)
                # WebDriverWait(driver, 10).until(
                #     EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'list_product_right')]"))
                # )
                # 额外等待，确保动态内容完全渲染
                # time.sleep(2)
                page_num += 1
            except TimeoutException:
                self.logger.info("翻页超时，可能没有下一页或网络延迟")
                driver.get("https://vacations.ctrip.com/list/whole/sc201.html?sv=%E4%B8%AD%E5%9B%BD&st=%E4%B8%AD%E5%9B%BD&startcity=201")

            except NoSuchElementException:
                self.logger.info("未找到下一页按钮，结束")
                break
            except Exception as e:
                self.logger.error(f"翻页异常: {e}")
                break

    def closed(self, reason):
        """爬虫结束时关闭浏览器"""
        self.driver.quit()
        self.logger.info("浏览器已关闭")