# test_download.py
"""
测试下载功能
"""
import time
from pathlib import Path
from browser_manager import BrowserManager
from resource_detector import TabExplorer, ResourceDetector
from downloader import DownloadManager
from logger import logger


def test_resource_detection():
    """测试资源检测功能"""
    logger.separator("测试资源检测")

    with BrowserManager(headless=False) as browser:
        # 登录
        logger.info("登录系统...")
        if not browser.login():
            logger.error("登录失败")
            return

        # 导航到课程管理页面
        logger.info("导航到课程管理页面...")
        if not browser.navigate_to_course_management():
            logger.error("导航失败")
            return

        # 等待页面加载
        time.sleep(5)

        # 创建资源检测器
        detector = ResourceDetector(browser.page)

        # 测试获取当前Tab层级
        tab_hierarchy = detector.get_current_tab_hierarchy()
        logger.info(f"当前Tab层级: {tab_hierarchy}")

        # 测试在当前Tab中检测资源
        resources = detector.detect_resources_in_tab(tab_hierarchy)
        logger.info(f"检测到 {len(resources)} 个资源")

        for i, resource in enumerate(resources[:5], 1):
            logger.info(f"资源 {i}:")
            logger.info(f"  类型: {resource.get('resource_type')}")
            logger.info(f"  文件名: {resource.get('file_name')}")
            logger.info(f"  下载方式: {resource.get('download_method')}")
            logger.info(f"  选择器: {resource.get('selector')}")

        return len(resources) > 0


def test_tab_explorer():
    """测试Tab探索器"""
    logger.separator("测试Tab探索器")

    with BrowserManager(headless=False) as browser:
        # 登录
        logger.info("登录系统...")
        if not browser.login():
            logger.error("登录失败")
            return

        # 导航到课程管理页面
        logger.info("导航到课程管理页面...")
        if not browser.navigate_to_course_management():
            logger.error("导航失败")
            return

        # 等待页面加载
        time.sleep(5)

        # 创建Tab探索器
        explorer = TabExplorer(browser.page)

        # 探索所有Tab
        all_resources = explorer.explore_all_tabs()

        logger.info(f"探索完成，发现 {len(all_resources)} 个Tab")

        for tab_path, resources in all_resources.items():
            logger.info(f"Tab: {tab_path}")
            logger.info(f"  资源数量: {len(resources)}")

            # 统计资源类型
            type_count = {}
            for resource in resources:
                rtype = resource.get("resource_type", "unknown")
                type_count[rtype] = type_count.get(rtype, 0) + 1

            for rtype, count in type_count.items():
                logger.info(f"    {rtype}: {count} 个")

        return len(all_resources) > 0


def test_download_manager():
    """测试下载管理器"""
    logger.separator("测试下载管理器")

    with BrowserManager(headless=False) as browser:
        # 登录
        logger.info("登录系统...")
        if not browser.login():
            logger.error("登录失败")
            return

        # 导航到课程管理页面
        logger.info("导航到课程管理页面...")
        if not browser.navigate_to_course_management():
            logger.error("导航失败")
            return

        # 等待页面加载
        time.sleep(5)

        # 创建下载管理器
        download_manager = DownloadManager(browser.page, max_concurrent=1)

        try:
            # 启动下载管理器
            download_manager.start()

            # 创建测试任务
            test_tasks = [
                {
                    "resource_type": "pdf",
                    "resource_name": "测试PDF",
                    "file_name": "测试文件.pdf",
                    "download_method": "preview_pdf",
                    "selector": "text='测试预览按钮'",  # 需要根据实际页面调整
                    "tab_path": ["课前预习", "资料"],
                    "lesson_info": {
                        "course_name": "测试课程",
                        "session_num": 1,
                        "session_name": "测试课时"
                    }
                }
            ]

            # 添加任务
            task_ids = download_manager.add_batch_tasks(test_tasks)
            logger.info(f"添加了 {len(task_ids)} 个测试任务")

            # 等待下载完成
            download_manager.wait_for_completion(timeout=30)

            # 获取统计信息
            stats = download_manager.get_stats()
            logger.info(f"下载统计: {stats}")

            return stats['completed'] > 0

        finally:
            # 停止下载管理器
            download_manager.stop()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "detect":
            success = test_resource_detection()
        elif test_name == "explore":
            success = test_tab_explorer()
        elif test_name == "download":
            success = test_download_manager()
        else:
            logger.error(f"未知测试: {test_name}")
            sys.exit(1)
    else:
        # 默认运行所有测试
        logger.info("运行所有测试...")
        success1 = test_resource_detection()
        if success1:
            success2 = test_tab_explorer()
        else:
            success2 = False

        logger.info(f"测试结果: 检测测试 {'通过' if success1 else '失败'}, "
                    f"探索测试 {'通过' if success2 else '失败'}")