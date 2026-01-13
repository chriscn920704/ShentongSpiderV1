# resource_detector.py
"""
智能资源检测器
根据Tab路径、元素特征和文件类型识别资源
"""
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from playwright.sync_api import Page, Locator
from logger import logger
from config import Config


class ResourceDetector:
    """资源检测器"""

    def __init__(self, page: Page):
        self.page = page

        # 资源类型映射
        self.resource_type_mapping = {
            # 文件扩展名 -> 类型
            ".mp4": "video",
            ".mp3": "audio",
            ".pdf": "pdf",
            ".pptx": "ppt",
            ".ppt": "ppt",
            ".sb3": "sb3",
            ".zip": "zip",
            ".rar": "archive",
            ".doc": "document",
            ".docx": "document",
            ".xls": "spreadsheet",
            ".xlsx": "spreadsheet",
            ".jpg": "image",
            ".jpeg": "image",
            ".png": "image",
            ".gif": "image",

            # 关键词 -> 类型
            "视频": "video",
            "课件": "ppt",
            "PPT": "ppt",
            "资料": "pdf",
            "编程题": "pdf",
            "程序": "zip",
            "讲义": "pdf",
            "教辅": "downloadable",
            "备课": "pdf",
            "项目文件": "sb3",
            "预置代码": "sb3",

            # 按钮文本 -> 下载方式
            "预览": "preview",
            "下载": "direct",
            "查看": "preview",
            "播放": "preview",
        }

        # 图标映射
        self.icon_mapping = {
            "video.png": "video",
            "ppt.png": "ppt",
            "sb3.png": "sb3",
            "zip.png": "zip",
            "pdf.png": "pdf",
            "doc.png": "document",
            "xls.png": "spreadsheet",
            "jpg.png": "image",
            "png.png": "image",
        }
        self.target_resource_types = [
            "pdf", "ppt", "video", "sb3", "zip", "archive",
            "downloadable", "document", "spreadsheet"
        ]

        # 新增：需要检测的文件扩展名
        self.target_extensions = [
            ".pdf", ".pptx", ".ppt", ".mp4", ".sb3", ".zip",
            ".rar", ".doc", ".docx", ".xls", ".xlsx"
        ]
    def _is_target_resource(self, resource_type: str, element_text: str) -> bool:
        """判断是否是需要下载的目标资源"""
        # 检查资源类型
        if resource_type in self.target_resource_types:
            return True

        # 检查文本中是否包含目标扩展名
        text_lower = element_text.lower()
        for ext in self.target_extensions:
            if ext in text_lower:
                return True

        # 检查是否包含特定关键词
        target_keywords = ["下载", "讲义", "课件", "资料", "视频", "程序", "教辅", "备课"]
        for keyword in target_keywords:
            if keyword in element_text:
                return True

        return False

    def detect_resources_in_tab(self, tab_path: List[str]) -> List[Dict]:
        """在指定Tab中检测资源 - 优化版"""
        resources = []

        try:
            # 1. 检测所有文件相关元素
            file_elements = self._find_file_elements()

            # 2. 检测所有按钮元素
            button_elements = self._find_button_elements()

            # 3. 合并并分析元素
            all_elements = file_elements + button_elements

            for element in all_elements:
                resource_info = self._analyze_element(element, tab_path)
                if resource_info:
                    # 过滤掉非目标资源
                    if self._is_target_resource(resource_info["resource_type"],
                                                resource_info["element_text"]):
                        resources.append(resource_info)

            # 去重
            resources = self._deduplicate_resources(resources)

            logger.info(f"在Tab '{' > '.join(tab_path)}' 中检测到 {len(resources)} 个目标资源")

        except Exception as e:
            logger.error(f"检测Tab资源失败: {e}")

        return resources

    def _find_file_elements(self) -> List[Locator]:
        """查找所有文件相关元素"""
        file_elements = []

        # 查找包含文件扩展名的元素
        file_extensions = [".mp4", ".pptx", ".pdf", ".sb3", ".zip", ".rar",
                           ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".png"]

        for ext in file_extensions:
            try:
                elements = self.page.locator(f"*:has-text('{ext}')").all()
                for elem in elements:
                    text = elem.inner_text().strip().lower()
                    if ext in text:
                        file_elements.append(elem)
            except:
                continue

        # 查找特定类名的元素
        special_classes = ["item_ppt", "resource_box", "tag_file", "video_item"]
        for cls in special_classes:
            try:
                elements = self.page.locator(f".{cls}").all()
                file_elements.extend(elements)
            except:
                continue

        return file_elements

    def _find_button_elements(self) -> List[Locator]:
        """查找所有按钮元素"""
        button_elements = []

        # 查找预览和下载按钮
        button_texts = ["预览", "下载", "查看", "播放"]
        for text in button_texts:
            try:
                elements = self.page.locator(f"span.file_btn:has-text('{text}'), "
                                             f"button:has-text('{text}'), "
                                             f"a:has-text('{text}')").all()
                button_elements.extend(elements)
            except:
                continue

        return button_elements

    def _analyze_element(self, element: Locator, tab_path: List[str]) -> Optional[Dict]:
        """分析单个元素，提取资源信息"""
        try:
            # 获取元素文本
            element_text = element.inner_text().strip()
            if not element_text:
                return None

            # 获取元素选择器
            selector = self._generate_selector(element)

            # 获取元素类名
            class_name = element.get_attribute("class") or ""

            # 获取图标信息
            icon_src = self._get_icon_src(element)

            # 获取父元素上下文
            context_text = self._get_context_text(element)

            # 识别资源类型
            resource_type = self._identify_resource_type(
                element_text, class_name, icon_src, context_text
            )

            # 识别下载方式
            download_method = self._identify_download_method(element_text, resource_type)

            # 提取文件名
            file_name = self._extract_file_name(element_text, resource_type)

            # 如果不是有效的资源类型，跳过
            if resource_type == "unknown" and not self._is_downloadable(element_text):
                return None

            # 构建资源信息
            resource_info = {
                "element_text": element_text[:200],
                "selector": selector,
                "class_name": class_name,
                "resource_type": resource_type,
                "download_method": download_method,
                "file_name": file_name,
                "tab_path": tab_path.copy(),  # 复制tab路径
                "icon_src": icon_src,
                "context_text": context_text[:100],
                "full_info": {
                    "tab_hierarchy": tab_path,
                    "element_details": {
                        "text": element_text,
                        "class": class_name,
                        "has_parent": self._has_parent_with_text(element, "下载") or
                                      self._has_parent_with_text(element, "预览")
                    }
                }
            }

            return resource_info

        except Exception as e:
            logger.debug(f"分析元素失败: {e}")
            return None

    def _identify_resource_type(self, text: str, class_name: str,
                                icon_src: str, context: str) -> str:
        """识别资源类型"""
        text_lower = text.lower()
        context_lower = context.lower()

        # 检查文件扩展名
        for ext, rtype in self.resource_type_mapping.items():
            if ext.startswith(".") and ext in text_lower:
                return rtype

        # 检查关键词
        for keyword, rtype in self.resource_type_mapping.items():
            if not keyword.startswith(".") and keyword in text:
                return rtype

        # 检查图标
        if icon_src:
            for icon_key, rtype in self.icon_mapping.items():
                if icon_key in icon_src:
                    return rtype

        # 检查上下文
        for keyword, rtype in self.resource_type_mapping.items():
            if not keyword.startswith(".") and keyword in context_lower:
                return rtype

        # 检查类名
        if "item_ppt" in class_name:
            if "pptx" in text_lower or "ppt" in text_lower:
                return "ppt"
            elif "pdf" in text_lower:
                return "pdf"
            elif "sb3" in text_lower:
                return "sb3"

        return "unknown"

    def _identify_download_method(self, text: str, resource_type: str) -> str:
        """识别下载方式"""
        text_lower = text.lower()

        # 根据按钮文本判断
        if "下载" in text:
            return "direct"
        elif "预览" in text:
            # 预览按钮可能有多种处理方式
            if resource_type == "pdf":
                return "preview_pdf"  # PDF预览需要特殊处理
            elif resource_type == "video":
                return "preview_video"
            elif resource_type == "ppt":
                return "preview_ppt"
            elif resource_type == "sb3":
                return "preview_sb3"
            else:
                return "preview"
        else:
            # 根据资源类型猜测
            if resource_type in ["zip", "archive", "downloadable"]:
                return "direct"
            else:
                return "preview"

    def _extract_file_name(self, text: str, resource_type: str) -> str:
        """从元素文本中提取文件名"""
        # 清理文本
        text = text.strip()

        # 尝试提取文件扩展名
        file_extensions = {
            "video": [".mp4", ".avi", ".mov", ".wmv"],
            "ppt": [".pptx", ".ppt"],
            "pdf": [".pdf"],
            "sb3": [".sb3"],
            "zip": [".zip", ".rar", ".7z"],
            "document": [".doc", ".docx"],
            "spreadsheet": [".xls", ".xlsx"],
            "image": [".jpg", ".jpeg", ".png", ".gif"]
        }

        # 查找已知扩展名
        if resource_type in file_extensions:
            for ext in file_extensions[resource_type]:
                if ext in text.lower():
                    # 提取文件名部分
                    parts = text.split(ext, 1)
                    if parts[0]:
                        filename = parts[0] + ext
                        # 清理文件名
                        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
                        return filename

        # 如果没有找到扩展名，返回清理后的文本
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', text)
        return safe_name[:100]

    def _get_icon_src(self, element: Locator) -> Optional[str]:
        """获取图标src"""
        try:
            # 查找元素内的img
            img = element.locator("img").first
            if img.count() > 0:
                return img.get_attribute("src")

            # 查找兄弟或父元素中的img
            parent = element.locator("xpath=..")
            img = parent.locator("img").first
            if img.count() > 0:
                return img.get_attribute("src")
        except:
            pass

        return None

    def _get_context_text(self, element: Locator) -> str:
        """获取上下文文本（父元素或兄弟元素的文本）"""
        try:
            # 获取父元素的文本
            parent = element.locator("xpath=..")
            if parent.count() > 0:
                parent_text = parent.inner_text()
                if parent_text and len(parent_text) > 10:
                    return parent_text

            # 获取前一个兄弟元素的文本
            prev_sibling = element.locator("xpath=preceding-sibling::*[1]")
            if prev_sibling.count() > 0:
                sibling_text = prev_sibling.inner_text()
                if sibling_text and len(sibling_text) > 5:
                    return sibling_text
        except:
            pass

        return ""

    def _generate_selector(self, element: Locator) -> str:
        """生成元素选择器"""
        try:
            # 尝试使用类名
            class_name = element.get_attribute("class")
            if class_name:
                classes = class_name.split()
                for cls in classes:
                    if cls and cls not in ["el-", "is-", "has-"] and len(cls) > 3:
                        return f".{cls}"

            # 尝试使用文本生成选择器
            text = element.inner_text().strip()
            if text and len(text) < 50:
                # 清理文本用于选择器
                clean_text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
                if clean_text:
                    return f"text='{clean_text}'"
        except:
            pass

        return ""

    def _has_parent_with_text(self, element: Locator, text: str) -> bool:
        """检查父元素是否包含特定文本"""
        try:
            parents = element.locator(f"xpath=ancestor::*[contains(text(), '{text}')]").all()
            return len(parents) > 0
        except:
            return False

    def _is_downloadable(self, text: str) -> bool:
        """判断元素是否可下载"""
        # 检查是否包含下载相关的关键词
        download_keywords = ["下载", "导出", "保存", "获取"]
        for keyword in download_keywords:
            if keyword in text:
                return True

        # 检查是否包含文件扩展名
        file_exts = [".mp4", ".pdf", ".pptx", ".ppt", ".sb3", ".zip", ".rar"]
        for ext in file_exts:
            if ext in text.lower():
                return True

        return False

    def _deduplicate_resources(self, resources: List[Dict]) -> List[Dict]:
        """去重资源列表"""
        seen = set()
        unique_resources = []

        for resource in resources:
            # 创建唯一标识
            key = (resource.get("element_text", ""),
                   resource.get("selector", ""),
                   " > ".join(resource.get("tab_path", [])))

            if key not in seen:
                seen.add(key)
                unique_resources.append(resource)

        return unique_resources

    def get_current_tab_hierarchy(self) -> List[str]:
        """
        获取当前Tab的层级路径

        Returns:
            Tab路径列表，如 ["课前预习", "视频"]
        """
        tab_hierarchy = []

        try:
            # 获取一级Tab
            primary_tabs = self.page.locator('.el-tabs__header.is-top .el-tabs__item.is-active')
            if primary_tabs.count() > 0:
                primary_tab_text = primary_tabs.first.inner_text().strip()
                if primary_tab_text:
                    tab_hierarchy.append(primary_tab_text)

            # 获取二级Tab
            secondary_tabs = self.page.locator('.el-tabs--left .el-tabs__item.is-active, '
                                               '.el-tabs--card .el-tabs__item.is-active')
            if secondary_tabs.count() > 0:
                secondary_tab_text = secondary_tabs.first.inner_text().strip()
                if secondary_tab_text:
                    tab_hierarchy.append(secondary_tab_text)

        except Exception as e:
            logger.debug(f"获取Tab层级失败: {e}")

        return tab_hierarchy if tab_hierarchy else ["未知Tab"]


