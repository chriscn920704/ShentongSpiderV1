# config.py (完整修复版本)
import os
from pathlib import Path


class Config:
    # API配置
    BASE_API_URL = "https://api-manage2.shengtongedu.cn/st-course-server"

    # 接口路径
    COURSE_LIST_URL = f"{BASE_API_URL}/manage/course/coursePageListV6"
    UNIT_LIST_URL = f"{BASE_API_URL}/manage/course/unit/courseUnitList"
    SESSION_LIST_URL = f"{BASE_API_URL}/manage/course/sesson/selectByCourseUnits"

    # 页面URL
    LOGIN_URL = "https://manage.shengtongedu.cn/curriculum/#/curriculum/courseManage"
    COURSE_MANAGE_URL = "https://manage.shengtongedu.cn/curriculum/#/curriculum/courseManage"

    # 用户配置（可改为从环境变量或配置文件读取）
    PHONE_NUMBER = "18795960907"
    CAMPUS_ID = "4104"
    CAMPUS_ID_LIST = ["4104"]

    # 下载配置
    DOWNLOAD_BASE_DIR = Path("downloads")
    PAGE_SIZE = 12
    REQUEST_TIMEOUT = 30

    # 浏览器配置
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    VIEWPORT_SIZE = {"width": 1920, "height": 1080}

    # 文件路径
    COURSES_DATA_FILE = Path("courses_data.json")
    LESSONS_INFO_FILE = Path("lessons_info.json")

    # 时间配置（秒）
    PAGE_LOAD_WAIT = 5
    CLICK_WAIT = 2
    API_REQUEST_DELAY = 1.5

    # 文件类型映射（新增）
    FILE_TYPE_EXTENSIONS = {
        "pdf": ".pdf",
        "ppt": ".ppt",
        "pptx": ".pptx",
        "word": ".docx",
        "excel": ".xlsx",
        "zip": ".zip",
        "video": ".mp4",
        "audio": ".mp3",
        "image": ".jpg",
        "sb3": ".sb3",
        "unknown": ".dat"
    }

    # 下载配置（通过类方法获取，避免循环引用）
    @classmethod
    def get_download_config(cls):
        """获取下载配置"""
        return {
            "max_concurrent": 3,           # 最大并发下载数
            "download_timeout": 300,       # 下载超时时间（秒）
            "max_retries": 3,             # 最大重试次数
            "chunk_size": 8192,           # 下载块大小
            "user_agent": cls.USER_AGENT,  # 正确引用类属性
        }

    @classmethod
    def get_api_headers(cls, token):
        """获取API请求的标准headers"""
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "campusid": cls.CAMPUS_ID,
            "content-type": "application/json; charset=UTF-8",
            "logincode": cls.PHONE_NUMBER,
            "origin": "https://manage.shengtongedu.cn",
            "platform": "OMO_WEB",
            "priority": "u=1, i",
            "referer": "https://manage.shengtongedu.cn/",
            "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "token": token,
            "user-agent": cls.USER_AGENT,
        }