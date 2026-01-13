# snapshot.py - 自动创建项目快照
import os
import json
import shutil
from pathlib import Path
from datetime import datetime


def create_project_snapshot():
    """创建项目状态快照"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = Path("snapshots") / timestamp
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # 要包含的文件列表
    files_to_copy = [
        "config.py",
        "logger.py",
        "utils.py",
        "browser_manager.py",
        "lesson_processor.py",
        "main.py",
        "collect_courses.py",
        "requirements.txt"
    ]

    # 复制源代码
    for file in files_to_copy:
        if Path(file).exists():
            shutil.copy2(file, snapshot_dir / file)

    # 复制数据文件（如果有）
    data_files = ["courses_data.json", "lessons_info.json"]
    for data_file in data_files:
        if Path(data_file).exists():
            shutil.copy2(data_file, snapshot_dir / data_file)

    # 复制最新日志
    logs_dir = Path("logs")
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.log"))
        if log_files:
            latest_log = max(log_files, key=os.path.getctime)
            shutil.copy2(latest_log, snapshot_dir / "latest.log")

    # 创建项目信息文件
    info = {
        "timestamp": timestamp,
        "python_version": os.popen("python --version").read().strip(),
        "files": files_to_copy,
        "data_files": [f for f in data_files if Path(f).exists()],
        "log_file": str(latest_log) if 'latest_log' in locals() else None
    }

    with open(snapshot_dir / "project_info.json", "w") as f:
        json.dump(info, f, indent=2)

    # 创建压缩包
    shutil.make_archive(f"snapshot_{timestamp}", 'zip', snapshot_dir)

    return f"snapshot_{timestamp}.zip"


if __name__ == "__main__":
    zip_file = create_project_snapshot()
    print(f"✅ 快照已创建: {zip_file}")