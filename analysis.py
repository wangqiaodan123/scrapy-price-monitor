"""
价格分析模块
提供价格统计、趋势分析、图表生成、报告导出等功能
"""

import os
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# 配置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class PriceAnalyzer:
    """
    价格分析器
    提供价格数据统计、趋势分析和可视化功能
    """

    def __init__(self, db_source='mysql'):
        """
        初始化分析器

        Args:
            db_source: 数据源 ('mysql' 或 'mongodb')
        """
        self.db_source = db_source
        self.output_dir = Path('./data/reports')
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据库连接
        if db_source == 'mysql':
            from price_monitor.utils.db_helper import get_mysql_helper
            self.db = get_mysql_helper()
        else:
            from price_monitor.utils.db_helper import get_mongodb_helper
            self.db = get_mongodb_helper()

    def get_price_data(self, platform=None, keyword=None, days=30):
        """
        获取价格数据

        Args:
            platform: 平台筛选
            keyword: 关键词筛选
            days: 查询天数

        Returns:
            DataFrame: 价格数据
        """
        if self.db_source == 'mysql':
            data = self.db.query_products(platform=platform, keyword=keyword, limit=10000)
        else:
            data = self.db.query_products(platform=platform, keyword=keyword, limit=10000)

        if not data:
            logger.warning("未查询到数据")
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # 转换时间字段
        if 'crawl_time' in df.columns:
            df['crawl_time'] = pd.to_datetime(df['crawl_time'])

        if 'update_time' in df.columns:
            df['update_time'] = pd.to_datetime(df['update_time'])

        # 转换价格字段
        if 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce')

        if 'original_price' in df.columns:
            df['original_price'] = pd.to_numeric(df['original_price'], errors='coerce')

        return df

    def get_price_history(self, product_id, platform, days=30):
        """
        获取商品历史价格

        Args:
            product_id: 商品ID
            platform: 平台
            days: 查询天数

        Returns:
            DataFrame: 价格历史数据
        """
        if self.db_source == 'mysql':
            data = self.db.query_price_history(product_id, platform, days)
        else:
            data = self.db.query_price_history(product_id, platform, days)

        if not data:
            logger.warning(f"未查询到商品 {product_id} 的价格历史")
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # 转换时间字段
        if 'record_time' in df.columns:
            df['record_time'] = pd.to_datetime(df['record_time'])

        # 转换价格字段
        for col in ['price', 'original_price', 'price_change', 'price_change_pct']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    def calculate_statistics(self, df):
        """
        计算价格统计信息

        Args:
            df: 价格数据 DataFrame

        Returns:
            dict: 统计结果
        """
        if df.empty:
            return {}

        stats = {
            'total_products': len(df),
            'avg_price': df['price'].mean(),
            'median_price': df['price'].median(),
            'min_price': df['price'].min(),
            'max_price': df['price'].max(),
            'std_price': df['price'].std(),
        }

        # 按平台统计
        if 'platform' in df.columns:
            platform_stats = df.groupby('platform').agg({
                'price': ['count', 'mean', 'median', 'min', 'max']
            }).round(2)
            stats['by_platform'] = platform_stats.to_dict()

        # 按关键词统计
        if 'keyword' in df.columns:
            keyword_stats = df.groupby('keyword').agg({
                'price': ['count', 'mean', 'median']
            }).round(2)
            stats['by_keyword'] = keyword_stats.to_dict()

        return stats

    def plot_price_trend(self, product_id, platform, days=30, save_path=None):
        """
        绘制价格趋势图

        Args:
            product_id: 商品ID
            platform: 平台
            days: 查询天数
            save_path: 保存路径
        """
        df = self.get_price_history(product_id, platform, days)

        if df.empty:
            logger.warning(f"无法绘制趋势图: 商品 {product_id} 无数据")
            return

        fig, ax = plt.subplots(figsize=(12, 6))

        # 绘制价格曲线
        ax.plot(df['record_time'], df['price'], marker='o', linewidth=2,
                markersize=4, label='当前价格', color='#2196F3')

        # 绘制原价曲线 (如果有)
        if 'original_price' in df.columns and df['original_price'].notna().any():
            ax.plot(df['record_time'], df['original_price'], linestyle='--',
                    linewidth=1, alpha=0.6, label='原价', color='#9E9E9E')

        # 设置标题和标签
        product_name = df.iloc[0].get('name', product_id)
        ax.set_title(f'{product_name[:50]} - 价格趋势 (最近{days}天)', fontsize=14, fontweight='bold')
        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('价格 (¥)', fontsize=12)

        # 格式化 X 轴
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
        plt.xticks(rotation=45)

        # 添加网格
        ax.grid(True, alpha=0.3, linestyle='--')

        # 添加图例
        ax.legend(loc='best')

        # 标注价格变化
        if 'price_change' in df.columns:
            for idx, row in df.iterrows():
                if pd.notna(row['price_change']) and abs(row['price_change']) > 0:
                    color = 'red' if row['price_change'] > 0 else 'green'
                    ax.annotate(
                        f"{row['price_change']:+.2f}",
                        xy=(row['record_time'], row['price']),
                        xytext=(10, 10),
                        textcoords='offset points',
                        fontsize=8,
                        color=color
                    )

        plt.tight_layout()

        # 保存图片
        if not save_path:
            save_path = self.output_dir / f'price_trend_{product_id}_{platform}.png'

        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info(f"价格趋势图已保存: {save_path}")
        plt.close()

    def plot_platform_comparison(self, keyword=None, days=7, save_path=None):
        """
        绘制平台价格对比图

        Args:
            keyword: 关键词筛选
            days: 查询天数
            save_path: 保存路径
        """
        df = self.get_price_data(keyword=keyword, days=days)

        if df.empty:
            logger.warning("无法绘制对比图: 无数据")
            return

        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        # 左图: 平台价格箱线图
        if 'platform' in df.columns:
            df.boxplot(column='price', by='platform', ax=axes[0])
            axes[0].set_title(f'各平台价格分布 (关键词: {keyword or "全部"})', fontsize=12, fontweight='bold')
            axes[0].set_xlabel('平台', fontsize=11)
            axes[0].set_ylabel('价格 (¥)', fontsize=11)

        # 右图: 平台商品数量柱状图
        if 'platform' in df.columns:
            platform_counts = df['platform'].value_counts()
            platform_counts.plot(kind='bar', ax=axes[1], color=['#2196F3', '#4CAF50', '#FF9800'])
            axes[1].set_title('各平台商品数量', fontsize=12, fontweight='bold')
            axes[1].set_xlabel('平台', fontsize=11)
            axes[1].set_ylabel('商品数量', fontsize=11)
            axes[1].tick_params(axis='x', rotation=0)

            # 在柱子上添加数值
            for i, v in enumerate(platform_counts.values):
                axes[1].text(i, v + 0.5, str(v), ha='center', fontweight='bold')

        plt.tight_layout()

        # 保存图片
        if not save_path:
            save_path = self.output_dir / f'platform_comparison_{keyword or "all"}.png'

        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info(f"平台对比图已保存: {save_path}")
        plt.close()

    def plot_price_distribution(self, platform=None, keyword=None, save_path=None):
        """
        绘制价格分布直方图

        Args:
            platform: 平台筛选
            keyword: 关键词筛选
            save_path: 保存路径
        """
        df = self.get_price_data(platform=platform, keyword=keyword)

        if df.empty:
            logger.warning("无法绘制分布图: 无数据")
            return

        fig, ax = plt.subplots(figsize=(12, 6))

        # 绘制价格分布
        df['price'].plot(kind='hist', bins=30, ax=ax, color='#2196F3', alpha=0.7, edgecolor='black')

        # 添加均值和中位数线
        mean_price = df['price'].mean()
        median_price = df['price'].median()

        ax.axvline(mean_price, color='red', linestyle='--', linewidth=2, label=f'均值: ¥{mean_price:.2f}')
        ax.axvline(median_price, color='green', linestyle='--', linewidth=2, label=f'中位数: ¥{median_price:.2f}')

        # 设置标题和标签
        title = '价格分布'
        if platform:
            title += f' - {platform}平台'
        if keyword:
            title += f' - {keyword}'
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('价格 (¥)', fontsize=12)
        ax.set_ylabel('商品数量', fontsize=12)

        # 添加图例
        ax.legend(loc='best')

        # 添加网格
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        # 保存图片
        if not save_path:
            save_path = self.output_dir / f'price_distribution_{platform or "all"}_{keyword or "all"}.png'

        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info(f"价格分布图已保存: {save_path}")
        plt.close()

    def export_csv_report(self, df, filename=None):
        """
        导出数据为 CSV 报告

        Args:
            df: 数据 DataFrame
            filename: 文件名
        """
        if df.empty:
            logger.warning("无法导出报告: 无数据")
            return None

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'price_report_{timestamp}.csv'

        save_path = self.output_dir / filename

        df.to_csv(save_path, index=False, encoding='utf-8-sig')
        logger.info(f"CSV 报告已导出: {save_path}")

        return save_path

    def generate_report(self, platform=None, keyword=None, days=30):
        """
        生成完整的分析报告

        Args:
            platform: 平台筛选
            keyword: 关键词筛选
            days: 查询天数

        Returns:
            str: 报告文件路径
        """
        logger.info(f"生成分析报告: 平台={platform}, 关键词={keyword}, 天数={days}")

        # 获取数据
        df = self.get_price_data(platform=platform, keyword=keyword, days=days)

        if df.empty:
            logger.error("无法生成报告: 无数据")
            return None

        # 计算统计信息
        stats = self.calculate_statistics(df)
        logger.info(f"统计结果: {stats}")

        # 生成图表
        self.plot_price_distribution(platform=platform, keyword=keyword)

        if keyword:
            self.plot_platform_comparison(keyword=keyword, days=days)

        # 导出 CSV
        csv_path = self.export_csv_report(df)

        # 生成文本报告
        report_path = self.output_dir / f'analysis_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("电商商品价格分析报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            f.write("【基本统计】\n")
            f.write(f"  商品总数: {stats['total_products']}\n")
            f.write(f"  平均价格: ¥{stats['avg_price']:.2f}\n")
            f.write(f"  中位价格: ¥{stats['median_price']:.2f}\n")
            f.write(f"  最低价格: ¥{stats['min_price']:.2f}\n")
            f.write(f"  最高价格: ¥{stats['max_price']:.2f}\n")
            f.write(f"  价格标准差: ¥{stats['std_price']:.2f}\n\n")

            if 'by_platform' in stats:
                f.write("【平台统计】\n")
                f.write(str(stats['by_platform']))
                f.write("\n\n")

            if 'by_keyword' in stats:
                f.write("【关键词统计】\n")
                f.write(str(stats['by_keyword']))
                f.write("\n\n")

        logger.info(f"分析报告已生成: {report_path}")
        return str(report_path)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='价格分析工具')
    parser.add_argument('--platform', type=str, help='平台筛选 (jd/taobao/suning)')
    parser.add_argument('--keyword', type=str, help='关键词筛选')
    parser.add_argument('--days', type=int, default=30, help='查询天数 (默认30)')
    parser.add_argument('--product-id', type=str, help='商品ID (用于趋势分析)')
    parser.add_argument('--trend', action='store_true', help='生成价格趋势图')
    parser.add_argument('--export', type=str, choices=['csv', 'report'], help='导出格式')
    parser.add_argument('--output', type=str, help='输出文件路径')

    args = parser.parse_args()

    analyzer = PriceAnalyzer()

    if args.trend and args.product_id:
        # 生成单个商品的趋势图
        platform = args.platform or 'jd'
        analyzer.plot_price_trend(args.product_id, platform, args.days, args.output)

    elif args.export == 'csv':
        # 导出 CSV
        df = analyzer.get_price_data(args.platform, args.keyword, args.days)
        analyzer.export_csv_report(df, args.output)

    elif args.export == 'report':
        # 生成完整报告
        analyzer.generate_report(args.platform, args.keyword, args.days)

    else:
        # 默认: 生成完整报告
        analyzer.generate_report(args.platform, args.keyword, args.days)


if __name__ == '__main__':
    main()
