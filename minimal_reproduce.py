# minimal_reproduce.py - 最小化重现脚本
"""
当出现问题时，创建这个脚本来重现错误。
只包含必要的代码，去除所有无关逻辑。
"""

import sys
import traceback
from pathlib import Path

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from logger import logger
from browser_manager import BrowserManager


def reproduce_error():
    """重现特定的错误"""
    try:
        logger.info("开始最小化错误重现...")

        # 这里只包含出现问题的核心代码
        with BrowserManager(headless=False) as browser:
            # 只测试登录部分
            success = browser.login()
            logger.info(f"登录结果: {success}")

            if success:
                token = browser.get_token()
                logger.info(f"Token获取结果: {bool(token)}")

        logger.info("重现完成")

    except Exception as e:
        logger.error(f"重现过程中出错: {e}", exc_info=True)
        traceback.print_exc()


if __name__ == "__main__":
    reproduce_error()