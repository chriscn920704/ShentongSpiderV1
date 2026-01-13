# browser_manager.py
import time
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright, Page, BrowserContext, Browser
from config import Config
from logger import logger


class BrowserManager:
    """浏览器管理类"""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()

    def start(self):
        """启动浏览器"""
        logger.progress("启动Chromium浏览器...")

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=['--start-maximized', '--disable-blink-features=AutomationControlled']
        )

        self.context = self.browser.new_context(
            no_viewport=False,
            user_agent=Config.USER_AGENT
        )

        # 注入反检测脚本
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """)

        self.page = self.context.new_page()
        self.page.set_viewport_size(Config.VIEWPORT_SIZE)
        self.page.set_default_timeout(15000)

        logger.success("浏览器启动成功")

    def stop(self):
        """停止浏览器"""
        if self.browser and self.browser.is_connected():
            self.browser.close()
            logger.debug("浏览器已关闭")

        if self.playwright:
            self.playwright.stop()

    def navigate_to(self, url: str, wait_for_network_idle: bool = True):
        """导航到指定URL"""
        logger.progress(f"导航到: {url}")

        options = {}
        if wait_for_network_idle:
            options['wait_until'] = 'networkidle'

        self.page.goto(url, **options)
        time.sleep(Config.PAGE_LOAD_WAIT)

    def login(self) -> bool:
        """执行登录流程"""
        try:
            logger.progress("正在访问登录页面...")
            self.navigate_to(Config.LOGIN_URL)

            logger.progress("填写登录表单...")
            self.page.fill('input[placeholder="手机号"]', Config.PHONE_NUMBER)
            self.page.fill('input[placeholder="密码"]', 'Wenji321')  # 密码应该从配置读取
            self.page.locator('input[placeholder="密码"]').press('Enter')
            logger.info("已提交登录表单")

            time.sleep(Config.PAGE_LOAD_WAIT)

            # 处理隐私协议弹窗
            logger.progress("处理隐私协议弹窗...")
            try:
                self.page.wait_for_selector('button.el-button--primary >> text=允许获取', timeout=8000)
                self.page.click('button.el-button--primary >> text=允许获取')
                logger.info("已点击'允许获取'按钮")
                time.sleep(Config.CLICK_WAIT)
            except:
                logger.debug("未找到弹窗或已消失")

            # 等待登录完成
            logger.progress("等待登录完成，进入分屏主页...")
            try:
                self.page.wait_for_selector('p.product_name:has-text("一校教培")', timeout=20000)
                logger.success("分屏主页加载完成")
            except:
                logger.warning("等待主页超时，尝试继续...")

            time.sleep(Config.PAGE_LOAD_WAIT)

            return True

        except Exception as e:
            logger.error(f"登录失败: {e}", exc_info=True)
            return False

    def navigate_to_course_management(self) -> bool:
        """导航到课程管理页面"""
        try:
            logger.progress("在分屏主页点击'一校教培'入口...")

            element = self.page.locator('li:has(p.product_name:has-text("一校教培"))')
            if element.count() > 0:
                element.scroll_into_view_if_needed()
                time.sleep(Config.CLICK_WAIT)
                element.click()
                logger.success("已点击'一校教培'图标")

                self.page.wait_for_load_state('networkidle', timeout=10000)
                time.sleep(Config.PAGE_LOAD_WAIT)
                return True
            else:
                logger.warning("未找到'一校教培'入口，尝试直接导航")

                self.navigate_to(Config.COURSE_MANAGE_URL)
                return True

        except Exception as e:
            logger.error(f"导航到课程管理页面失败: {e}")

            # 尝试直接导航
            try:
                self.navigate_to(Config.COURSE_MANAGE_URL)
                return True
            except:
                return False

    def get_token(self) -> Optional[str]:
        """从浏览器获取Token"""
        logger.progress("从浏览器获取认证信息...")

        # 尝试从多种来源获取Token
        token_sources = [
            self._get_token_from_cookies,
            self._get_token_from_localstorage,
            self._get_token_from_sessionstorage,
            self._get_token_from_window,
        ]

        for source in token_sources:
            try:
                token = source()
                if token:
                    logger.success(f"Token获取成功: {token[:40]}...")
                    return token
            except Exception as e:
                logger.debug(f"Token获取失败: {source.__name__} - {e}")

        logger.error("无法获取有效的Token")
        return None

    def _get_token_from_cookies(self) -> Optional[str]:
        """从Cookies获取Token"""
        cookies = self.context.cookies()
        for cookie in cookies:
            if 'token' in cookie['name'].lower():
                return cookie['value']
        return None

    def _get_token_from_localstorage(self) -> Optional[str]:
        """从LocalStorage获取Token"""
        return self.page.evaluate("() => localStorage.getItem('token')")

    def _get_token_from_sessionstorage(self) -> Optional[str]:
        """从SessionStorage获取Token"""
        return self.page.evaluate("() => sessionStorage.getItem('token')")

    def _get_token_from_window(self) -> Optional[str]:
        """从window对象获取Token"""
        return self.page.evaluate("() => window.token || window.TOKEN || null")

    # 在 browser_manager.py 中添加以下方法

    def navigate_to_course_detail(self, course_code: str) -> bool:
        """导航到课程详情页"""
        try:
            # 方法1：通过URL直接进入课程详情页
            # 注意：需要确认课程详情页URL的模式
            # 可能是：https://manage.shengtongedu.cn/curriculum/#/curriculum/courseDetail?courseCode={course_code}
            course_detail_url = f"https://manage.shengtongedu.cn/curriculum/#/curriculum/courseDetail?courseCode={course_code}"

            logger.progress(f"导航到课程详情页: {course_code}")
            self.navigate_to(course_detail_url)

            # 等待课程详情页加载
            time.sleep(Config.PAGE_LOAD_WAIT * 2)

            # 检查是否成功进入课程详情页
            # 可以检查一些课程详情页特有的元素
            try:
                # 检查课程名称元素
                self.page.wait_for_selector('h1.course-title, div.course-header, .course-name', timeout=10000)
                logger.success("课程详情页加载成功")
                return True
            except:
                logger.warning("未检测到课程详情页特有元素，尝试其他方式")

                # 方法2：尝试通过页面上的课程点击
                return self._navigate_to_course_detail_by_click(course_code)

        except Exception as e:
            logger.error(f"导航到课程详情页失败: {e}")
            return False

    # 在 browser_manager.py 中添加以下方法

    def click_course_in_list(self, course_name: str) -> bool:
        """
        在课程列表页点击指定课程名称的课程
        """
        try:
            # ---- 新增的核心步骤：先尝试设置每页96条 ----
            # 无论设置成功与否，都继续执行后续的查找逻辑。
            # 如果设置成功，则所有课程都在当前页，一定能找到。
            # 如果设置失败，则回退到原先的查找逻辑（可能只在第一页找，或需要翻页）。
            self._set_page_size_to_96()
            # ---- 新增步骤结束 ----

            logger.progress(f"在课程列表页查找并点击课程: {course_name}")

            # 等待课程列表加载（设置96条/页后可能会刷新）
            self.page.wait_for_selector('div.course_name', timeout=15000)
            time.sleep(Config.CLICK_WAIT)

            # 获取所有课程元素（设置后应为全部课程）
            course_elements = self.page.locator('div.course_name').all()
            logger.info(f"找到 {len(course_elements)} 个课程元素")

            # 遍历查找匹配的课程
            for i, course_elem in enumerate(course_elements):
                try:
                    # 获取课程文本
                    elem_text = course_elem.inner_text().strip()
                    logger.debug(f"检查课程 [{i + 1}]: {elem_text}")

                    # 检查是否匹配（使用部分匹配，因为课程名称可能包含额外空格或符号）
                    if course_name in elem_text or elem_text in course_name:
                        logger.info(f"找到匹配课程: {elem_text}")

                        # 滚动到视图
                        course_elem.scroll_into_view_if_needed()
                        time.sleep(Config.CLICK_WAIT)

                        # 点击课程
                        course_elem.click()
                        logger.success(f"已点击课程: {elem_text}")

                        # 等待页面跳转
                        self.page.wait_for_load_state('networkidle')
                        time.sleep(Config.PAGE_LOAD_WAIT * 2)

                        # 验证是否进入了课程详情页
                        current_url = self.page.url
                        logger.debug(f"点击后URL: {current_url}")

                        # 检查页面是否有课程详情页的特征元素
                        detail_selectors = [
                            '.course-detail',
                            '.course-header',
                            '.el-tabs',  # 课程详情页应该有标签页
                            'h1', 'h2'  # 标题元素
                        ]

                        for selector in detail_selectors:
                            try:
                                if self.page.locator(selector).count() > 0:
                                    logger.success("成功进入课程详情页")
                                    return True
                            except:
                                continue

                        logger.warning("未检测到课程详情页特有元素，但继续执行")
                        return True

                except Exception as e:
                    logger.debug(f"检查课程元素 {i + 1} 失败: {e}")
                    continue

            logger.error(f"未找到课程: {course_name}")

            # 如果没找到，尝试其他查找方式
            logger.info("尝试通过XPath查找...")
            try:
                # 使用XPath进行模糊匹配
                xpath_query = f"//*[contains(text(), '{course_name[:10]}')]"  # 只匹配前10个字符
                matching_elements = self.page.locator(f"xpath={xpath_query}").all()

                for elem in matching_elements:
                    try:
                        elem_text = elem.inner_text().strip()
                        logger.info(f"XPath找到元素: {elem_text}")

                        # 检查是否是课程名称
                        if "课程" in elem_text or len(elem_text) > 5:  # 简单判断
                            elem.click()
                            logger.success(f"已点击XPath找到的课程: {elem_text}")
                            time.sleep(Config.PAGE_LOAD_WAIT * 2)
                            return True
                    except:
                        continue
            except Exception as e:
                logger.debug(f"XPath查找失败: {e}")

            return False

        except Exception as e:
            logger.error(f"点击课程失败: {e}", exc_info=True)
            return False

    def ensure_in_course_detail_page(self, course_name: str) -> bool:
        """
        确保当前在课程详情页，如果不在则尝试进入
        """
        try:
            current_url = self.page.url
            logger.debug(f"当前URL: {current_url}")

            # 检查是否已经在课程详情页
            if "courseDetail" in current_url:
                logger.info("已经在课程详情页")
                return True

            # 检查是否在课程列表页
            if "courseManage" in current_url or "curriculum" in current_url:
                logger.info("在课程管理页面，尝试点击课程进入详情页")
                return self.click_course_in_list(course_name)

            # 如果都不在，先导航到课程管理页面
            logger.info("不在课程相关页面，先导航到课程管理页面")
            if not self.navigate_to_course_management():
                return False

            # 然后点击课程
            return self.click_course_in_list(course_name)

        except Exception as e:
            logger.error(f"确保在课程详情页失败: {e}")
            return False

    def _set_page_size_to_96(self) -> bool:
        """
        在课程管理页面，将每页显示条数设置为最大值（96条/页）。
        成功后，所有课程将显示在同一页，无需翻页。
        """
        try:
            logger.progress("正在尝试设置每页显示96条课程...")

            # 1. 定位整个分页组件（根据你提供的HTML，它的class是'el-pagination'）
            pagination_div = self.page.locator('div.el-pagination')
            if pagination_div.count() == 0:
                logger.warning("未找到分页组件，可能页面布局不同或课程数量很少。")
                return False

            # 2. 在分页组件内，定位到“每页条数”选择器的输入框并点击
            # 你提供的HTML路径是：div.el-pagination -> span.el-pagination__sizes -> div.el-select -> div.el-input -> input
            page_size_input = pagination_div.locator('input.el-input__inner[placeholder="请选择"]')
            if page_size_input.count() == 0:
                logger.warning("未找到‘每页条数’选择输入框。")
                return False

            page_size_input.click()
            logger.debug("已点击分页条数选择框，等待下拉列表弹出...")
            time.sleep(1)  # 等待下拉动画

            # 3. 在全局范围内选择下拉列表中包含“96条/页”文本的选项
            # 注意：弹出的下拉列表可能在body末尾，不一定在分页组件内部
            option_96 = self.page.locator('li.el-select-dropdown__item:has-text("96条/页")')
            if option_96.count() == 0:
                logger.warning("在下拉列表中未找到‘96条/页’的选项。")
                # 尝试截图当前页面状态，便于调试
                self.page.screenshot(path="debug_dropdown_failed.png")
                return False

            option_96.click()
            logger.success("✅ 已成功选择‘96条/页’。")

            # 4. 重要：等待页面数据刷新
            # 选择后，页面会重新请求数据并刷新列表
            logger.info("等待课程列表刷新...")
            self.page.wait_for_load_state('networkidle')
            time.sleep(2)  # 额外等待确保DOM渲染完成

            # 5. （可选）验证：检查分页器是否消失或页码只剩下1
            # 如果成功，通常页码列表会消失或只有一页，并且“共 X 条”的X应该是总课程数
            total_text = pagination_div.locator('span.el-pagination__total')
            if total_text.count() > 0:
                logger.debug(f"分页信息: {total_text.inner_text()}")

            return True

        except Exception as e:
            logger.error(f"设置每页显示条数时发生意外错误: {e}", exc_info=True)
            return False

    def _navigate_to_course_detail_by_click(self, course_code: str) -> bool:
        """通过点击课程进入详情页"""
        try:
            # 首先确保在课程管理页面
            self.navigate_to(Config.COURSE_MANAGE_URL)
            time.sleep(Config.PAGE_LOAD_WAIT)

            # 等待课程列表加载
            self.page.wait_for_selector('div.course_name', timeout=15000)

            # 查找并点击对应课程
            # 注意：这需要知道如何在页面中找到特定课程
            # 这里我们假设可以通过课程名称的模糊匹配来点击

            # 先获取所有课程元素
            course_elements = self.page.locator('div.course_name').all()

            for course_element in course_elements:
                try:
                    course_text = course_element.inner_text().strip()
                    logger.debug(f"检查课程: {course_text}")

                    # 这里需要你根据实际情况调整匹配逻辑
                    # 比如，如果你有课程名称，可以匹配课程名称
                    # 或者通过其他方式识别目标课程

                    # 暂时假设我们点击第一个课程
                    # 在实际应用中，你需要根据选择的课程来点击对应的元素
                    course_element.click()
                    logger.info(f"已点击课程: {course_text}")

                    # 等待页面跳转
                    self.page.wait_for_load_state('networkidle')
                    time.sleep(Config.PAGE_LOAD_WAIT * 2)

                    return True

                except Exception as e:
                    logger.debug(f"点击课程失败: {e}")
                    continue

            logger.error("未找到可点击的课程元素")
            return False

        except Exception as e:
            logger.error(f"通过点击进入课程详情页失败: {e}")
            return False