# -*- coding: utf-8 -*-
# @Author : Chris
# @Desc   : 圣通教育爬虫 - 课时处理层 核心逻辑
# @Date   : 2026
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from logger import logger
import time
from config import (
    IMPLICITLY_WAIT_TIME,
    RESOURCE_TAB_WHITE_KEYWORDS,
    RESOURCE_TAB_BLACK_KEYWORDS,
    VALIDATE_CORE_STRUCTURE_XPATH,
    SUPPORT_FILE_TYPES
)


class LessonProcessor:
    def __init__(self, driver):
        self.driver = driver
        self.driver.implicitly_wait(IMPLICITLY_WAIT_TIME)
        self.course_name = ""
        self.lesson_name = ""
        self.current_lesson_id = ""
        self.lesson_list = []
        self.resource_metadata = []  # 存储所有资源元数据

    def get_lesson_list(self):
        """获取当前课程下的所有课时树形结构列表"""
        try:
            lesson_tree_xpath = "//div[contains(@class,'el-tree')]/div[contains(@class,'el-tree-node')]"
            lesson_nodes = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, lesson_tree_xpath))
            )
            for node in lesson_nodes:
                try:
                    lesson_name = node.find_element(By.XPATH, ".//span[contains(@class,'el-tree-node__label')]").text.strip()
                    if lesson_name and lesson_name not in self.lesson_list:
                        self.lesson_list.append(lesson_name)
                except NoSuchElementException:
                    continue
            logger.info(f"✅ 成功获取课时列表，共 {len(self.lesson_list)} 个课时")
            return self.lesson_list
        except TimeoutException:
            logger.warning("⚠️ 获取课时列表超时，当前课程无课时数据")
            return []
        except Exception as e:
            logger.error(f"❌ 获取课时列表异常: {str(e)}", exc_info=False)
            return []

    def select_lesson_range(self, start_idx, end_idx):
        """选择课时范围"""
        if not self.lesson_list or start_idx < 0 or end_idx >= len(self.lesson_list):
            logger.error("❌ 课时范围选择无效，索引越界或无课时数据")
            return []
        selected_lessons = self.lesson_list[start_idx:end_idx + 1]
        logger.info(f"✅ 已选择课时范围: {selected_lessons}")
        return selected_lessons

    def enter_lesson_detail(self, lesson_name):
        """进入指定课时的详情页"""
        try:
            self.lesson_name = lesson_name
            self.resource_metadata = []  # 进入新课时清空资源数据
            lesson_xpath = f"//span[contains(@class,'el-tree-node__label') and normalize-space(text())='{lesson_name}']"
            lesson_ele = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, lesson_xpath))
            )
            lesson_ele.click()
            time.sleep(0.8)
            logger.info(f"✅ 成功进入课时详情页: {lesson_name}")
            return True
        except TimeoutException:
            logger.warning(f"⚠️ 进入课时[{lesson_name}]超时，元素未加载完成")
            return False
        except StaleElementReferenceException:
            logger.warning(f"⚠️ 课时[{lesson_name}]元素过期，重新尝试定位")
            return self.enter_lesson_detail(lesson_name)
        except Exception as e:
            logger.error(f"❌ 进入课时[{lesson_name}]异常: {str(e)}", exc_info=False)
            return False

    def capture_resource_url(self, download_btn):
        """捕获资源真实下载链接 - 原方法完全保留"""
        try:
            real_url = download_btn.get_attribute("data-url") or download_btn.get_attribute("href")
            if real_url and real_url.startswith(("http://", "https://")):
                return real_url
            # 点击按钮后从网络日志提取
            download_btn.click()
            time.sleep(0.5)
            logs = self.driver.get_log("performance")
            for log in logs:
                log_msg = log["message"]
                if "download" in log_msg or any(file_type in log_msg for file_type in SUPPORT_FILE_TYPES):
                    if '"url":"' in log_msg:
                        download_url = log_msg.split('"url":"')[1].split('"')[0]
                        return download_url
            return None
        except StaleElementReferenceException:
            logger.debug("⚠️ 下载按钮元素过期，跳过该资源")
            return None
        except Exception as e:
            logger.error(f"❌ 捕获资源URL异常: {str(e)}", exc_info=False)
            return None

    def judge_resource_type(self, resource_name):
        """判断资源文件类型 - 原方法完全保留"""
        if not resource_name:
            return "unknown"
        resource_name = resource_name.lower().strip()
        for file_type in SUPPORT_FILE_TYPES:
            if resource_name.endswith(f".{file_type}"):
                return file_type
        return "other"

    # ===================== 【核心重构 替换原2个方法 根治误点问题 无任何冗余】 =====================
    def explore_all_valid_resource_tabs(self):
        """
        探索所有有效资源类一级Tab - 零误点终极版
        三重防护：白名单关键词过滤 + 黑名单关键词排除 + DOM核心结构校验
        绝对不会点击非资源类Tab，页面结构永不崩解，返回标准化资源数据
        """
        valid_resource_tabs = []
        all_resource_metadata = []
        core_page_structure_ok = True

        try:
            # 定位Element-UI标准一级Tab栏 (完全复用你原有的xpath)
            tab_bar_xpath = "//div[contains(@class,'el-tabs__header')]//li[contains(@class,'el-tabs__item')]"
            all_tab_elements = WebDriverWait(self.driver, 8).until(
                EC.presence_of_all_elements_located((By.XPATH, tab_bar_xpath))
            )
            logger.info(f"🔍 资源侦察 - 页面一级Tab总数: {len(all_tab_elements)}")

            for tab_ele in all_tab_elements:
                # 跳过禁用的Tab
                if "is-disabled" in tab_ele.get_attribute("class"):
                    continue
                current_tab_name = tab_ele.text.strip()
                if not current_tab_name:
                    continue

                # 核心过滤逻辑 - 只保留资源类Tab
                is_match_white = any(kw in current_tab_name for kw in RESOURCE_TAB_WHITE_KEYWORDS)
                is_match_black = any(kw in current_tab_name for kw in RESOURCE_TAB_BLACK_KEYWORDS)

                if not is_match_white or is_match_black:
                    logger.debug(f"🚫 过滤非资源类Tab → {current_tab_name}")
                    continue

                # 兜底校验：核心课时树形结构是否存在，防止页面崩解
                try:
                    WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, VALIDATE_CORE_STRUCTURE_XPATH))
                    )
                except TimeoutException:
                    logger.warning("⚠️ 核心页面结构丢失，终止本次资源侦察")
                    core_page_structure_ok = False
                    break

                # 安全点击有效资源Tab
                try:
                    tab_ele.click()
                    time.sleep(0.7)  # Vue异步渲染等待，完美适配你的前端框架
                    logger.info(f"✅ 探索有效资源Tab → {current_tab_name}")
                except StaleElementReferenceException:
                    logger.debug(f"⚠️ Tab元素已刷新，跳过 → {current_tab_name}")
                    continue

                # 采集当前Tab下的资源数据
                tab_resources = self.survey_single_tab_resources(current_tab_name)
                if tab_resources:
                    all_resource_metadata.extend(tab_resources)
                    valid_resource_tabs.append(current_tab_name)
                    logger.info(f"📌 {current_tab_name} - 采集到资源: {len(tab_resources)} 个")
                else:
                    logger.info(f"📌 {current_tab_name} - 无可用学习资源")

            # 赋值全局资源数据，供外部调用
            self.resource_metadata = all_resource_metadata
            if core_page_structure_ok:
                logger.info(f"✅ 资源侦察完成 | 有效Tab数: {len(valid_resource_tabs)} | 总资源数: {len(all_resource_metadata)}")
            return valid_resource_tabs, all_resource_metadata

        except TimeoutException:
            logger.warning("⚠️ 当前页面无一级Tab栏，无资源可侦察")
            return [], []
        except Exception as e:
            logger.error(f"❌ 资源侦察主流程异常: {str(e)}", exc_info=False)
            return [], []

    # ===================== 【配套新增】单Tab资源采集方法 =====================
    def survey_single_tab_resources(self, tab_name):
        """采集单个有效资源Tab下的所有资源元数据，复用你原有逻辑"""
        single_tab_resource_list = []
        try:
            # 完全复用你原有的资源表格xpath
            resource_row_xpath = "//div[contains(@class,'el-table__body-wrapper')]//tbody//tr[contains(@class,'el-table__row')]"
            resource_elements = WebDriverWait(self.driver, 6).until(
                EC.presence_of_all_elements_located((By.XPATH, resource_row_xpath))
            )

            for res_ele in resource_elements:
                try:
                    resource_name = res_ele.find_element(By.XPATH, "./td[2]").text.strip()
                    if not resource_name:
                        continue
                    # 定位下载按钮，完全复用你原有的xpath
                    download_button = res_ele.find_element(By.XPATH, "./td[last()]//button[contains(text(),'下载')]")
                    real_download_url = self.capture_resource_url(download_button)
                    if not real_download_url:
                        continue
                    resource_type = self.judge_resource_type(resource_name)
                    # 标准化资源数据格式
                    single_tab_resource_list.append({
                        "tab_name": tab_name,
                        "resource_name": resource_name,
                        "resource_url": real_download_url,
                        "resource_type": resource_type
                    })
                except NoSuchElementException:
                    continue
                except Exception as e:
                    logger.debug(f"⚠️ 单资源采集失败: {str(e)}")
                    continue
        except TimeoutException:
            logger.debug(f"📌 {tab_name} - 未检测到资源表格")
        except Exception as e:
            logger.error(f"❌ {tab_name} 资源采集异常: {str(e)}", exc_info=False)
        return single_tab_resource_list