# collect_courses.py
"""
独立脚本：用于收集和保存课程数据到本地JSON文件
"""
import time
import json
from pathlib import Path
from config import Config
from logger import logger
from browser_manager import BrowserManager
from utils import APIUtils, FileUtils


def collect_courses_data():
    """收集并保存课程数据"""
    logger.separator("课程数据收集工具")

    try:
        # 1. 启动浏览器并登录
        with BrowserManager(headless=False) as browser:
            logger.progress("开始登录流程...")

            if not browser.login():
                logger.error("登录失败")
                return

            if not browser.navigate_to_course_management():
                logger.error("导航到课程管理页面失败")
                return

            # 2. 获取Token
            token = browser.get_token()
            if not token:
                logger.error("获取Token失败")
                return

            logger.success("登录成功，Token已获取")

            # 3. 通过API获取所有课程
            logger.progress("开始收集课程数据...")
            courses_data = APIUtils.get_all_courses(token)

            if not courses_data:
                logger.error("未能获取任何课程数据")
                return

            # 4. 保存课程数据
            logger.progress("保存课程数据到文件...")

            if FileUtils.save_json(courses_data, Config.COURSES_DATA_FILE):
                logger.success(f"课程数据收集完成，共 {len(courses_data)} 门课程")
                logger.success(f"数据已保存到: {Config.COURSES_DATA_FILE}")

                # 显示课程列表
                logger.separator("课程列表")
                for i, course in enumerate(courses_data[:10], 1):  # 只显示前10个
                    course_name = course.get('courseName', '未知课程')
                    course_id = course.get('id', '未知ID')
                    logger.info(f"{i:2d}. {course_name} (ID: {course_id})")

                if len(courses_data) > 10:
                    logger.info(f"... 还有 {len(courses_data) - 10} 门课程未显示")

            else:
                logger.error("保存课程数据失败")

            # 保持浏览器打开
            logger.info("\n按回车键关闭浏览器...")
            input()

    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序运行出错: {e}", exc_info=True)
    finally:
        logger.info("程序结束")


def load_and_display_courses():
    """加载并显示已保存的课程数据"""
    logger.separator("课程数据查看工具")

    courses_data = FileUtils.load_json(Config.COURSES_DATA_FILE)
    if not courses_data:
        logger.error("没有可用的课程数据")
        return

    logger.success(f"成功加载 {len(courses_data)} 门课程")

    # 显示课程统计
    logger.separator("课程统计")

    # 按课程类型统计
    course_types = {}
    for course in courses_data:
        course_type = course.get('courseType', '未知类型')
        course_types[course_type] = course_types.get(course_type, 0) + 1

    logger.info("课程类型分布:")
    for ctype, count in course_types.items():
        logger.info(f"  {ctype}: {count}门")

    # 显示课程详情
    logger.separator("课程详情")
    for i, course in enumerate(courses_data[:20], 1):  # 只显示前20个
        course_name = course.get('courseName', '未知课程')
        course_id = course.get('id', '未知ID')
        course_code = course.get('courseCode', '未知编码')
        unit_num = course.get('unitNum', 0)
        session_num = course.get('sessionNum', 0)

        logger.info(f"{i:2d}. {course_name}")
        logger.info(f"     课程ID: {course_id} | 编码: {course_code[:20]}...")
        logger.info(f"     单元: {unit_num}个 | 课时: {session_num}节")

        if i % 5 == 0:  # 每5个课程加一个分隔
            logger.info("-" * 60)

    if len(courses_data) > 20:
        logger.info(f"... 还有 {len(courses_data) - 20} 门课程未显示")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'collect':
        # 收集课程数据
        collect_courses_data()
    elif len(sys.argv) > 1 and sys.argv[1] == 'view':
        # 查看已保存的课程数据
        load_and_display_courses()
    else:
        # 默认执行收集
        collect_courses_data()