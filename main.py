# main.py
import time
import signal
from pathlib import Path
from typing import Optional
from config import Config
from logger import logger
from utils import FileUtils, UserInputUtils
from browser_manager import BrowserManager
from lesson_processor import LessonProcessor, get_all_lessons_info


def signal_handler(sig, frame):
    """处理中断信号"""
    logger.warning("程序被用户中断，正在优雅退出...")
    exit(0)


def load_course_data() -> Optional[list]:
    """从本地文件加载课程数据"""
    logger.progress("从本地文件加载课程数据...")

    if not Config.COURSES_DATA_FILE.exists():
        logger.error(f"课程数据文件不存在: {Config.COURSES_DATA_FILE}")
        logger.info("请先运行课程数据收集脚本或确保文件存在")
        return None

    courses_data = FileUtils.load_json(Config.COURSES_DATA_FILE)
    if not courses_data:
        logger.error("加载课程数据失败")
        return None

    logger.success(f"成功加载 {len(courses_data)} 门课程")
    return courses_data


def save_lessons_info(lessons_info: list):
    """保存课时信息到文件"""
    if FileUtils.save_json(lessons_info, Config.LESSONS_INFO_FILE):
        logger.success(f"课时信息已保存到: {Config.LESSONS_INFO_FILE}")
    else:
        logger.error("保存课时信息失败")


def main():
    """主函数"""
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)

    logger.separator("圣通教育资源下载工具")

    try:
        # 1. 从本地文件加载课程数据
        courses_data = load_course_data()
        if not courses_data:
            return

        # 2. 用户选择课程
        selected_course = UserInputUtils.select_course(courses_data)
        if not selected_course:
            return
        # 3. 启动浏览器并登录
        with BrowserManager(headless=False) as browser:
            if not browser.login():
                logger.error("登录失败，程序退出")
                return

            if not browser.navigate_to_course_management():
                logger.error("导航到课程管理页面失败，程序退出")
                return

            # 4. 从本地加载课程数据并选择课程（浏览器已打开）
            courses_data = load_course_data()
            if not courses_data:
                return

            # ⭐⭐ 在浏览器打开的情况下选择课程 ⭐⭐
            selected_course = UserInputUtils.select_course(courses_data)
            if not selected_course:
                return

            course_name = selected_course.get("courseName", "未命名课程")
            course_code = selected_course.get("courseCode")

            if not course_code:
                logger.error("无法获取课程编码")
                return

            # 5. ⭐⭐ 关键：点击课程进入课程详情页 ⭐⭐
            logger.progress(f"进入课程详情页: {course_name}")

            # 确保在课程详情页
            if not browser.ensure_in_course_detail_page(course_name):
                logger.error("进入课程详情页失败，程序退出")
                return

            # 6. 获取Token（现在我们在课程详情页）
            token = browser.get_token()
            if not token:
                logger.error("获取Token失败，程序退出")
                return

            # 7. 获取课程的所有课时信息（使用API）
            logger.progress("获取课程课时信息...")
            lessons_info = get_all_lessons_info(selected_course, token)
            if not lessons_info:
                logger.error("获取课时信息失败，程序退出")
                return

            # 8. 保存课时信息
            save_lessons_info(lessons_info)

            # 9. 用户选择要处理的课时
            selected_lessons = UserInputUtils.select_lessons(lessons_info)
            if not selected_lessons:
                logger.info("没有选择任何课时，程序退出")
                return

            # 10. 创建下载目录
            download_base = Config.DOWNLOAD_BASE_DIR / course_name
            FileUtils.ensure_directory(download_base)

            # 11. 初始化课时处理器
            processor = LessonProcessor(browser.page, download_base)

            # 12. 处理选中的课时
            total_lessons = len(selected_lessons)
            logger.separator(f"开始处理课时 ({total_lessons}个)")

            for i, lesson_info in enumerate(selected_lessons, 1):
                logger.progress(f"处理进度: {i}/{total_lessons}")
                success = processor.process_lesson(lesson_info)
                if not success:
                    logger.warning(f"课时 {lesson_info['session_name']} 处理失败")
                time.sleep(Config.CLICK_WAIT)

            logger.separator("任务完成")
            logger.success(f"资源下载任务已完成！")
            logger.success(f"资源保存在: {download_base.absolute()}")

            # 保持浏览器打开
            logger.info("\n浏览器将保持打开状态，按回车键关闭...")
            input()


    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序运行出错: {e}", exc_info=True)
    finally:
        logger.info("程序结束")


if __name__ == '__main__':
    # 检查并安装依赖
    try:
        import playwright
    except ImportError:
        logger.warning("正在安装playwright依赖...")
        import subprocess
        import sys

        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'playwright'])
        subprocess.check_call([sys.executable, '-m', 'playwright', 'install'])

    main()