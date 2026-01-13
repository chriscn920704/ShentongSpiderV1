# quick_share.py
"""
快速生成可分享的代码摘要
"""

import inspect
import json
from pathlib import Path


def generate_code_summary():
    """生成代码摘要"""
    summary = {
        "project": "圣通教育爬虫",
        "modules": {},
        "recent_changes": [],
        "known_issues": []
    }

    # 分析主要模块
    modules = ["config", "logger", "utils", "browser_manager",
               "lesson_processor", "main", "collect_courses"]

    for module_name in modules:
        module_file = Path(f"{module_name}.py")
        if module_file.exists():
            with open(module_file, 'r', encoding='utf-8') as f:
                content = f.read()

            summary["modules"][module_name] = {
                "size": len(content),
                "functions": [],
                "classes": []
            }

    # 保存摘要
    with open("AI 协助/code_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # 创建简化的代码文件（用于快速分享）
    create_simplified_export()

    return summary


def create_simplified_export():
    """创建简化的导出文件"""
    with open("AI 协助/simplified_code.py", "w", encoding='utf-8') as out:
        out.write("# 圣通教育爬虫 - 简化版代码\n")
        out.write("# 用于快速分享和调试\n\n")

        # 只包含核心逻辑
        core_files = ["config.py", "main.py"]

        for file in core_files:
            if Path(file).exists():
                out.write(f"\n{'=' * 60}\n# {file}\n{'=' * 60}\n\n")
                with open(file, 'r', encoding='utf-8') as f:
                    out.write(f.read())
                out.write("\n\n")


if __name__ == "__main__":
    summary = generate_code_summary()
    print(f"✅ 代码摘要已生成: code_summary.json")
    print(f"📄 简化版代码: simplified_code.py")