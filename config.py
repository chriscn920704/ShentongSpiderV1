# -*- coding: utf-8 -*-
# @Author : Chris
# @Desc   : 圣通教育爬虫 全局配置文件
# @Date   : 2026

# ===================== 基础配置 =====================
# 登录相关
USER_PHONE = ""
CAMPUS_ID = ""
LOGIN_URL = "https://shentongedu.com/omo/login"

# 分页配置
PAGE_SIZE = 96  # 每页条数 规避翻页

# 路径配置
LOG_DIR = "./logs"
DOWNLOAD_DIR = "./shentong_download_resources"

# 日志配置
LOG_LEVEL = "INFO"
LOG_FILE = "shentong_spider.log"

# 浏览器配置
IMPLICITLY_WAIT_TIME = 10
PAGE_LOAD_TIMEOUT = 20
SCRIPT_TIMEOUT = 15

# ===================== 新增：资源Tab过滤核心配置【本次改动】 =====================
# 白名单关键词：包含这些词的Tab才判定为资源类Tab，会点击探索
RESOURCE_TAB_WHITE_KEYWORDS = ["资源", "资料", "课件", "附件", "课前", "课中", "课后", "学习", "讲义", "素材"]
# 黑名单关键词：包含这些词的Tab一律判定为非资源类，强制跳过永不点击
RESOURCE_TAB_BLACK_KEYWORDS = ["学员", "考勤", "作业", "批改", "统计", "班级", "评价", "数据", "设置", "管理", "报表", "分析", "考核", "签到"]
# 核心页面结构校验xpath - 你的课时树形结构节点，不变则页面结构安全
VALIDATE_CORE_STRUCTURE_XPATH = "//div[contains(@class,'el-tree') or contains(@class,'lesson-tree')]"

# ===================== 下载模块配置 =====================
MAX_CONCURRENT = 3
RETRY_TIMES = 3
RETRY_DELAY = 2
SUPPORT_FILE_TYPES = ["pdf", "ppt", "pptx", "doc", "docx", "xls", "xlsx", "mp4", "mp3", "jpg", "png", "zip", "rar"]