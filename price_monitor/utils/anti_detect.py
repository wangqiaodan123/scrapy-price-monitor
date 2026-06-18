"""
反检测工具模块
提供 Cookie 管理、浏览器指纹随机化、请求间隔随机化、验证码检测等功能
"""

import random
import time
import hashlib
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def random_sleep(min_seconds=1, max_seconds=3):
    """
    随机延迟
    模拟人类行为，避免请求过于频繁

    Args:
        min_seconds: 最小延迟秒数
        max_seconds: 最大延迟秒数
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)
    logger.debug(f"随机延迟 {delay:.2f} 秒")


def randomize_request_interval(base_interval=2, variance=0.5):
    """
    随机化请求间隔
    在基础间隔上添加随机波动

    Args:
        base_interval: 基础间隔 (秒)
        variance: 波动范围 (0-1)

    Returns:
        float: 随机化后的间隔
    """
    min_interval = base_interval * (1 - variance)
    max_interval = base_interval * (1 + variance)
    interval = random.uniform(min_interval, max_interval)
    return interval


class CookieManager:
    """
    Cookie 管理器
    管理多个账号的 Cookie，支持自动刷新和轮换
    """

    def __init__(self):
        self.cookies = {}
        self.cookie_timestamps = {}
        self.cookie_ttl = 3600  # Cookie 有效期 (秒)

    def add_cookie(self, account_id, cookie_dict):
        """
        添加或更新 Cookie

        Args:
            account_id: 账号标识
            cookie_dict: Cookie 字典
        """
        self.cookies[account_id] = cookie_dict
        self.cookie_timestamps[account_id] = datetime.now()
        logger.info(f"Cookie 已更新: {account_id}")

    def get_cookie(self, account_id=None):
        """
        获取 Cookie

        Args:
            account_id: 账号标识，为 None 时随机获取

        Returns:
            dict: Cookie 字典
        """
        if not self.cookies:
            return None

        # 清理过期 Cookie
        self._clean_expired_cookies()

        if account_id:
            return self.cookies.get(account_id)

        # 随机选择一个账号的 Cookie
        available_accounts = list(self.cookies.keys())
        if available_accounts:
            selected = random.choice(available_accounts)
            return self.cookies[selected]

        return None

    def _clean_expired_cookies(self):
        """清理过期的 Cookie"""
        current_time = datetime.now()
        expired_accounts = []

        for account_id, timestamp in self.cookie_timestamps.items():
            if (current_time - timestamp).total_seconds() > self.cookie_ttl:
                expired_accounts.append(account_id)

        for account_id in expired_accounts:
            del self.cookies[account_id]
            del self.cookie_timestamps[account_id]
            logger.info(f"Cookie 已过期并清理: {account_id}")

    def remove_cookie(self, account_id):
        """删除指定账号的 Cookie"""
        if account_id in self.cookies:
            del self.cookies[account_id]
            del self.cookie_timestamps[account_id]
            logger.info(f"Cookie 已删除: {account_id}")

    def list_accounts(self):
        """列出所有账号"""
        return list(self.cookies.keys())


class BrowserFingerprint:
    """
    浏览器指纹生成器
    随机生成浏览器特征，用于反检测
    """

    # 屏幕分辨率池
    SCREEN_RESOLUTIONS = [
        (1920, 1080), (2560, 1440), (1366, 768), (1440, 900),
        (1536, 864), (1680, 1050), (1280, 720), (3840, 2160)
    ]

    # 时区池
    TIMEZONES = [
        'Asia/Shanghai', 'Asia/Hong_Kong', 'Asia/Taipei',
        'America/New_York', 'America/Los_Angeles', 'Europe/London'
    ]

    # 语言池
    LANGUAGES = [
        'zh-CN', 'zh-TW', 'zh-HK', 'en-US', 'en-GB', 'ja-JP'
    ]

    # 色深
    COLOR_DEPTHS = [24, 32]

    # 硬件并发数
    HARDWARE_CONCURRENCY = [2, 4, 8, 16]

    def generate(self):
        """
        生成随机浏览器指纹

        Returns:
            dict: 浏览器指纹特征
        """
        resolution = random.choice(self.SCREEN_RESOLUTIONS)

        fingerprint = {
            'screen': {
                'width': resolution[0],
                'height': resolution[1],
                'availWidth': resolution[0],
                'availHeight': resolution[1] - random.choice([0, 40]),  # 任务栏高度
                'colorDepth': random.choice(self.COLOR_DEPTHS),
                'pixelDepth': random.choice(self.COLOR_DEPTHS),
            },
            'navigator': {
                'platform': random.choice(['Win32', 'MacIntel', 'Linux x86_64']),
                'language': random.choice(self.LANGUAGES),
                'languages': random.sample(self.LANGUAGES, k=random.randint(1, 3)),
                'hardwareConcurrency': random.choice(self.HARDWARE_CONCURRENCY),
                'maxTouchPoints': random.choice([0, 1, 10]),
            },
            'timezone': random.choice(self.TIMEZONES),
            'canvas': self._generate_canvas_hash(),
            'webgl': self._generate_webgl_info(),
        }

        return fingerprint

    def _generate_canvas_hash(self):
        """生成 Canvas 指纹哈希"""
        # 模拟 Canvas 指纹 (实际使用时需要真实渲染)
        random_data = f"canvas_{random.randint(100000, 999999)}"
        return hashlib.md5(random_data.encode()).hexdigest()

    def _generate_webgl_info(self):
        """生成 WebGL 指纹信息"""
        vendors = [
            'Google Inc. (NVIDIA)',
            'Google Inc. (AMD)',
            'Google Inc. (Intel)',
        ]

        renderers = [
            'ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)',
            'ANGLE (AMD, AMD Radeon RX 6800 XT Direct3D11 vs_5_0 ps_5_0)',
            'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)',
        ]

        return {
            'vendor': random.choice(vendors),
            'renderer': random.choice(renderers),
        }


def check_captcha(driver):
    """
    检测页面是否存在验证码

    Args:
        driver: Selenium WebDriver 实例

    Returns:
        bool: 是否检测到验证码
    """
    try:
        from selenium.webdriver.common.by import By

        # 常见验证码元素选择器
        captcha_selectors = [
            'div.nc-container',  # 阿里系滑块
            'div.J_MIDDLEWARE',  # 阿里系验证
            'div.geetest_panel',  # 极验
            'iframe[src*="captcha"]',
            'div[class*="captcha"]',
            'div[id*="captcha"]',
            'div[class*="verify"]',
            'div[id*="verify"]',
        ]

        for selector in captcha_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and any(elem.is_displayed() for elem in elements):
                    logger.warning(f"检测到验证码: {selector}")
                    return True
            except Exception:
                continue

        return False

    except Exception as e:
        logger.error(f"验证码检测失败: {e}")
        return False


def generate_track(distance):
    """
    生成滑块拖动轨迹
    模拟人类拖动滑块的行为

    Args:
        distance: 需要拖动的距离

    Returns:
        list: 轨迹点列表 [(x, y, timestamp), ...]
    """
    track = []
    current = 0
    mid = distance * 0.7  # 70% 的距离加速
    t = 0.2  # 时间间隔
    v = 0  # 初速度

    while current < distance:
        if current < mid:
            # 加速阶段
            a = random.uniform(2, 4)
        else:
            # 减速阶段
            a = random.uniform(-3, -1)

        v0 = v
        v = v0 + a * t
        move = v0 * t + 0.5 * a * t * t

        # 确保不超过总距离
        if current + move > distance:
            move = distance - current

        current += move
        track.append((int(current), 0, t))

    # 添加微小抖动
    for _ in range(random.randint(2, 4)):
        track.append((int(current), random.randint(-1, 1), random.uniform(0.1, 0.3)))

    return track


def random_headers():
    """
    生成随机请求头

    Returns:
        dict: 随机请求头
    """
    headers = {
        'Accept': random.choice([
            'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'application/json, text/javascript, */*; q=0.01',
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        ]),
        'Accept-Language': random.choice([
            'zh-CN,zh;q=0.9,en;q=0.8',
            'zh-CN,zh;q=0.9',
            'en-US,en;q=0.9',
        ]),
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    # 随机添加一些头部
    if random.random() > 0.5:
        headers['Cache-Control'] = 'max-age=0'

    if random.random() > 0.5:
        headers['Sec-Fetch-Dest'] = random.choice(['document', 'empty'])
        headers['Sec-Fetch-Mode'] = random.choice(['navigate', 'cors'])
        headers['Sec-Fetch-Site'] = random.choice(['same-origin', 'cross-site', 'none'])

    return headers
