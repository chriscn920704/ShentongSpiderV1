# utils.py
import time
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
from config import Config
from logger import logger


class FileUtils:
    """文件操作工具类"""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名中的非法字符"""
        # 替换非法字符为下划线
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)

    @staticmethod
    def ensure_directory(path: Path) -> Path:
        """确保目录存在，返回Path对象"""
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def save_json(data: Any, file_path: Path, indent: int = 2) -> bool:
        """保存数据到JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
            logger.debug(f"数据已保存到: {file_path}")
            return True
        except Exception as e:
            logger.error(f"保存JSON文件失败: {file_path}", exc_info=True)
            return False

    @staticmethod
    def load_json(file_path: Path) -> Optional[Any]:
        """从JSON文件加载数据"""
        try:
            if not file_path.exists():
                logger.warning(f"JSON文件不存在: {file_path}")
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"从文件加载数据: {file_path}")
            return data
        except Exception as e:
            logger.error(f"加载JSON文件失败: {file_path}", exc_info=True)
            return None

    @staticmethod
    def create_lesson_folder(base_dir: Path, lesson_info: Dict) -> Path:
        """创建课时文件夹"""
        # 生成安全的文件夹名
        safe_name = FileUtils.sanitize_filename(lesson_info.get("full_name", "unknown"))
        session_num = lesson_info.get("session_num", 1)
        folder_name = f"{session_num:02d}_{safe_name}"

        # 创建文件夹
        lesson_folder = base_dir / folder_name
        FileUtils.ensure_directory(lesson_folder)

        # 保存课时信息
        info_file = lesson_folder / "课时信息.json"
        FileUtils.save_json({
            "课时基本信息": {
                "课时编号": session_num,
                "课时名称": lesson_info.get("session_name"),
                "课时编码": lesson_info.get("session_code"),
                "所属单元": lesson_info.get("unit_num"),
                "完整名称": lesson_info.get("full_name"),
                "处理时间": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }, info_file)

        return lesson_folder


class APIUtils:
    """API工具类"""

    @staticmethod
    def get_all_courses(token: str) -> List[Dict]:
        """
        获取所有课程（分页）
        注意：这个函数现在主要用于测试，实际应该使用本地保存的课程数据
        """
        logger.progress("通过API获取所有课程列表...")

        api_session = requests.Session()
        api_session.headers.update(Config.get_api_headers(token))

        all_courses = []
        page_num = 0

        while True:
            logger.progress(f"请求第 {page_num + 1} 页课程数据...")

            payload = {
                "campusIdList": Config.CAMPUS_ID_LIST,
                "platform": "OMO_WEB",
                "pageSize": Config.PAGE_SIZE,
                "pageNum": page_num,
                "total": 0,
                "seartchType": True
            }

            time.sleep(Config.API_REQUEST_DELAY)

            try:
                response = api_session.post(
                    Config.COURSE_LIST_URL,
                    json=payload,
                    timeout=Config.REQUEST_TIMEOUT
                )

                if response.status_code != 200:
                    logger.error(f"请求第 {page_num + 1} 页失败，状态码: {response.status_code}")
                    break

                data = response.json()

                if data.get("code") != 0:
                    logger.warning(f"API返回非成功状态: {data.get('msg')}")
                    break

                records = data.get("data", {}).get("list", [])
                total = data.get("data", {}).get("total", 0)

                if not records:
                    logger.info("无更多课程数据，结束分页拉取")
                    break

                all_courses.extend(records)
                logger.progress(
                    f"第 {page_num + 1} 页获取 {len(records)} 门课程",
                    total=f"{len(all_courses)}/{total}"
                )

                if len(all_courses) >= total:
                    logger.success(f"已获取全部 {total} 门课程")
                    break

                page_num += 1

            except Exception as e:
                logger.error(f"获取课程数据异常: {e}", exc_info=True)
                break

        return all_courses

    @staticmethod
    def fetch_course_units(course_code: str, token: str) -> List[Dict]:
        """获取课程下的所有单元"""
        logger.debug(f"获取课程单元，课程编码: {course_code}")

        headers = Config.get_api_headers(token)
        payload = {
            "campusIdList": Config.CAMPUS_ID_LIST,
            "platform": "OMO_WEB",
            "courseCode": course_code
        }

        try:
            response = requests.post(
                Config.UNIT_LIST_URL,
                json=payload,
                headers=headers,
                timeout=Config.REQUEST_TIMEOUT
            )

            if response.status_code != 200:
                logger.error(f"获取单元失败，状态码: {response.status_code}")
                return []

            data = response.json()

            if data.get("code") == 0:
                api_data = data.get("data", {})
                if isinstance(api_data, dict) and "courseUnit" in api_data:
                    units = api_data["courseUnit"]
                    logger.success(f"获取到 {len(units)} 个单元")
                    return units
                else:
                    logger.warning("未找到courseUnit字段")
                    return []
            else:
                logger.error(f"获取单元失败: {data.get('msg')}")
                return []

        except Exception as e:
            logger.error(f"请求单元接口失败: {e}", exc_info=True)
            return []

    @staticmethod
    def fetch_unit_sessions(course_code: str, unit_code: str, token: str) -> List[Dict]:
        """获取指定单元下的所有课时"""
        logger.debug(f"获取单元课时，课程编码: {course_code}, 单元编码: {unit_code}")

        headers = Config.get_api_headers(token)
        payload = {
            "campusIdList": Config.CAMPUS_ID_LIST,
            "platform": "OMO_WEB",
            "courseCode": course_code,
            "courseUnitCode": unit_code
        }

        try:
            response = requests.post(
                Config.SESSION_LIST_URL,
                json=payload,
                headers=headers,
                timeout=Config.REQUEST_TIMEOUT
            )

            if response.status_code != 200:
                logger.error(f"获取课时失败，状态码: {response.status_code}")
                return []

            data = response.json()

            if data.get("code") == 0:
                sessions = data.get("data", [])
                logger.success(f"获取到 {len(sessions)} 个课时")
                return sessions
            else:
                logger.error(f"获取课时失败: {data.get('msg')}")
                return []

        except Exception as e:
            logger.error(f"请求课时接口失败: {e}", exc_info=True)
            return []


class UserInputUtils:
    """用户输入工具类"""

    @staticmethod
    def select_course(courses_data: List[Dict]) -> Optional[Dict]:
        """让用户选择课程"""
        if not courses_data:
            logger.error("没有可用的课程数据")
            return None

        logger.separator("课程选择")
        logger.info("请选择要处理的课程：")

        for i, course in enumerate(courses_data, 1):
            course_name = course.get("courseName", f"课程{i}")
            course_id = course.get("id", "未知ID")
            logger.info(f"  {i:2d}. {course_name} (ID: {course_id})")

        while True:
            try:
                choice = input('\n请输入课程编号 (1-{}): '.format(len(courses_data))).strip()

                if not choice:
                    logger.info("使用默认选择第一个课程")
                    selected_index = 0
                else:
                    selected_index = int(choice) - 1

                if 0 <= selected_index < len(courses_data):
                    selected_course = courses_data[selected_index]
                    logger.success(f"已选择课程: {selected_course.get('courseName')}")
                    return selected_course
                else:
                    logger.warning(f"请输入1到{len(courses_data)}之间的数字")

            except ValueError:
                logger.warning("请输入有效的数字")
            except KeyboardInterrupt:
                logger.info("用户取消选择")
                return None

    @staticmethod
    def select_lessons(lessons_info: List[Dict]) -> List[Dict]:
        """让用户选择要处理的课时"""
        if not lessons_info:
            logger.error("没有可用的课时数据")
            return []

        logger.separator("课时选择")
        logger.info("请选择课时处理方式：")
        logger.info("  1. 处理所有课时")
        logger.info("  2. 处理指定范围 (N-M课时)")
        logger.info("  3. 仅测试第2个课时")
        logger.info("  4. 手动选择特定课时")

        # 显示课时列表
        logger.info("\n当前课程包含以下课时：")
        for i, lesson in enumerate(lessons_info, 1):
            logger.info(f'  {i:2d}. [{lesson["session_num"]:02d}] {lesson["session_name"]}')

        while True:
            try:
                choice = input('\n请选择处理方式 (1-4): ').strip()

                if choice == '1':  # 所有课时
                    selected_lessons = lessons_info
                    logger.info(f"将处理所有 {len(lessons_info)} 个课时")
                    return selected_lessons

                elif choice == '2':  # N-M课时
                    while True:
                        try:
                            range_input = input('请输入课时范围 (格式: N-M, 如: 2-5): ').strip()

                            if not range_input:
                                logger.info(f"使用默认范围: 1-{len(lessons_info)}")
                                start, end = 1, len(lessons_info)
                                break

                            if '-' in range_input:
                                parts = range_input.split('-')
                                start = int(parts[0].strip())
                                end = int(parts[1].strip())
                            else:
                                start = end = int(range_input.strip())

                            if 1 <= start <= end <= len(lessons_info):
                                break
                            else:
                                logger.warning(f"请输入1到{len(lessons_info)}之间的有效范围")

                        except ValueError:
                            logger.warning("请输入有效的数字范围")

                    selected_lessons = lessons_info[start - 1:end]
                    logger.info(f"将处理第 {start} 到第 {end} 个课时")
                    return selected_lessons

                elif choice == '3':  # 仅测试第2个课时
                    if len(lessons_info) >= 2:
                        selected_lessons = [lessons_info[1]]
                        logger.info("将测试第2个课时")
                    else:
                        selected_lessons = [lessons_info[0]]
                        logger.warning("课时数量不足，将测试第1个课时")
                    return selected_lessons

                elif choice == '4':  # 手动选择特定课时
                    while True:
                        try:
                            indices_input = input('请输入课时编号 (多个用逗号分隔，如: 1,3,5): ').strip()

                            if not indices_input:
                                logger.info("使用默认: 第1个课时")
                                selected_lessons = [lessons_info[0]]
                                break

                            indices = []
                            for part in indices_input.split(','):
                                idx = int(part.strip())
                                if 1 <= idx <= len(lessons_info):
                                    indices.append(idx - 1)

                            if indices:
                                selected_lessons = [lessons_info[i] for i in indices]
                                break
                            else:
                                logger.warning(f"请输入1到{len(lessons_info)}之间的有效数字")

                        except ValueError:
                            logger.warning("请输入有效的数字")

                    selected_indices = [str(i + 1) for i, lesson in enumerate(lessons_info)
                                        if lesson in selected_lessons]
                    logger.info(f"将处理第 {', '.join(selected_indices)} 个课时")
                    return selected_lessons

                else:
                    logger.warning("请输入1-4之间的数字")

            except KeyboardInterrupt:
                logger.info("用户取消选择")
                return []