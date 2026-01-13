# -*- coding: utf-8 -*-
# @Author : Chris
# @Desc   : 圣通教育资源爬虫 - 主程序入口/核心流程控制
# @Date   : 2026
import os
import sys
from browser_manager import BrowserManager
from lesson_processor import LessonProcessor
from collect_courses import CourseCollector
from utils import init_logger, check_dir
from logger import logger
from config import LOG_DIR, DOWNLOAD_DIR


class ShentongSpider:
    def __init__(self):
        # 初始化目录
        check_dir(LOG_DIR)
        check_dir(DOWNLOAD_DIR)
        # 初始化日志
        init_logger()
        # 初始化核心模块
        self.browser = BrowserManager()
        self.course_collector = CourseCollector(self.browser.driver)
        self.lesson_processor = LessonProcessor(self.browser.driver)
        self.is_login = False

    def run(self):
        """爬虫主运行流程"""
        try:
            logger.info("=" * 50)
            logger.info("🚀 圣通教育资源爬虫V1.0 启动成功")
            logger.info("=" * 50)

            # 1. 自动化登录
            self.is_login = self.browser.login()
            if not self.is_login:
                logger.error("❌ 登录失败，程序终止")
                return

            # 2. 获取所有课程列表
            course_list = self.course_collector.collect_all_courses()
            if not course_list:
                logger.error("❌ 未采集到课程数据，程序终止")
                return

            # 3. 课程选择交互
            logger.info("\n📚 已采集到的课程列表:")
            for idx, course in enumerate(course_list):
                logger.info(f"[{idx + 1}] {course}")

            course_choice = int(input("请选择课程序号: ")) - 1
            if course_choice < 0 or course_choice >= len(course_list):
                logger.error("❌ 课程选择无效")
                return
            selected_course = course_list[course_choice]
            self.lesson_processor.course_name = selected_course
            logger.info(f"✅ 已选择课程: {selected_course}")

            # 4. 进入课程详情 & 获取课时列表
            self.course_collector.enter_course_detail(selected_course)
            lesson_list = self.lesson_processor.get_lesson_list()
            if not lesson_list:
                logger.error("❌ 该课程无课时数据")
                return

            # 5. 课时范围选择交互
            logger.info("\n📖 该课程课时列表:")
            for idx, lesson in enumerate(lesson_list):
                logger.info(f"[{idx + 1}] {lesson}")

            start_lesson = int(input("请选择起始课时序号: ")) - 1
            end_lesson = int(input("请选择结束课时序号: ")) - 1
            selected_lessons = self.lesson_processor.select_lesson_range(start_lesson, end_lesson)
            if not selected_lessons:
                logger.error("❌ 课时范围选择无效")
                return

            # 6. 遍历课时 & 资源侦察
            logger.info(f"\n🔍 开始处理 {len(selected_lessons)} 个课时的资源侦察")
            for lesson in selected_lessons:
                logger.info("-" * 30)
                enter_ok = self.lesson_processor.enter_lesson_detail(lesson)
                if not enter_ok:
                    logger.warning(f"⚠️ 跳过课时: {lesson}")
                    continue

                # ========== 这里是你调用资源探索方法的位置 ==========
                # 你源码里的写法是调用原方法，我已在lesson_processor.py中替换为新方法
                self.lesson_processor.explore_all_valid_resource_tabs()

            logger.info("=" * 50)
            logger.info("🎉 所有课时处理完成，程序运行结束")
            logger.info("=" * 50)

        except KeyboardInterrupt:
            logger.info("\nℹ️ 用户手动终止程序")
        except Exception as e:
            logger.error(f"❌ 程序主流程异常: {str(e)}", exc_info=True)
        finally:
            # 关闭浏览器
            self.browser.quit()
            sys.exit(0)


if __name__ == "__main__":
    spider = ShentongSpider()
    spider.run()