class TabExplorer:
    """Tab探索器，负责遍历所有Tab"""

    def __init__(self, page: Page):
        self.page = page
        self.detector = ResourceDetector(page)

    def explore_all_tabs(self) -> Dict[str, List[Dict]]:
        """
        探索所有Tab中的资源

        Returns:
            按Tab路径分组的资源字典
        """
        all_resources = {}

        try:
            # 获取所有一级Tab
            primary_tabs = self.page.locator('.el-tabs__header.is-top .el-tabs__item').all()
            logger.info(f"找到 {len(primary_tabs)} 个一级Tab")

            for primary_tab in primary_tabs:
                try:
                    primary_name = primary_tab.inner_text().strip()
                    if not primary_name:
                        continue

                    logger.info(f"探索一级Tab: {primary_name}")

                    # 点击激活Tab
                    if "is-active" not in (primary_tab.get_attribute("class") or ""):
                        primary_tab.click()
                        self.page.wait_for_load_state("networkidle")
                        import time
                        time.sleep(Config.CLICK_WAIT)

                    # 探索当前一级Tab下的二级Tab
                    secondary_resources = self._explore_secondary_tabs(primary_name)

                    # 如果没有二级Tab，直接检测当前Tab
                    if not secondary_resources:
                        tab_path = [primary_name]
                        resources = self.detector.detect_resources_in_tab(tab_path)
                        if resources:
                            all_resources[" > ".join(tab_path)] = resources
                    else:
                        all_resources.update(secondary_resources)

                except Exception as e:
                    logger.error(f"探索Tab '{primary_name}' 失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"探索所有Tab失败: {e}")

        return all_resources

    def _explore_secondary_tabs(self, primary_name: str) -> Dict[str, List[Dict]]:
        """探索二级Tab"""
        secondary_resources = {}

        try:
            # 查找二级Tab容器
            secondary_containers = self.page.locator(
                '.tabmain.el-tabs.el-tabs--card.el-tabs--left, '
                'div.tabmain, '
                '.el-tabs__content .el-tabs'
            ).all()

            if not secondary_containers:
                return {}

            # 使用第一个容器
            container = secondary_containers[0]

            # 获取所有二级Tab
            secondary_tabs = container.locator('.el-tabs__item').all()
            logger.info(f"在 '{primary_name}' 下找到 {len(secondary_tabs)} 个二级Tab")

            for secondary_tab in secondary_tabs:
                try:
                    secondary_name = secondary_tab.inner_text().strip()
                    if not secondary_name:
                        continue

                    tab_path = [primary_name, secondary_name]
                    tab_key = " > ".join(tab_path)

                    logger.info(f"探索二级Tab: {tab_key}")

                    # 点击激活二级Tab
                    if "is-active" not in (secondary_tab.get_attribute("class") or ""):
                        secondary_tab.click()
                        self.page.wait_for_load_state("networkidle")
                        import time
                        time.sleep(Config.CLICK_WAIT)

                    # 检测资源
                    resources = self.detector.detect_resources_in_tab(tab_path)
                    if resources:
                        secondary_resources[tab_key] = resources

                except Exception as e:
                    logger.error(f"探索二级Tab '{secondary_name}' 失败: {e}")
                    continue

        except Exception as e:
            logger.debug(f"探索二级Tab失败: {e}")

        return secondary_resources