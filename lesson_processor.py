# lesson_processor.py
import time
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from config import Config
from logger import logger
from utils import FileUtils, APIUtils
from downloader import SimpleDownloader


class LessonProcessor:
    """课时处理器 - 修复整合版"""

    def __init__(self, page, download_base: Path):
        self.page = page
        self.download_base = download_base
        self.seen_resources = set()  # 用于去重的集合
        # 初始化简化版下载器
        self.downloader = SimpleDownloader(page)

    def process_lesson(self, lesson_info: Dict) -> bool:
        """处理单个课时"""
        try:
            # 从lesson_info中提取变量
            session_index = lesson_info.get("session_num", 1)
            session_name = lesson_info.get("session_name", "未知课时")
            session_code = lesson_info.get("session_code", "")
            full_name = lesson_info.get("full_name", "未知课时")

            logger.progress(f"开始处理课时 [{session_index:02d}]: {full_name}")

            # 导航到课时详情页
            if self._navigate_to_lesson(lesson_info):
                # 创建课时文件夹（在导航成功后创建）
                lesson_folder = FileUtils.create_lesson_folder(self.download_base, lesson_info)
                logger.info(f"文件夹: {lesson_folder.name}")

                # ---- 执行安全资源普查 ----
                logger.separator("执行资源普查")
                self.seen_resources.clear()  # 清空去重集合
                survey_result = self.survey_all_resource_tabs(lesson_info)

                # ---- 开始下载资源 ----
                if survey_result["发现的资源"]:
                    logger.separator("开始下载资源")

                    # 将普查结果转换为下载器需要的格式
                    download_tasks = self._convert_survey_to_download_tasks(
                        survey_result, lesson_info, lesson_folder
                    )

                    if download_tasks:
                        # 使用下载器下载资源
                        download_success = self.downloader.download_resources(
                            lesson_info=lesson_info,
                            download_dir=lesson_folder
                        )

                        if download_success:
                            logger.success("资源下载完成")
                        else:
                            logger.warning("部分或全部资源下载失败")
                    else:
                        logger.warning("⚠️ 没有找到可下载的资源")
                else:
                    logger.warning("⚠️ 普查未发现任何资源线索，跳过下载")

                # 创建下载完成标记
                self._create_completion_marker(lesson_folder, lesson_info)

                logger.success(f"课时 [{session_index:02d}] {session_name} 处理完成")
                return True
            else:
                logger.error(f"课时 [{session_index:02d}] 导航失败")
                return False

        except Exception as e:
            logger.error(f"处理课时失败: {e}", exc_info=True)
            return False

    def _convert_survey_to_download_tasks(self, survey_result: Dict,
                                          lesson_info: Dict,
                                          lesson_folder: Path) -> bool:
        """
        将普查结果转换为下载任务
        这是一个临时方法，实际下载逻辑由下载器内部处理
        """
        # 这里只返回True表示有任务，实际转换在Downloader内部完成
        return len(survey_result["发现的资源"]) > 0

    def survey_all_resource_tabs(self, lesson_info: Dict):
        """
        核心普查方法：侦察当前课时详情页的所有资源Tab和可点击元素。
        只关注与资源相关的Tab，避免点击会导航到其他页面的Tab。
        """
        survey_result = {
            "课时信息": lesson_info,
            "普查时间": time.strftime("%Y-%m-%d %H:%M:%S"),
            "资源相关Tab": [],
            "发现的资源": []
        }

        logger.info("🔍 开始资源普查...")

        # 定义资源相关Tab（只会切换内容，不会跳转页面）
        RESOURCE_RELATED_TABS = ["课前预习", "课中学习", "课后练习", "讲师磨课"]

        # 定义需要避免的Tab（可能导致页面跳转或卡住）
        AVOID_TABS = ["基本信息", "课程授权", "上课进度", "课程详情", "授课老师",
                      "校区", "设置", "编辑", "管理", "权限"]

        # 定义需要避免的二级Tab（非资源相关）
        AVOID_SECONDARY_TABS = ["基本信息", "课程授权", "上课进度"]

        try:
            # 1. 找到所有一级Tab
            primary_tabs = self.page.locator('.el-tabs__header.is-top .el-tabs__item').all()
            logger.info(f"发现 {len(primary_tabs)} 个一级Tab")

            # 首先找到并激活"课中学习"Tab（通常是最安全的起始点）
            target_tab_found = False
            for tab in primary_tabs:
                try:
                    tab_name = tab.inner_text().strip()
                    if tab_name == "课中学习":
                        # 如果不是激活状态，点击激活
                        is_active = "is-active" in (tab.get_attribute("class") or "")
                        if not is_active:
                            logger.debug(f"激活基准Tab: {tab_name}")
                            tab.click()
                            self.page.wait_for_load_state("networkidle")
                            time.sleep(2)
                        target_tab_found = True
                        break
                except:
                    continue

            if not target_tab_found:
                logger.warning("未找到'课中学习'Tab，尝试其他资源Tab")

            # 记录所有Tab信息，但只点击资源相关的Tab
            for tab in primary_tabs:
                try:
                    tab_name = tab.inner_text().strip()
                    is_active = "is-active" in (tab.get_attribute("class") or "")

                    # 检查是否需要避免点击
                    should_avoid = any(avoid_tab in tab_name for avoid_tab in AVOID_TABS)

                    if should_avoid:
                        logger.debug(f"⚠️ 跳过危险Tab: {tab_name} (可能导致页面跳转)")
                        continue

                    # 检查是否是资源相关Tab
                    is_resource_related = tab_name in RESOURCE_RELATED_TABS
                    tab_info = {"名称": tab_name, "是否激活": is_active, "资源相关": is_resource_related}

                    if is_resource_related:
                        survey_result["资源相关Tab"].append(tab_info)

                        # 只在必要时点击（非激活状态）
                        if not is_active:
                            logger.info(f"安全点击资源Tab: {tab_name}")
                            tab.click()
                            self.page.wait_for_load_state("networkidle")
                            time.sleep(2.5)  # 等待内容加载

                            # 探索这个Tab下的内容
                            self._explore_resource_tab(tab_name, AVOID_SECONDARY_TABS, survey_result)

                            # 探索完成后，返回"课中学习"Tab作为安全基准点
                            try:
                                # 查找"课中学习"Tab并点击
                                lesson_tab = self.page.locator(
                                    '.el-tabs__header.is-top .el-tabs__item:has-text("课中学习")').first
                                if lesson_tab.count() > 0:
                                    lesson_tab.click()
                                    logger.debug(f"已返回'课中学习'Tab")
                                    time.sleep(1.5)
                            except Exception as e:
                                logger.warning(f"返回'课中学习'Tab失败: {e}")
                        else:
                            # 如果是激活状态，直接探索
                            logger.info(f"探索当前激活的Tab: {tab_name}")
                            self._explore_resource_tab(tab_name, AVOID_SECONDARY_TABS, survey_result)
                    else:
                        logger.debug(f"跳过非资源Tab: {tab_name}")

                except Exception as tab_e:
                    logger.debug(f"处理Tab '{tab_name}' 时出错: {tab_e}")
                    continue

        except Exception as e:
            logger.error(f"资源普查过程发生错误: {e}", exc_info=True)
            # 尝试恢复页面状态
            self._safe_navigate_back()

        # 打印并保存普查结果
        self._log_and_save_survey(survey_result, lesson_info)
        return survey_result

    def _explore_resource_tab(self, tab_name: str, avoid_secondary_tabs: List[str], survey_result: Dict):
        """探索特定资源Tab下的内容"""
        try:
            logger.info(f"探索Tab: {tab_name}")

            # 等待资源内容区域加载
            time.sleep(1.5)

            # 查找二级Tab容器
            secondary_containers = self.page.locator('.tabmain.el-tabs.el-tabs--card.el-tabs--left, div.tabmain').all()

            if secondary_containers:
                # 使用第一个找到的容器
                secondary_container = secondary_containers[0]

                # 获取所有二级Tab
                secondary_tabs = secondary_container.locator('.el-tabs__item').all()
                logger.info(f"在 '{tab_name}' 下发现 {len(secondary_tabs)} 个二级Tab")

                # 记录当前激活的二级Tab
                active_secondary_tab = None

                for i, sub_tab in enumerate(secondary_tabs):
                    try:
                        sub_name = sub_tab.inner_text().strip()
                        sub_is_active = "is-active" in (sub_tab.get_attribute("class") or "")

                        # 检查是否需要避免此二级Tab
                        if any(avoid_tab in sub_name for avoid_tab in avoid_secondary_tabs):
                            logger.debug(f"跳过非资源二级Tab: {sub_name}")
                            continue

                        logger.info(f"二级Tab [{i + 1}/{len(secondary_tabs)}]: {sub_name} (激活: {sub_is_active})")

                        if sub_is_active:
                            active_secondary_tab = sub_name

                        # 点击这个二级Tab来探索其内部资源
                        if not sub_is_active:
                            logger.debug(f"点击二级Tab: {sub_name}")
                            sub_tab.click()
                            self.page.wait_for_load_state("networkidle")
                            time.sleep(1.5)

                        # 在当前二级Tab内，普查所有可能的资源元素
                        resource_candidates = self._find_resource_candidates()
                        for candidate in resource_candidates:
                            candidate["所属Tab"] = f"{tab_name} > {sub_name}"
                            survey_result["发现的资源"].append(candidate)

                    except Exception as sub_e:
                        logger.debug(f"探索二级Tab '{sub_name}' 时出错: {sub_e}")
                        continue

                # 探索完成后，如果有激活的二级Tab，尝试返回它
                if active_secondary_tab:
                    try:
                        for sub_tab in secondary_tabs:
                            if sub_tab.inner_text().strip() == active_secondary_tab:
                                if "is-active" not in (sub_tab.get_attribute("class") or ""):
                                    sub_tab.click()
                                    time.sleep(1)
                                break
                    except:
                        pass
            else:
                # 没有二级Tab容器，直接查找资源
                logger.info(f"在 '{tab_name}' 下未发现二级Tab容器，直接查找资源")
                resource_candidates = self._find_resource_candidates()
                for candidate in resource_candidates:
                    candidate["所属Tab"] = tab_name
                    survey_result["发现的资源"].append(candidate)

        except Exception as e:
            logger.debug(f"探索资源Tab '{tab_name}' 时出错: {e}")

    def _find_resource_candidates(self):
        """在当前活动Tab中，查找所有可能是资源入口的元素。返回去重后的字典列表。"""
        candidates = []
        seen_keys = set()  # 用于去重的键集合

        # 模式1: 查找特定class的下载按钮
        suspect_classes = ["file_btn", "download-btn", "download-button", "btn-download"]

        for class_name in suspect_classes:
            try:
                elements = self.page.locator(f'.{class_name}').all()
                for elem in elements:
                    try:
                        elem_text = elem.inner_text().strip()
                        if not elem_text:
                            continue

                        # 生成唯一键
                        elem_key = f"{class_name}:{elem_text[:50]}"
                        if elem_key in seen_keys:
                            continue

                        seen_keys.add(elem_key)
                        candidates.append({
                            "类型": "下载按钮",
                            "元素文本": elem_text[:100],
                            "选择器建议": f".{class_name}",
                            "特征": f"class包含 {class_name}"
                        })
                    except:
                        pass
            except:
                pass

        # 模式2: 所有包含"下载"文本的按钮或Span
        try:
            download_elements = self.page.locator(
                'button:has-text("下载"), span:has-text("下载"), a:has-text("下载")').all()
            for elem in download_elements:
                try:
                    elem_text = elem.inner_text().strip()
                    if not elem_text or "下载" not in elem_text:
                        continue

                    # 生成唯一键
                    elem_key = f"下载按钮:{elem_text[:50]}"
                    if elem_key in seen_keys:
                        continue

                    seen_keys.add(elem_key)
                    candidates.append({
                        "类型": "下载按钮",
                        "元素文本": elem_text[:100],
                        "选择器建议": self._generate_selector(elem),
                        "特征": "文本包含'下载'"
                    })
                except:
                    pass
        except:
            pass

        # 模式3: 所有包含常见文件扩展名的链接
        file_extensions = [".pdf", ".ppt", ".pptx", ".zip", ".sb3", ".jpg", ".png", ".mp4", ".mp3", ".doc", ".docx"]
        for ext in file_extensions:
            try:
                links = self.page.locator(f'a[href*="{ext}"]').all()
                for link in links:
                    try:
                        href = link.get_attribute("href") or ""
                        if not href:
                            continue

                        # 生成唯一键
                        elem_key = f"文件链接:{href[:100]}"
                        if elem_key in seen_keys:
                            continue

                        seen_keys.add(elem_key)
                        link_text = link.inner_text().strip()[:100] or "无文本"
                        candidates.append({
                            "类型": "文件链接",
                            "元素文本": link_text,
                            "href": href[:200],
                            "特征": f"链接包含{ext}"
                        })
                    except:
                        pass
            except:
                pass

        # 模式4: 查找图片元素（限制数量）
        try:
            images = self.page.locator('img[src*="."]').all()
            for img in images[:10]:  # 限制数量，避免太多
                try:
                    src = img.get_attribute("src") or ""
                    if not src or "http" not in src:
                        continue

                    # 生成唯一键
                    elem_key = f"图片:{src[:100]}"
                    if elem_key in seen_keys:
                        continue

                    seen_keys.add(elem_key)
                    alt = img.get_attribute("alt") or img.get_attribute("title") or "图片"
                    candidates.append({
                        "类型": "图片",
                        "元素文本": alt[:100],
                        "src": src[:200],
                        "特征": "图片资源"
                    })
                except:
                    pass
        except:
            pass

        logger.debug(f"找到 {len(candidates)} 个去重后的资源候选元素")
        return candidates

    def _generate_selector(self, element):
        """尝试为元素生成一个相对稳定的选择器。"""
        try:
            # 获取class属性
            class_attr = element.get_attribute("class") or ""
            if class_attr:
                classes = class_attr.split()
                for cls in classes:
                    if cls and len(cls) > 2 and not cls.startswith('el-') and not cls.startswith('is-'):
                        return f'.{cls}'

            return "需更精准定位"
        except:
            return "未知"

    def _log_and_save_survey(self, survey_result, lesson_info):
        """记录并保存普查结果到文件。"""
        # 在控制台打印结构化结果
        logger.info("📊 ========== 资源普查报告 ==========")
        logger.info(f"课时: {lesson_info.get('full_name')}")
        logger.info(f"资源相关Tab数量: {len(survey_result['资源相关Tab'])}")

        for tab in survey_result["资源相关Tab"]:
            logger.info(f"  - {tab['名称']} (激活: {tab['是否激活']}, 资源相关: {tab['资源相关']})")

        logger.info(f"发现的资源线索总数: {len(survey_result['发现的资源'])}")

        if len(survey_result['发现的资源']) > 0:
            # 按类型统计
            type_count = {}
            for res in survey_result["发现的资源"]:
                res_type = res.get("类型", "未知")
                type_count[res_type] = type_count.get(res_type, 0) + 1
            for t, c in type_count.items():
                logger.info(f"    {t}: {c} 个")

            # 按所属Tab统计
            tab_count = {}
            for res in survey_result["发现的资源"]:
                tab_path = res.get("所属Tab", "未知")
                tab_count[tab_path] = tab_count.get(tab_path, 0) + 1

            if tab_count:
                logger.info("按Tab分布:")
                for tab_path, count in tab_count.items():
                    logger.info(f"    {tab_path}: {count} 个")

            # 显示前5个资源线索详情
            logger.info("前5个资源线索详情:")
            for i, res in enumerate(survey_result["发现的资源"][:5], 1):
                elem_text = res.get('元素文本', '无文本')
                logger.info(f"    {i}. [{res.get('类型', '未知')}] {elem_text[:50]}")
        else:
            logger.warning("⚠️ 未发现任何资源线索")

        # 保存到课时文件夹（只保存精简信息）
        try:
            safe_name = FileUtils.sanitize_filename(lesson_info["full_name"])
            safe_name = f"{lesson_info['session_num']:02d}_{safe_name}"
            lesson_folder = self.download_base / safe_name

            # 确保文件夹存在
            lesson_folder.mkdir(parents=True, exist_ok=True)

            # 创建精简的报告
            compact_survey = {
                "课时信息": survey_result["课时信息"],
                "普查时间": survey_result["普查时间"],
                "资源相关Tab": survey_result["资源相关Tab"],
                "发现的资源统计": {
                    "总数": len(survey_result["发现的资源"]),
                    "按类型": {},
                    "按Tab分布": {}
                }
            }

            # 按类型统计
            for res in survey_result["发现的资源"]:
                res_type = res.get("类型", "未知")
                compact_survey["发现的资源统计"]["按类型"][res_type] = \
                    compact_survey["发现的资源统计"]["按类型"].get(res_type, 0) + 1

            # 按Tab分布统计
            for res in survey_result["发现的资源"]:
                tab_path = res.get("所属Tab", "未知")
                compact_survey["发现的资源统计"]["按Tab分布"][tab_path] = \
                    compact_survey["发现的资源统计"]["按Tab分布"].get(tab_path, 0) + 1

            # 只保存前10个资源详情
            compact_survey["资源详情示例"] = survey_result["发现的资源"][:10]

            survey_file = lesson_folder / "资源普查报告.json"
            with open(survey_file, 'w', encoding='utf-8') as f:
                json.dump(compact_survey, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"📁 普查报告已保存至: {survey_file}")
        except Exception as e:
            logger.debug(f"保存普查报告失败: {e}")

    def _navigate_to_lesson(self, lesson_info: Dict) -> bool:
        """导航到课时详情页"""
        try:
            session_name = lesson_info["session_name"]
            unit_num = lesson_info["unit_num"]
            session_code = lesson_info["session_code"]

            logger.info("导航到上课进度页面...")

            # 首先检查当前页面状态
            current_url = self.page.url
            logger.debug(f"当前URL: {current_url}")

            # 检查URL模式：是否在课程详情页
            course_detail_patterns = [
                "editCourse/basicInfo",  # 基本信息页
                "editCourse/progress",  # 上课进度页
                "id=",  # 包含课程ID的URL
                "progress?id="  # 进度页面
            ]

            # 检查是否在课程详情页
            is_course_detail = any(pattern in current_url for pattern in course_detail_patterns)

            if not is_course_detail:
                logger.error(f"不在课程详情页，无法处理课时。当前URL: {current_url}")
                return False

            logger.success("确认在课程详情页")

            # 确保在"上课进度"页
            if "editCourse/progress" not in current_url:
                logger.info("当前不在上课进度页，尝试跳转...")

                # 从URL中提取课程ID
                course_id = self._extract_course_id(current_url)
                if not course_id:
                    logger.error("无法从URL中提取课程ID")
                    return False

                # 构建上课进度页URL
                progress_url = f"https://manage.shengtongedu.cn/curriculum/#/curriculum/editCourse/progress?id={course_id}&operationAuthority=0"

                logger.info(f"跳转到上课进度页: {progress_url}")
                self.page.goto(progress_url)
                self.page.wait_for_load_state("networkidle")
                time.sleep(Config.PAGE_LOAD_WAIT * 2)

                # 验证跳转成功
                current_url = self.page.url
                logger.debug(f"跳转后URL: {current_url}")

                if "editCourse/progress" in current_url:
                    logger.success("已成功进入上课进度页")
                else:
                    logger.warning(f"跳转后URL可能未完全更新: {current_url}")

            # 等待课时树形结构加载
            logger.info("等待课时树形结构加载...")
            time.sleep(Config.PAGE_LOAD_WAIT)

            # ⭐⭐ 展开单元 ⭐⭐
            logger.info(f"尝试展开单元: {unit_num}")
            self._expand_unit(unit_num)

            # ⭐⭐ 点击课时 ⭐⭐
            logger.info(f"尝试点击课时: {session_name}")
            if self._click_lesson_by_name(session_name):
                return True
            else:
                # 备选方案：直接通过sessionCode跳转
                logger.info("尝试直接通过sessionCode跳转到课时详情页...")
                return self._navigate_directly_by_session_code(session_code)

        except Exception as e:
            logger.error(f"导航到课时页面失败: {e}", exc_info=True)
            return False

    def _safe_navigate_back(self):
        """安全返回到课时详情页"""
        try:
            current_url = self.page.url
            logger.debug(f"尝试恢复页面，当前URL: {current_url}")

            # 检查是否还在课时详情页
            if "courseDetail" in current_url and "sessionCode" in current_url:
                logger.debug("仍在课时详情页，尝试刷新或等待")
                self.page.reload()
                self.page.wait_for_load_state("networkidle")
                time.sleep(3)
                return True
            else:
                # 如果不在详情页，尝试返回
                logger.warning("页面可能已跳转，尝试返回")
                self.page.go_back()
                self.page.wait_for_load_state("networkidle")
                time.sleep(3)
                return True
        except Exception as e:
            logger.error(f"恢复页面失败: {e}")
            return False

    def _extract_course_id(self, url: str) -> Optional[str]:
        """从URL中提取课程ID"""
        try:
            # 使用正则表达式提取课程ID
            match = re.search(r'[?&]id=(\d+)', url)
            if match:
                return match.group(1)

            return None

        except Exception as e:
            logger.debug(f"提取课程ID失败: {e}")
            return None

    def _expand_unit(self, unit_num: str):
        """展开指定单元"""
        try:
            # 尝试查找单元元素
            unit_elements = self.page.locator(f"text={unit_num}").all()

            if not unit_elements:
                logger.warning(f"未找到单元文本: {unit_num}")
                # 使用XPath进行模糊匹配
                xpath_query = f"//*[contains(text(), '{unit_num[:5]}')]"  # 只匹配前5个字符
                unit_elements = self.page.locator(f"xpath={xpath_query}").all()

            logger.debug(f"找到 {len(unit_elements)} 个匹配单元元素")

            for unit_elem in unit_elements:
                try:
                    elem_text = unit_elem.inner_text().strip()
                    logger.debug(f"检查单元元素文本: {elem_text}")

                    # 检查是否是完全匹配
                    if unit_num in elem_text:
                        # 检查父元素是否是树节点
                        parent = unit_elem.locator("xpath=..")
                        parent_class = parent.get_attribute("class") or ""

                        if "el-tree-node" in parent_class:
                            # 检查是否有展开图标
                            expand_icon = parent.locator('.el-tree-node__expand-icon, .el-icon-arrow-right').first
                            if expand_icon.count() > 0:
                                # 检查是否已经展开
                                is_expanded = "is-expanded" in parent_class or "expanded" in parent_class

                                if not is_expanded:
                                    # 点击展开
                                    expand_icon.click()
                                    logger.success(f"已展开单元: {unit_num}")
                                    time.sleep(Config.CLICK_WAIT)
                                    return True
                                else:
                                    logger.info(f"单元 {unit_num} 已经展开")
                                    return True
                except Exception as e:
                    logger.debug(f"检查单元元素失败: {e}")
                    continue

            logger.warning(f"未找到可展开的单元: {unit_num}")
            return False

        except Exception as e:
            logger.debug(f"展开单元失败: {e}")
            return False

    def _click_lesson_by_name(self, session_name: str) -> bool:
        """通过课时名称点击课时"""
        try:
            # 方法1：通过文本查找课时
            lesson_elements = self.page.locator(f"text={session_name}").all()
            logger.debug(f"找到 {len(lesson_elements)} 个匹配课时元素")

            for lesson_elem in lesson_elements:
                try:
                    elem_text = lesson_elem.inner_text().strip()
                    logger.debug(f"检查课时元素文本: {elem_text}")

                    if session_name in elem_text:
                        # 检查父元素是否是课时节点
                        parent = lesson_elem.locator("xpath=..")
                        parent_class = parent.get_attribute("class") or ""

                        if "el-tree-node__content" in parent_class:
                            # 点击课时
                            lesson_elem.click()
                            logger.success(f"已点击课时: {session_name}")

                            # 等待页面加载
                            self.page.wait_for_load_state("networkidle")
                            time.sleep(Config.PAGE_LOAD_WAIT)

                            return True
                except Exception as e:
                    logger.debug(f"处理课时元素失败: {e}")
                    continue

            # 方法2：如果通过文本找不到，尝试通过XPath
            logger.info("通过文本查找失败，尝试XPath...")
            try:
                # 使用包含课时名称的XPath
                xpath_query = f"//*[contains(text(), '{session_name}')]"
                lesson_elements = self.page.locator(f"xpath={xpath_query}").all()

                for lesson_elem in lesson_elements:
                    try:
                        # 简单点击
                        lesson_elem.click()
                        logger.success(f"通过XPath点击课时: {session_name}")

                        self.page.wait_for_load_state("networkidle")
                        time.sleep(Config.PAGE_LOAD_WAIT)

                        return True
                    except:
                        continue
            except Exception as e:
                logger.debug(f"XPath查找失败: {e}")

            return False

        except Exception as e:
            logger.error(f"点击课时失败: {e}")
            return False

    def _navigate_directly_by_session_code(self, session_code: str) -> bool:
        """直接通过sessionCode跳转到课时详情页"""
        try:
            detail_url = f"https://manage.shengtongedu.cn/curriculum/#/curriculum/courseDetail?sessionCode={session_code}"
            logger.info(f"直接跳转到课时详情页: {detail_url}")

            self.page.goto(detail_url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(Config.PAGE_LOAD_WAIT)

            # 验证是否跳转成功
            current_url = self.page.url
            logger.debug(f"跳转后URL: {current_url}")

            if "sessionCode" in current_url:
                logger.success("已跳转到课时详情页")
                return True
            else:
                logger.warning("跳转后URL不符合预期")
                return False

        except Exception as e:
            logger.error(f"直接跳转失败: {e}")
            return False

    def _create_completion_marker(self, lesson_folder: Path, lesson_info: Dict):
        """创建下载完成标记文件"""
        if not lesson_folder:
            logger.warning("课时文件夹不存在，跳过创建完成标记")
            return

        try:
            completion_file = lesson_folder / "下载完成.txt"
            session_index = lesson_info.get("session_num", 1)
            session_name = lesson_info.get("session_name", "未知课时")

            with open(completion_file, 'w', encoding='utf-8') as f:
                f.write(f"课时 [{session_index:02d}] {session_name} 下载完成\n")
                f.write(f"完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"课时编码: {lesson_info.get('session_code', '未知')}\n")
            logger.debug(f"创建完成标记: {completion_file}")
        except Exception as e:
            logger.error(f"创建完成标记失败: {e}")


def get_all_lessons_info(course_data: Dict, token: str) -> List[Dict]:
    """获取课程的所有课时信息"""
    logger.progress("使用API获取所有单元和课时...")

    course_code = course_data.get("courseCode")
    if not course_code:
        logger.error("课程数据中没有courseCode字段")
        return []

    # 获取单元列表
    units_data = APIUtils.fetch_course_units(course_code, token)
    if not units_data:
        logger.error("未能获取任何单元信息")
        return []

    # 遍历单元，获取每个单元的课时
    all_lesson_info = []

    for unit_index, unit in enumerate(units_data, 1):
        unit_code = unit.get("courseUnitCode")
        unit_num = unit.get("courseUnitName") or f"第{unit_index}单元"
        unit_name = unit.get("courseUnitName") or "未知单元"

        logger.progress(f"处理单元 [{unit_index}/{len(units_data)}]: {unit_num}")

        # 获取该单元的所有课时
        if unit_code:
            sessions = APIUtils.fetch_unit_sessions(course_code, unit_code, token)
        else:
            logger.warning(f"单元 {unit_index} 没有courseUnitCode，跳过")
            sessions = []

        for sess_index, session in enumerate(sessions, 1):
            # 获取课时编码
            session_code = session.get("courseSessionCode")
            session_name = session.get("sessionName") or f"第{sess_index}节"

            # 获取单元内课时编号
            session_number = session.get("number")
            if session_number is None:
                session_number = sess_index

            if not session_code:
                session_code = session.get("id") or f"session_{session_number}"

            full_name = f"{unit_num} - {session_name}"

            all_lesson_info.append({
                "unit_num": unit_num,
                "unit_code": unit_code,
                "unit_name": unit_name,
                "session_num": session_number,
                "session_code": session_code,
                "session_name": session_name,
                "full_name": full_name
            })

            logger.debug(f"发现课时 [{session_number:02d}]: {full_name}")

    logger.success(f"汇总完成！总共识别到 {len(all_lesson_info)} 个课时")
    return all_lesson_info