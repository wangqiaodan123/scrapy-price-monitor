"""
电商价格监控系统 - 主程序入口
支持定时调度多个爬虫任务
"""

import os
import sys
import time
import logging
import argparse
import yaml
from pathlib import Path
from datetime import datetime
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/main.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 确保日志目录存在
os.makedirs('logs', exist_ok=True)


def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_spider(spider_name, keyword=None, max_pages=None):
    """
    运行指定爬虫

    Args:
        spider_name: 爬虫名称 (jd/taobao/suning)
        keyword: 搜索关键词
        max_pages: 最大页数
    """
    logger.info(f"启动爬虫: {spider_name}, 关键词: {keyword}, 最大页数: {max_pages}")

    try:
        # 获取 Scrapy 配置
        settings = get_project_settings()

        # 创建爬虫进程
        process = CrawlerProcess(settings)

        # 构建爬虫参数
        spider_kwargs = {}
        if keyword:
            spider_kwargs['keyword'] = keyword
        if max_pages:
            spider_kwargs['max_pages'] = max_pages

        # 启动爬虫
        process.crawl(spider_name, **spider_kwargs)
        process.start()

        logger.info(f"爬虫 {spider_name} 执行完成")

    except Exception as e:
        logger.error(f"爬虫 {spider_name} 执行失败: {e}", exc_info=True)


def run_all_spiders(config):
    """
    运行所有启用的爬虫

    Args:
        config: 配置字典
    """
    platforms = config.get('platforms', {})

    for platform_name, platform_config in platforms.items():
        if not platform_config.get('enabled', False):
            logger.info(f"平台 {platform_name} 未启用，跳过")
            continue

        keywords = platform_config.get('keywords', [])
        max_pages = platform_config.get('max_pages', 10)

        # 映射平台名到爬虫名
        spider_name_map = {
            'jd': 'jd',
            'taobao': 'taobao',
            'suning': 'suning'
        }

        spider_name = spider_name_map.get(platform_name)
        if not spider_name:
            logger.warning(f"未找到平台 {platform_name} 对应的爬虫")
            continue

        # 对每个关键词运行爬虫
        for keyword in keywords:
            logger.info(f"采集 {platform_name} 平台，关键词: {keyword}")
            run_spider(spider_name, keyword=keyword, max_pages=max_pages)

            # 爬虫之间添加延迟
            time.sleep(5)


def run_scheduled(config):
    """
    运行定时任务调度器

    Args:
        config: 配置字典
    """
    import schedule

    logger.info("启动定时任务调度器...")

    schedule_config = config.get('schedule', {})

    # 京东定时任务
    jd_interval = schedule_config.get('jd_interval_hours', 2)
    schedule.every(jd_interval).hours.do(
        lambda: run_spider('jd', keyword='手机', max_pages=5)
    )
    logger.info(f"京东爬虫已调度: 每 {jd_interval} 小时执行")

    # 淘宝定时任务
    taobao_interval = schedule_config.get('taobao_interval_hours', 4)
    schedule.every(taobao_interval).hours.do(
        lambda: run_spider('taobao', keyword='笔记本', max_pages=3)
    )
    logger.info(f"淘宝爬虫已调度: 每 {taobao_interval} 小时执行")

    # 苏宁定时任务
    suning_interval = schedule_config.get('suning_interval_hours', 3)
    schedule.every(suning_interval).hours.do(
        lambda: run_spider('suning', keyword='耳机', max_pages=5)
    )
    logger.info(f"苏宁爬虫已调度: 每 {suning_interval} 小时执行")

    # 价格分析任务
    analysis_time = schedule_config.get('analysis_time', '02:00')
    schedule.every().day.at(analysis_time).do(run_analysis)
    logger.info(f"价格分析任务已调度: 每天 {analysis_time} 执行")

    # 运行调度器
    logger.info("定时任务调度器已启动，按 Ctrl+C 停止")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logger.info("调度器已停止")


def run_analysis():
    """运行价格分析"""
    logger.info("启动价格分析...")

    try:
        from analysis import PriceAnalyzer

        analyzer = PriceAnalyzer()
        report = analyzer.generate_report()

        logger.info(f"价格分析完成，生成报告: {report}")

    except Exception as e:
        logger.error(f"价格分析失败: {e}", exc_info=True)


def init_database():
    """初始化数据库"""
    logger.info("初始化数据库...")

    try:
        from price_monitor.utils.db_helper import init_mysql_tables, init_mongodb_collections

        init_mysql_tables()
        init_mongodb_collections()

        logger.info("数据库初始化完成")

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='电商价格监控系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --spider jd --keyword 手机 --pages 5
  python main.py --all
  python main.py --schedule
  python main.py --init-db
        """
    )

    parser.add_argument('--spider', type=str, help='运行指定爬虫 (jd/taobao/suning)')
    parser.add_argument('--keyword', type=str, help='搜索关键词')
    parser.add_argument('--pages', type=int, help='最大页数')
    parser.add_argument('--all', action='store_true', help='运行所有爬虫')
    parser.add_argument('--schedule', action='store_true', help='启动定时任务调度')
    parser.add_argument('--init-db', action='store_true', help='初始化数据库')
    parser.add_argument('--analysis', action='store_true', help='运行价格分析')

    args = parser.parse_args()

    # 加载配置
    config = load_config()

    # 初始化数据库
    if args.init_db:
        init_database()
        return

    # 运行价格分析
    if args.analysis:
        run_analysis()
        return

    # 启动定时调度
    if args.schedule:
        run_scheduled(config)
        return

    # 运行所有爬虫
    if args.all:
        run_all_spiders(config)
        return

    # 运行指定爬虫
    if args.spider:
        run_spider(args.spider, keyword=args.keyword, max_pages=args.pages)
        return

    # 默认: 显示帮助信息
    parser.print_help()


if __name__ == '__main__':
    main()
