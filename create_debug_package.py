### 3. **创建调试包脚本**
#python
# create_debug_package.py
"""
自动创建调试包，包含所有必要信息
"""

import json
import shutil
import traceback
from pathlib import Path
from datetime import datetime
import subprocess


class DebugPackageCreator:
    def __init__(self, issue_description=""):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.package_dir = Path(f"debug_package_{self.timestamp}")
        self.issue_description = issue_description

    def create(self):
        """创建调试包"""
        self.package_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. 收集基本信息
            self._collect_system_info()

            # 2. 复制源代码
            self._collect_source_code()

            # 3. 复制数据文件
            self._collect_data_files()

            # 4. 收集日志
            self._collect_logs()

            # 5. 创建问题描述
            self._create_issue_file()

            # 6. 创建压缩包
            zip_path = self._create_zip()

            print(f"✅ 调试包已创建: {zip_path}")
            print(f"📦 包含以下内容:")
            for item in self.package_dir.rglob("*"):
                if item.is_file():
                    print(f"   - {item.relative_to(self.package_dir)}")

            return zip_path

        except Exception as e:
            print(f"❌ 创建调试包失败: {e}")
            traceback.print_exc()
            return None

    def _collect_system_info(self):
        """收集系统信息"""
        info = {
            "timestamp": self.timestamp,
            "issue_description": self.issue_description,
            "python_version": self._get_python_version(),
            "pip_freeze": self._get_pip_freeze(),
            "platform": self._get_platform_info()
        }

        with open(self.package_dir / "system_info.json", "w") as f:
            json.dump(info, f, indent=2)

    def _get_python_version(self):
        try:
            import platform
            return platform.python_version()
        except:
            return "未知"

    def _get_pip_freeze(self):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True, text=True
            )
            return result.stdout
        except:
            return "无法获取"

    def _get_platform_info(self):
        import platform
        return {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine()
        }

    def _collect_source_code(self):
        """收集源代码"""
        source_files = [
            "config.py", "logger.py", "utils.py",
            "browser_manager.py", "lesson_processor.py",
            "main.py", "collect_courses.py"
        ]

        for file in source_files:
            if Path(file).exists():
                shutil.copy2(file, self.package_dir / file)

    def _collect_data_files(self):
        """收集数据文件"""
        data_files = ["courses_data.json", "lessons_info.json"]
        for file in data_files:
            if Path(file).exists():
                # 只复制前几行，避免文件过大
                self._copy_partial_json(file, self.package_dir / file, max_items=5)

    def _copy_partial_json(self, src, dst, max_items=5):
        """复制JSON文件的部分内容"""
        try:
            with open(src, 'r') as f:
                data = json.load(f)

            if isinstance(data, list) and len(data) > max_items:
                data = data[:max_items]
                data.append(f"... 还有 {len(data)} 项未显示")

            with open(dst, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except:
            shutil.copy2(src, dst)

    def _collect_logs(self):
        """收集日志"""
        logs_dir = Path("logs")
        if logs_dir.exists():
            # 复制最新的3个日志文件
            log_files = sorted(logs_dir.glob("*.log"),
                               key=lambda x: x.stat().st_mtime,
                               reverse=True)[:3]

            for log_file in log_files:
                # 只复制最后1000行
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                if len(lines) > 1000:
                    lines = lines[-1000:]
                    lines.insert(0, f"... 前面省略了 {len(lines) - 1000} 行\n")

                with open(self.package_dir / log_file.name, 'w', encoding='utf-8') as f:
                    f.writelines(lines)

    def _create_issue_file(self):
        """创建问题描述文件"""
        with open(self.package_dir / "ISSUE.md", "w") as f:
            f.write(f"""# 问题报告

## 问题描述
{self.issue_description}

## 发生时间
{self.timestamp}

## 重现步骤
1. 
2. 
3. 

## 预期行为
[描述期望的结果]

## 实际行为
[描述实际发生的情况]

## 附加说明
[其他相关信息]
""")

    def _create_zip(self):
        """创建压缩包"""
        zip_path = f"debug_package_{self.timestamp}.zip"
        shutil.make_archive(
            f"debug_package_{self.timestamp}",
            'zip',
            self.package_dir
        )
        return zip_path


if __name__ == "__main__":
    import sys

    issue_desc = input("请输入问题描述: ").strip()
    if not issue_desc:
        issue_desc = "未提供问题描述"

    creator = DebugPackageCreator(issue_desc)
    creator.create()
