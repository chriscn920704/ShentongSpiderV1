# downloader.py
"""
资源下载管理器 - 增强版
整合PDF解析和直接下载功能
"""
import os
import time
import json
import hashlib
import threading
import queue
import re
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import requests
from playwright.sync_api import Page, BrowserContext, Response, expect
from logger import logger
from config import Config
from resource_detector import ResourceDetector, TabExplorer

class DownloadTask:
    """单个下载任务的数据结构"""

    def __init__(self, task_id: str, task_info: Dict):
        self.task_id = task_id
        self.task_info = task_info
        self.status = "pending"  # pending, downloading, completed, failed
        self.progress = 0.0
        self.start_time = None
        self.end_time = None
        self.error_message = None
        self.file_path = None

        # 解析任务信息
        self.resource_type = task_info.get("resource_type", "unknown")
        self.resource_name = task_info.get("resource_name", "unnamed")
        self.file_name = task_info.get("file_name", "unnamed")
        self.download_method = task_info.get("download_method", "direct")  # direct, preview_pdf, etc.
        self.element_selector = task_info.get("selector")
        self.lesson_info = task_info.get("lesson_info", {})
        self.tab_path = task_info.get("tab_path", ["未知Tab"])
        self.destination_dir = task_info.get("destination_dir")

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "file_name": self.file_name,
            "tab_path": " > ".join(self.tab_path),
            "status": self.status,
            "progress": self.progress,
            "file_path": str(self.file_path) if self.file_path else None,
            "error_message": self.error_message,
            "duration": (self.end_time - self.start_time).total_seconds()
            if self.start_time and self.end_time else None
        }


