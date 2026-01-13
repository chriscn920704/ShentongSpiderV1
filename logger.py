# logger.py
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class ShengTongLogger:
    """圣通教育爬虫日志系统"""

    def __init__(self, name: str = "shengtong_spider", log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 避免重复添加handler
        if not self.logger.handlers:
            self._setup_handlers(log_dir)

    def _setup_handlers(self, log_dir: str):
        """设置日志处理器"""
        # 创建日志目录
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

        # 日志文件名（按日期）
        log_file = log_path / f"shengtong_{datetime.now().strftime('%Y%m%d')}.log"

        # 1. 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)

        # 2. 文件处理器（详细日志）
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)

        # 添加处理器
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def info(self, message: str, **kwargs):
        """信息日志"""
        if kwargs:
            self.logger.info(f"{message} | {kwargs}")
        else:
            self.logger.info(message)

    def warning(self, message: str, **kwargs):
        """警告日志"""
        if kwargs:
            self.logger.warning(f"{message} | {kwargs}")
        else:
            self.logger.warning(message)

    def error(self, message: str, exc_info: Optional[bool] = False, **kwargs):
        """错误日志"""
        if kwargs:
            self.logger.error(f"{message} | {kwargs}", exc_info=exc_info)
        else:
            self.logger.error(message, exc_info=exc_info)

    def debug(self, message: str, **kwargs):
        """调试日志"""
        if kwargs:
            self.logger.debug(f"{message} | {kwargs}")
        else:
            self.logger.debug(message)

    def success(self, message: str, **kwargs):
        """成功日志（自定义级别）"""
        if kwargs:
            self.logger.info(f"✅ {message} | {kwargs}")
        else:
            self.logger.info(f"✅ {message}")

    def progress(self, message: str, **kwargs):
        """进度日志"""
        if kwargs:
            self.logger.info(f"🔄 {message} | {kwargs}")
        else:
            self.logger.info(f"🔄 {message}")

    def separator(self, title: Optional[str] = None):
        """分隔线日志"""
        line = "=" * 60
        if title:
            self.logger.info(f"\n{line}\n{title.center(60)}\n{line}")
        else:
            self.logger.info(f"\n{line}")


# 全局日志实例
logger = ShengTongLogger()