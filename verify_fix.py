# verify_fix.py
"""
验证修复结果
"""
import sys
from pathlib import Path

print("验证导入修复...")

# 1. 验证lesson_processor.py
print("\n1. 验证lesson_processor.py导入...")
try:
    from lesson_processor import LessonProcessor, get_all_lessons_info

    print("✅ lesson_processor.py 导入成功")

    # 检查datetime是否可用
    from datetime import datetime

    print(f"✅ datetime可用: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

except Exception as e:
    print(f"❌ lesson_processor.py导入失败: {e}")
    sys.exit(1)

# 2. 验证downloader.py
print("\n2. 验证downloader.py导入...")
try:
    from downloader import DownloadManager, SimpleDownloader

    print("✅ downloader.py 导入成功")
except Exception as e:
    print(f"❌ downloader.py导入失败: {e}")
    sys.exit(1)

# 3. 验证resource_detector.py
print("\n3. 验证resource_detector.py导入...")
try:
    from resource_detector import ResourceDetector, TabExplorer

    print("✅ resource_detector.py 导入成功")
except Exception as e:
    print(f"❌ resource_detector.py导入失败: {e}")
    sys.exit(1)

# 4. 验证模块间的依赖关系
print("\n4. 验证模块间依赖...")
try:
    # 模拟一个Page对象
    class MockPage:
        def __init__(self):
            self.context = MockContext()


    class MockContext:
        def __init__(self):
            pass


    # 测试ResourceDetector初始化
    mock_page = MockPage()
    detector = ResourceDetector(mock_page)
    print("✅ ResourceDetector 初始化成功")

    # 测试TabExplorer初始化
    explorer = TabExplorer(mock_page)
    print("✅ TabExplorer 初始化成功")

    # 测试DownloadManager初始化
    download_manager = DownloadManager(mock_page, max_concurrent=1)
    print("✅ DownloadManager 初始化成功")

    # 测试SimpleDownloader初始化
    simple_downloader = SimpleDownloader(mock_page)
    print("✅ SimpleDownloader 初始化成功")

except Exception as e:
    print(f"❌ 模块间依赖验证失败: {e}")
    sys.exit(1)

print("\n✅ 所有导入修复验证通过！")
print("\n现在可以运行程序了。")