class DownloadManager:
    """下载管理器 - 增强版"""

    def __init__(self,
                 browser_page: Page,
                 max_concurrent: int = 2,
                 download_timeout: int = 300,
                 max_retries: int = 3):
        """
        初始化下载管理器

        Args:
            browser_page: Playwright页面对象
            max_concurrent: 最大并发下载数
            download_timeout: 下载超时时间（秒）
            max_retries: 最大重试次数
        """
        self.page = browser_page
        self.context = browser_page.context
        self.max_concurrent = max_concurrent
        self.download_timeout = download_timeout
        self.max_retries = max_retries

        # 任务管理
        self.task_queue = queue.Queue()
        self.active_tasks: Dict[str, DownloadTask] = {}
        self.completed_tasks: List[DownloadTask] = []
        self.failed_tasks: List[DownloadTask] = []

        # 统计信息
        self.total_tasks = 0
        self.completed_count = 0
        self.failed_count = 0

        # 线程控制
        self.worker_threads = []
        self.is_running = False
        self.download_event = threading.Event()

        # 工具类
        self.detector = ResourceDetector(browser_page)
        self.tab_explorer = TabExplorer(browser_page)

        # 下载路径配置
        self.base_download_dir = Config.DOWNLOAD_BASE_DIR
        self.base_download_dir.mkdir(exist_ok=True)

        # 文件类型映射
        self.file_type_extensions = Config.FILE_TYPE_EXTENSIONS.copy()

        logger.info(f"下载管理器初始化完成，最大并发数: {max_concurrent}")

    def start(self):
        """启动下载管理器"""
        if self.is_running:
            logger.warning("下载管理器已经在运行")
            return

        self.is_running = True
        self.download_event.clear()

        # 启动工作线程
        for i in range(self.max_concurrent):
            thread = threading.Thread(
                target=self._download_worker,
                name=f"DownloadWorker-{i + 1}",
                daemon=True
            )
            thread.start()
            self.worker_threads.append(thread)

        logger.success("下载管理器已启动")

    def stop(self):
        """停止下载管理器"""
        self.is_running = False
        self.download_event.set()

        # 等待工作线程结束
        for thread in self.worker_threads:
            thread.join(timeout=5)

        self.worker_threads.clear()
        logger.info("下载管理器已停止")

    def add_task(self, task_info: Dict) -> str:
        """
        添加下载任务

        Args:
            task_info: 任务信息字典

        Returns:
            任务ID
        """
        task_id = self._generate_task_id(task_info)
        task = DownloadTask(task_id, task_info)

        self.task_queue.put(task)
        self.total_tasks += 1

        logger.debug(
            f"添加下载任务: {task.resource_name} (类型: {task.resource_type}, Tab: {' > '.join(task.tab_path)})")
        return task_id

    def add_batch_tasks(self, tasks_info: List[Dict]) -> List[str]:
        """批量添加下载任务"""
        task_ids = []
        for task_info in tasks_info:
            task_id = self.add_task(task_info)
            task_ids.append(task_id)

        logger.info(f"批量添加 {len(tasks_info)} 个下载任务")
        return task_ids

    def wait_for_completion(self, timeout: Optional[int] = None):
        """
        等待所有任务完成

        Args:
            timeout: 超时时间（秒），None表示无限等待
        """
        start_time = time.time()

        while self.total_tasks > (self.completed_count + self.failed_count):
            # 检查超时
            if timeout and (time.time() - start_time) > timeout:
                logger.warning("等待任务完成超时")
                break

            # 打印进度
            remaining = self.total_tasks - (self.completed_count + self.failed_count)
            logger.info(f"等待任务完成: {self.completed_count}完成, "
                        f"{self.failed_count}失败, {remaining}进行中")

            time.sleep(2)

        logger.success("所有下载任务已完成")

    def get_stats(self) -> Dict:
        """获取下载统计信息"""
        return {
            "total_tasks": self.total_tasks,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "in_progress": len(self.active_tasks),
            "pending": self.task_queue.qsize(),
            "success_rate": (self.completed_count / self.total_tasks * 100
                             if self.total_tasks > 0 else 0)
        }

    def _download_worker(self):
        """下载工作线程"""
        while self.is_running:
            try:
                # 从队列获取任务（非阻塞）
                try:
                    task = self.task_queue.get(timeout=1)
                except queue.Empty:
                    continue

                # 标记为激活状态
                task.status = "downloading"
                task.start_time = datetime.now()
                self.active_tasks[task.task_id] = task

                # 执行下载（最多重试max_retries次）
                success = False
                for retry in range(self.max_retries):
                    if retry > 0:
                        logger.info(f"重试下载 {task.resource_name} (第{retry + 1}次)")

                    success = self._execute_download(task)

                    if success:
                        break
                    else:
                        time.sleep(2 ** retry)  # 指数退避

                # 更新任务状态
                task.end_time = datetime.now()
                if success:
                    task.status = "completed"
                    task.progress = 100.0
                    self.completed_tasks.append(task)
                    self.completed_count += 1
                    logger.success(f"下载完成: {task.resource_name}")
                else:
                    task.status = "failed"
                    self.failed_tasks.append(task)
                    self.failed_count += 1
                    logger.error(f"下载失败: {task.resource_name} - {task.error_message}")

                # 从激活任务中移除
                del self.active_tasks[task.task_id]
                self.task_queue.task_done()

            except Exception as e:
                logger.error(f"下载工作线程异常: {e}", exc_info=True)
                time.sleep(5)

    def _execute_download(self, task: DownloadTask) -> bool:
        """
        执行单个下载任务

        Args:
            task: 下载任务对象

        Returns:
            是否成功
        """
        try:
            # 根据下载方式选择执行策略
            if task.download_method == "direct":
                return self._download_direct(task)
            elif task.download_method == "preview_pdf":
                return self._download_preview_pdf(task)
            elif task.download_method.startswith("preview"):
                # 其他预览类型（视频、PPT、SB3等）暂时不支持
                task.error_message = f"预览下载方式 '{task.download_method}' 暂未实现"
                return False
            else:
                # 尝试通用下载
                if task.element_selector:
                    return self._download_by_selector(task)
                else:
                    task.error_message = f"不支持的下载方式: {task.download_method}"
                    return False

        except Exception as e:
            task.error_message = str(e)
            logger.error(f"下载执行失败: {task.resource_name} - {e}", exc_info=True)
            return False

    def _download_direct(self, task: DownloadTask) -> bool:
        """
        直接下载（有下载按钮）

        Args:
            task: 下载任务对象

        Returns:
            是否成功
        """
        try:
            # 确保在正确的Tab
            self._ensure_tab_context(task.tab_path)

            # 等待元素加载
            if not task.element_selector:
                task.error_message = "没有有效的元素选择器"
                return False

            logger.info(f"准备直接下载: {task.resource_name}")

            # 定位元素
            element = self.page.locator(task.element_selector).first
            if element.count() == 0:
                task.error_message = f"找不到元素: {task.element_selector}"
                return False

            # 点击下载
            with self.page.expect_download(timeout=self.download_timeout * 1000) as download_info:
                element.click()
                time.sleep(1)

            # 获取下载对象
            download = download_info.value

            # 确定保存路径
            file_path = self._get_file_path(task)

            # 保存文件
            download.save_as(str(file_path))

            # 验证文件
            if os.path.getsize(file_path) > 0:
                task.file_path = file_path

                # 计算文件哈希
                file_hash = self._calculate_file_hash(file_path)
                logger.debug(f"直接下载完成: {file_path.name} (大小: {os.path.getsize(file_path)} bytes)")

                # 保存下载记录
                self._save_download_record(task, file_hash)
                return True
            else:
                task.error_message = "下载的文件大小为0"
                if os.path.exists(file_path):
                    os.remove(file_path)
                return False

        except Exception as e:
            task.error_message = f"直接下载失败: {e}"
            return False

    def _download_preview_pdf(self, task: DownloadTask) -> bool:
        """
        预览下载PDF（点击预览按钮，解析新标签页URL）

        Args:
            task: 下载任务对象

        Returns:
            是否成功
        """
        try:
            # 确保在正确的Tab
            self._ensure_tab_context(task.tab_path)

            # 等待元素加载
            if not task.element_selector:
                task.error_message = "没有有效的元素选择器"
                return False

            logger.info(f"准备下载PDF: {task.resource_name}")

            # 定位元素
            element = self.page.locator(task.element_selector).first
            if element.count() == 0:
                task.error_message = f"找不到元素: {task.element_selector}"
                return False

            # 点击预览，等待新标签页打开
            with self.page.expect_popup(timeout=self.download_timeout * 1000) as popup_info:
                element.click()
                time.sleep(2)

            # 获取新标签页
            new_page = popup_info.value
            new_page.wait_for_load_state("networkidle")
            time.sleep(2)

            # 获取新页面的URL
            page_url = new_page.url
            logger.debug(f"新标签页URL: {page_url}")

            # 提取真实的PDF链接
            pdf_url = self._extract_pdf_url_from_preview(page_url)

            if not pdf_url:
                task.error_message = "无法从预览页面提取PDF链接"
                new_page.close()
                return False

            logger.info(f"提取到PDF链接: {pdf_url[:100]}...")

            # 确定保存路径
            file_path = self._get_file_path(task)

            # 下载PDF文件
            success = self._download_from_url(pdf_url, file_path, task)

            # 关闭新标签页
            new_page.close()

            if success:
                task.file_path = file_path
                return True
            else:
                return False

        except Exception as e:
            task.error_message = f"PDF预览下载失败: {e}"
            return False

    def _download_by_selector(self, task: DownloadTask) -> bool:
        """
        通过选择器下载（通用方法）

        Args:
            task: 下载任务对象

        Returns:
            是否成功
        """
        try:
            # 确保在正确的Tab
            self._ensure_tab_context(task.tab_path)

            # 定位元素
            element = self.page.locator(task.element_selector).first
            if element.count() == 0:
                task.error_message = f"找不到元素: {task.element_selector}"
                return False

            # 获取元素文本
            element_text = element.inner_text().strip().lower()

            # 根据元素文本判断下载方式
            if "下载" in element_text:
                # 直接下载
                return self._download_direct(task)
            elif "预览" in element_text:
                # 如果是PDF，尝试预览下载
                if task.resource_type == "pdf":
                    return self._download_preview_pdf(task)
                else:
                    task.error_message = f"预览下载类型 '{task.resource_type}' 暂不支持"
                    return False
            else:
                task.error_message = f"无法识别的按钮文本: {element_text}"
                return False

        except Exception as e:
            task.error_message = f"选择器下载失败: {e}"
            return False

    def _download_from_url(self, url: str, file_path: Path, task: DownloadTask) -> bool:
        """
        从URL下载文件

        Args:
            url: 下载URL
            file_path: 保存路径
            task: 下载任务对象

        Returns:
            是否成功
        """
        try:
            # 设置请求头
            headers = {
                'User-Agent': Config.USER_AGENT,
                'Accept': 'application/pdf,application/x-pdf,*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://manage.shengtongedu.cn/',
            }

            # 获取页面的cookies用于认证
            cookies = {}
            page_cookies = self.page.context.cookies()
            for cookie in page_cookies:
                cookies[cookie['name']] = cookie['value']

            logger.debug(f"使用 {len(cookies)} 个cookies进行认证")

            # 发送请求
            session = requests.Session()
            if cookies:
                session.cookies.update(cookies)

            response = session.get(
                url,
                headers=headers,
                stream=True,
                timeout=self.download_timeout
            )

            if response.status_code != 200:
                task.error_message = f"HTTP错误: {response.status_code}"
                return False

            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))

            # 写入文件
            with open(file_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # 更新进度
                        if total_size > 0:
                            task.progress = (downloaded / total_size) * 100

            # 验证文件
            if os.path.getsize(file_path) > 0:
                # 计算文件哈希
                file_hash = self._calculate_file_hash(file_path)
                logger.debug(f"URL下载完成: {file_path.name} (大小: {os.path.getsize(file_path)} bytes)")
                return True
            else:
                task.error_message = "下载的文件大小为0"
                if os.path.exists(file_path):
                    os.remove(file_path)
                return False

        except Exception as e:
            task.error_message = f"URL下载失败: {e}"
            return False

    def _extract_pdf_url_from_preview(self, page_url: str) -> Optional[str]:
        """
        从预览页面URL中提取真实的PDF链接

        Args:
            page_url: 预览页面URL

        Returns:
            真实的PDF链接，如果提取失败则返回None
        """
        try:
            # 解析URL
            parsed = urlparse(page_url)

            # 方法1: 从查询参数中提取双重编码的URL
            query_params = parse_qs(parsed.query)
            if 'url' in query_params:
                encoded_url = query_params['url'][0]
                # 双重解码
                pdf_url = unquote(unquote(encoded_url))
                if pdf_url.startswith('https://') and '.pdf' in pdf_url.lower():
                    return pdf_url

            # 方法2: 从URL片段中提取
            if parsed.fragment:
                # 片段中可能包含查询参数
                fragment_parts = parsed.fragment.split('?')
                if len(fragment_parts) > 1:
                    fragment_params = parse_qs(fragment_parts[1])
                    if 'url' in fragment_params:
                        encoded_url = fragment_params['url'][0]
                        pdf_url = unquote(unquote(encoded_url))
                        if pdf_url.startswith('https://') and '.pdf' in pdf_url.lower():
                            return pdf_url

            # 方法3: 正则匹配OSS链接
            oss_pattern = r'(https://public-[a-zA-Z0-9-]+\.oss[^&"\']+\.pdf)'
            matches = re.findall(oss_pattern, page_url)
            if matches:
                return unquote(unquote(matches[0]))

            return None

        except Exception as e:
            logger.debug(f"提取PDF链接失败: {e}")
            return None

    def _ensure_tab_context(self, tab_path: List[str]):
        """
        确保页面在正确的Tab上下文中

        Args:
            tab_path: Tab路径列表
        """
        try:
            if len(tab_path) < 1:
                return

            # 激活一级Tab
            primary_tab = self.page.locator(f'.el-tabs__header.is-top .el-tabs__item:has-text("{tab_path[0]}")').first
            if primary_tab.count() > 0:
                if "is-active" not in (primary_tab.get_attribute("class") or ""):
                    primary_tab.click()
                    self.page.wait_for_load_state("networkidle")
                    time.sleep(Config.CLICK_WAIT)

            # 如果有二级Tab，激活二级Tab
            if len(tab_path) > 1:
                secondary_tab = self.page.locator(f'.el-tabs--left .el-tabs__item:has-text("{tab_path[1]}"), '
                                                  f'.el-tabs--card .el-tabs__item:has-text("{tab_path[1]}")').first
                if secondary_tab.count() > 0:
                    if "is-active" not in (secondary_tab.get_attribute("class") or ""):
                        secondary_tab.click()
                        self.page.wait_for_load_state("networkidle")
                        time.sleep(Config.CLICK_WAIT)

        except Exception as e:
            logger.debug(f"切换Tab上下文失败: {e}")

    def _get_file_path(self, task: DownloadTask) -> Path:
        """
        生成文件保存路径（基于Tab路径）

        Args:
            task: 下载任务对象

        Returns:
            完整的文件路径
        """
        # 基础目录
        base_dir = task.destination_dir or self.base_download_dir

        # 课程信息
        lesson_info = task.lesson_info
        if lesson_info:
            # 课程文件夹
            course_name = lesson_info.get("course_name", "未知课程")
            safe_course_name = self._sanitize_filename(course_name)

            # 课时文件夹
            session_num = lesson_info.get("session_num", 1)
            session_name = lesson_info.get("session_name", "未知课时")
            safe_session_name = self._sanitize_filename(f"{session_num:02d}_{session_name}")

            # Tab路径文件夹
            tab_path_str = "_".join(task.tab_path)
            safe_tab_path = self._sanitize_filename(tab_path_str) if tab_path_str else "未知Tab"

            # 资源类型文件夹
            resource_type_dir = task.resource_type

            # 完整路径
            file_dir = base_dir / safe_course_name / safe_session_name / safe_tab_path / resource_type_dir
        else:
            # 没有课时信息时使用简化路径
            tab_path_str = "_".join(task.tab_path)
            safe_tab_path = self._sanitize_filename(tab_path_str) if tab_path_str else "未知Tab"
            file_dir = base_dir / safe_tab_path / task.resource_type

        # 确保目录存在
        file_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_file_name = self._sanitize_filename(task.file_name)

        # 获取文件扩展名
        extension = self.file_type_extensions.get(task.resource_type, ".dat")

        # 如果文件名已经有正确的扩展名，就不再加了
        if safe_file_name.lower().endswith(tuple(self.file_type_extensions.values())):
            filename = f"{timestamp}_{safe_file_name}"
        else:
            filename = f"{timestamp}_{safe_file_name}{extension}"

        return file_dir / filename

    def _save_download_record(self, task: DownloadTask, file_hash: str):
        """保存下载记录到JSON文件"""
        try:
            record_dir = task.file_path.parent if task.file_path else self.base_download_dir
            record_file = record_dir / "下载记录.json"

            # 读取现有记录
            records = []
            if record_file.exists():
                with open(record_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)

            # 添加新记录
            record = {
                "timestamp": datetime.now().isoformat(),
                "task_id": task.task_id,
                "resource_name": task.resource_name,
                "resource_type": task.resource_type,
                "file_name": task.file_path.name if task.file_path else "未知",
                "file_size": os.path.getsize(task.file_path) if task.file_path and task.file_path.exists() else 0,
                "file_hash": file_hash,
                "tab_path": " > ".join(task.tab_path),
                "status": task.status,
                "lesson_info": task.lesson_info,
                "download_method": task.download_method
            }

            records.append(record)

            # 保存记录
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.debug(f"保存下载记录失败: {e}")

    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件的MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        # 替换非法字符为下划线，限制长度
        clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
        # 移除连续的下划线和首尾空格
        clean = re.sub(r'_+', '_', clean).strip(' _')
        # 限制长度
        return clean[:100]

    def _generate_task_id(self, task_info: Dict) -> str:
        """生成任务ID"""
        import uuid
        # 基于资源信息和时间戳生成唯一ID
        resource_str = f"{task_info.get('resource_name', '')}_{task_info.get('resource_type', '')}"
        timestamp = int(time.time() * 1000)
        unique_id = uuid.uuid4().hex[:8]

        return f"task_{timestamp}_{unique_id}"

    def export_report(self, report_path: Optional[Path] = None) -> Path:
        """
        导出下载报告

        Args:
            report_path: 报告保存路径，None则使用默认路径

        Returns:
            报告文件路径
        """
        if report_path is None:
            report_path = self.base_download_dir / "下载报告.json"

        report_data = {
            "generated_at": datetime.now().isoformat(),
            "statistics": self.get_stats(),
            "completed_tasks": [task.to_dict() for task in self.completed_tasks],
            "failed_tasks": [task.to_dict() for task in self.failed_tasks],
            "summary": {
                "total_files": len(self.completed_tasks),
                "total_size": sum(os.path.getsize(task.file_path)
                                  for task in self.completed_tasks
                                  if task.file_path and task.file_path.exists()),
                "success_rate": self.get_stats()["success_rate"]
            }
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.success(f"下载报告已导出: {report_path}")
        return report_path

    def explore_and_download(self, lesson_info: Dict, download_dir: Path) -> bool:
        """
        探索并下载课时资源（一站式接口）

        Args:
            lesson_info: 课时信息
            download_dir: 下载目录

        Returns:
            是否成功
        """
        try:
            logger.separator("开始资源探索与下载")

            # 1. 探索所有Tab中的资源
            logger.info("探索所有Tab中的资源...")
            all_resources = self.tab_explorer.explore_all_tabs()

            # 汇总统计
            total_resources = sum(len(resources) for resources in all_resources.values())
            logger.info(f"总共发现 {total_resources} 个资源，分布在 {len(all_resources)} 个Tab中")

            # 显示Tab资源分布
            for tab_path, resources in all_resources.items():
                logger.info(f"  {tab_path}: {len(resources)} 个资源")
                for resource in resources[:3]:  # 显示前3个
                    logger.debug(f"    - {resource['resource_type']}: {resource['file_name']}")
                if len(resources) > 3:
                    logger.debug(f"    ... 还有 {len(resources) - 3} 个资源")

            if total_resources == 0:
                logger.warning("未发现任何资源，跳过下载")
                return False

            # 2. 过滤出可下载的资源（目前只支持PDF和直接下载）
            downloadable_resources = []
            for tab_path, resources in all_resources.items():
                for resource in resources:
                    # 只处理PDF和直接下载的资源
                    if resource['resource_type'] == 'pdf' or resource['download_method'] == 'direct':
                        # 添加课时信息和下载目录
                        resource['lesson_info'] = lesson_info
                        resource['destination_dir'] = download_dir
                        downloadable_resources.append(resource)

            logger.info(f"筛选出 {len(downloadable_resources)} 个可下载资源（PDF和直接下载）")

            if len(downloadable_resources) == 0:
                logger.warning("没有可下载的资源（目前只支持PDF和直接下载）")
                return False

            # 3. 启动下载管理器
            self.start()

            # 4. 添加下载任务
            task_ids = self.add_batch_tasks(downloadable_resources)

            # 5. 等待下载完成（最多10分钟）
            self.wait_for_completion(timeout=600)

            # 6. 获取统计信息
            stats = self.get_stats()
            logger.info(
                f"下载统计: {stats['completed']}成功, {stats['failed']}失败, 成功率: {stats['success_rate']:.1f}%")

            # 7. 导出报告
            report_path = download_dir / "下载报告.json"
            self.export_report(report_path)

            # 8. 停止下载管理器
            self.stop()

            logger.success(f"资源下载完成！报告: {report_path}")
            return stats['completed'] > 0

        except Exception as e:
            logger.error(f"探索下载失败: {e}", exc_info=True)
            return False


# 简化接口
class SimpleDownloader:
    """简化版下载器"""

    def __init__(self, page: Page):
        self.page = page
        self.download_manager = DownloadManager(page, max_concurrent=2)

    def download_resources(self, lesson_info: Dict, download_dir: Path) -> bool:
        """
        下载课时资源

        Args:
            lesson_info: 课时信息
            download_dir: 下载目录

        Returns:
            是否成功
        """
        return self.download_manager.explore_and_download(lesson_info, download_dir)