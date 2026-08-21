"""点击器核心 - 支持多种代理源
- ProxyHub API(默认)
- 付费代理 API(快代理/芝麻代理...)
- SOCKS5 代理列表
- HTTP 代理列表
- 不使用代理
"""
import asyncio
import random
import time
import sys
import os
import tempfile
from pathlib import Path
import requests
from playwright.async_api import async_playwright


# 找内置 Chromium
def find_chromium():
    candidates = [
        Path(sys.executable).parent / "chromium-1223" / "chrome-win64" / "chrome.exe",
        Path(__file__).parent.parent / "chromium-1223" / "chrome-win64" / "chrome.exe",
        Path(r"C:\Users\Administrator\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


# 各种设备指纹
DEVICE_PROFILES = [
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     "viewport": {"width": 1920, "height": 1080}, "platform": "Win32"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
     "viewport": {"width": 1536, "height": 864}, "platform": "Win32"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
     "viewport": {"width": 1440, "height": 900}, "platform": "MacIntel"},
    {"ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
     "viewport": {"width": 1366, "height": 768}, "platform": "Linux x86_64"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
     "viewport": {"width": 1280, "height": 720}, "platform": "Win32"},
]


class ProxySource:
    """代理源基类"""
    name = "基类"

    def get_proxy(self):
        """返回 (proxy_str, scheme)
        proxy_str: "1.2.3.4:8080" 或 None
        scheme: "http"/"socks5"
        """
        return None, "http"

    def report_fail(self, proxy_str):
        """报告一个代理失败(可选)"""
        pass


class ProxyHubAPI(ProxySource):
    """从 ProxyHub API 拿代理"""

    def __init__(self, url="http://localhost:5010"):
        self.url = url.rstrip("/")
        self.name = f"ProxyHub ({self.url})"

    def get_proxy(self):
        try:
            r = requests.get(f"{self.url}/get/?type=http", timeout=5)
            data = r.json()
            if "proxy" in data and data["proxy"]:
                return data["proxy"], "http"
        except Exception as e:
            return None, "http"
        return None, "http"

    def report_fail(self, proxy_str):
        try:
            requests.get(f"{self.url}/delete/?proxy={proxy_str}", timeout=3)
        except:
            pass


class CustomAPI(ProxySource):
    """通用付费代理 API(快代理/芝麻代理/...)
    用户填一个 URL 模板,如 http://api.ip3366.net/api/?key=xxx
    返回可能是 JSON {"proxy": [...]} 或纯文本 "ip:port\\nip:port"
    """

    def __init__(self, url_template):
        self.url = url_template
        self.name = f"自定义 API"

    def get_proxy(self):
        try:
            r = requests.get(self.url, timeout=10)
            content = r.text.strip()
            # 尝试解析 JSON
            try:
                data = r.json()
                if isinstance(data, dict):
                    # 多种可能字段名
                    for key in ["proxy", "data", "ip", "result"]:
                        if key in data:
                            val = data[key]
                            if isinstance(val, list) and val:
                                item = val[0]
                                if isinstance(item, dict):
                                    ip = item.get("ip") or item.get("proxy", "")
                                    port = item.get("port") or ""
                                    if ip and port:
                                        return f"{ip}:{port}", "http"
                                elif isinstance(item, str):
                                    return item, "http"
                    # 如果没匹配,转字符串查找
                elif isinstance(data, list) and data:
                    item = data[0]
                    if isinstance(item, dict):
                        return f"{item.get('ip')}:{item.get('port')}", "http"
                    elif isinstance(item, str):
                        return item, "http"
            except:
                pass
            # 不是 JSON,当纯文本处理
            lines = [l.strip() for l in content.split("\n") if l.strip() and ":" in l]
            if lines:
                # 看第一行是 socks5:// 还是 socks5: 还是 ip:port
                first = lines[0]
                if first.startswith("socks5://"):
                    return first.replace("socks5://", ""), "socks5"
                return first, "http"
        except Exception as e:
            return None, "http"
        return None, "http"


class ProxyList(ProxySource):
    """从列表随机选代理
    用户粘贴 ip:port 一行一个
    """

    def __init__(self, text, scheme="http"):
        # 解析列表
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # 去掉 socks5:// 前缀(如果有)
        cleaned = []
        for l in lines:
            if "://" in l:
                if l.startswith("socks5://"):
                    cleaned.append((l.replace("socks5://", ""), "socks5"))
                elif l.startswith("http://"):
                    cleaned.append((l.replace("http://", ""), "http"))
                else:
                    cleaned.append((l.split("://", 1)[1], "http"))
            elif ":" in l:
                cleaned.append((l, scheme))
        self.proxies = cleaned
        self.name = f"自定义列表 ({len(cleaned)} 个)"
        self._used = set()

    def get_proxy(self):
        available = [p for p in self.proxies if p[0] not in self._used]
        if not available:
            # 用完了,重置
            self._used.clear()
            available = self.proxies
        if available:
            proxy_str, scheme = random.choice(available)
            self._used.add(proxy_str)
            return proxy_str, scheme
        return None, "http"

    def report_fail(self, proxy_str):
        """失败后从列表移除"""
        self.proxies = [(p, s) for p, s in self.proxies if p != proxy_str]


class NoProxy(ProxySource):
    """不使用代理(直连)"""

    def __init__(self):
        self.name = "不使用代理(直连)"

    def get_proxy(self):
        return None, "http"


class Clicker:
    """百度关键词点击器"""

    def __init__(self, proxy_source=None, log_callback=None, target_domain=None):
        self.log = log_callback or print
        self.proxy_source = proxy_source or NoProxy()
        self.chromium = find_chromium()
        self.target_domain = target_domain
        self._stop_flag = False
        self.stats = {
            "total": 0,
            "success": 0,
            "fail": 0,
            "current_ip": "",
            "current_keyword": "",
            "proxy_source": self.proxy_source.name,
        }

    def set_proxy_source(self, source):
        self.proxy_source = source
        self.stats["proxy_source"] = source.name

    def _log_msg(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log(f"[{ts}] {msg}")

    def stop(self):
        self._stop_flag = True
        self._log_msg("⏹ 收到停止信号")

    def run_keyword(self, keyword):
        """单次关键词点击"""
        if self._stop_flag:
            return False

        if not self.chromium:
            self._log_msg("❌ 没找到 Chromium,请确保 chromium-1223 在 EXE 同目录")
            return False

        self.stats["total"] += 1
        self.stats["current_keyword"] = keyword

        proxy, scheme = self.proxy_source.get_proxy()
        proxy_display = proxy or "(直连)"
        self.stats["current_ip"] = proxy_display
        self._log_msg(f"🔍 关键词: {keyword}  ·  代理: {proxy_display} ({scheme})")

        device = random.choice(DEVICE_PROFILES)

        try:
            asyncio.run(self._search(keyword, proxy, scheme, device, self.target_domain))
            self.stats["success"] += 1
            self._log_msg(f"✅ 完成「{keyword}」")
            return True
        except Exception as e:
            self.stats["fail"] += 1
            self._log_msg(f"❌ 失败「{keyword}」: {e}")
            if proxy and self.proxy_source:
                self.proxy_source.report_fail(proxy)
            return False

    async def _random_hover(self, page):
        """随机鼠标抖动/悬停"""
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, page.viewport_size['width'] - 100)
            y = random.randint(100, page.viewport_size['height'] - 100)
            await page.mouse.move(x, y, steps=random.randint(3, 10))
            await asyncio.sleep(random.uniform(0.1, 0.5))

    async def _human_type(self, page, text):
        """真人打字(每个字符有随机延迟)"""
        for char in text:
            await page.keyboard.type(char, delay=random.randint(50, 180))
            # 偶尔打错回退
            if random.random() < 0.05 and len(text) > 3:
                await page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await page.keyboard.type(char)

    async def _get_baidu_hot_words(self, page):
        """获取百度热搜词(模拟真人选热词)"""
        try:
            hot_words = []
            items = await page.query_selector_all('#hotsearch-content-wrapper li a, .hotsearch-item a')
            for item in items[:10]:
                txt = await item.text_content()
                if txt and txt.strip():
                    hot_words.append(txt.strip())
            return hot_words
        except:
            return []

    async def _use_search_suggestion(self, page, keyword):
        """使用百度搜索下拉联想词(模拟真实用户)"""
        try:
            # 在搜索框输入关键词,触发联想
            search_input = await page.query_selector('#kw, input[name="wd"]')
            if not search_input:
                return None

            await search_input.click()
            await asyncio.sleep(random.uniform(0.2, 0.5))

            # 清空
            await page.keyboard.press('Control+A')
            await page.keyboard.press('Delete')

            # 真人方式输入(每个字符有延迟)
            for char in keyword:
                await page.keyboard.type(char, delay=random.randint(80, 200))

            # 等待下拉框出现
            await asyncio.sleep(random.uniform(0.5, 1.2))

            # 找下拉联想词
            suggestions = await page.query_selector_all('.bdsug-overflow li, .bdsug-menu li')
            if suggestions:
                # 70% 概率选一个下拉词,30% 直接按回车
                if random.random() < 0.7:
                    chosen = random.choice(suggestions[:5])
                    txt = await chosen.text_content()
                    if txt:
                        self._log_msg(f"  💡 选下拉词: {txt.strip()[:30]}")
                        await chosen.click()
                        await asyncio.sleep(random.uniform(0.3, 0.8))
                        return txt.strip()

            # 按回车搜索
            await page.keyboard.press('Enter')
            return None
        except Exception as e:
            return None

    async def _human_mouse_move(self, page, target_x, target_y, steps=None):
        """模拟真人鼠标移动轨迹(贝塞尔曲线)"""
        if steps is None:
            steps = random.randint(15, 30)
        # 当前鼠标位置(默认 0,0)
        current_x = random.randint(0, 100)
        current_y = random.randint(0, 100)

        # 控制点(贝塞尔曲线弯曲)
        cp1_x = (current_x + target_x) / 2 + random.randint(-100, 100)
        cp1_y = (current_y + target_y) / 2 + random.randint(-100, 100)
        cp2_x = (current_x + target_x) / 2 + random.randint(-100, 100)
        cp2_y = (current_y + target_y) / 2 + random.randint(-100, 100)

        for i in range(steps + 1):
            t = i / steps
            # 三次贝塞尔
            x = ((1-t)**3 * current_x +
                 3*(1-t)**2*t * cp1_x +
                 3*(1-t)*t**2 * cp2_x +
                 t**3 * target_x)
            y = ((1-t)**3 * current_y +
                 3*(1-t)**2*t * cp1_y +
                 3*(1-t)*t**2 * cp2_y +
                 t**3 * target_y)
            await page.mouse.move(int(x), int(y))
            await asyncio.sleep(random.uniform(0.005, 0.02))

    async def _human_scroll(self, page, total_distance=None):
        """模拟真人滚动(分多次,每次不等距)"""
        if total_distance is None:
            total_distance = random.randint(500, 1500)
        scrolled = 0
        while scrolled < total_distance:
            # 每次滚动距离不等
            chunk = random.randint(80, 250)
            chunk = min(chunk, total_distance - scrolled)
            await page.mouse.wheel(0, chunk)
            scrolled += chunk
            # 滚动后停顿随机时长
            await asyncio.sleep(random.uniform(0.2, 0.8))

    async def _find_target_site(self, page, target_domain, max_pages=5):
        """在百度搜索结果中找目标站点,支持翻页"""
        for page_num in range(1, max_pages + 1):
            try:
                # 找所有搜索结果链接
                links = await page.query_selector_all('#content_left h3 a')
                if not links:
                    links = await page.query_selector_all('h3 a')

                for i, link in enumerate(links):
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                    try:
                        # 百度搜索结果是跳转链接,需要解析真实 URL
                        real_url = await page.evaluate("""
                            async (url) => {
                                try {
                                    const resp = await fetch(url, {redirect: 'follow'});
                                    return resp.url;
                                } catch (e) {
                                    return url;
                                }
                            }
                        """, href)
                    except:
                        real_url = href

                    if target_domain in real_url:
                        return link, real_url, page_num

                # 没找到,翻页
                if page_num < max_pages:
                    self._log_msg(f"  📄 第 {page_num} 页没找到,翻第 {page_num+1} 页...")
                    try:
                        next_btn = await page.query_selector('a.n')  # 百度"下一页"
                        if next_btn:
                            await next_btn.click()
                            await asyncio.sleep(random.uniform(1.5, 3.0))
                            await page.wait_for_selector('#content_left', timeout=10000)
                        else:
                            break
                    except:
                        break
                else:
                    break
            except Exception as e:
                self._log_msg(f"  ⚠️ 翻页错误: {e}")
                break

        return None, None, 0

    async def _search(self, keyword, proxy, scheme, device, target_domain=None):
        async with async_playwright() as p:
            browser_kwargs = {
                "headless": True,
                "executable_path": self.chromium,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            }
            browser = await p.chromium.launch(**browser_kwargs)

            context_kwargs = {
                "user_agent": device["ua"],
                "viewport": device["viewport"],
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai",
                "ignore_https_errors": True,
            }
            if proxy:
                context_kwargs["proxy"] = {"server": f"{scheme}://{proxy}"}

            context = await browser.new_context(**context_kwargs)
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            """)

            page = await context.new_page()

            try:
                # Step 1: 先访问百度首页(更像真人,先到首页)
                self._log_msg(f"  📍 访问百度首页")
                await page.goto("https://www.baidu.com", wait_until="load", timeout=30000)

                # 随机悬停
                await self._random_hover(page)

                # Step 2: 通过搜索框输入(比直接 s?wd 更真实)
                suggestion_used = await self._use_search_suggestion(page, keyword)
                if suggestion_used:
                    self._log_msg(f"  📝 实际搜索词: {suggestion_used}")

                # 等搜索结果加载
                try:
                    await page.wait_for_selector("#content_left", timeout=10000)
                except:
                    self._log_msg("  ⚠️ 搜索结果未出现(可能被反爬)")

                # Step 3: 模拟真人滚动(页面下拉)
                await self._human_scroll(page)

                # Step 3.5: 再次随机鼠标悬停
                await self._random_hover(page)

                # Step 2: 如果指定了目标站点,尝试找目标站并深度访问
                if target_domain:
                    self._log_msg(f"  🎯 找目标站点: {target_domain}")

                    target_link, real_url, found_page = await self._find_target_site(
                        page, target_domain, max_pages=5
                    )

                    if target_link:
                        self._log_msg(f"  ✅ 找到目标站点(第 {found_page} 页): {real_url[:60]}...")

                        # 模拟真人鼠标移动到目标链接
                        box = await target_link.bounding_box()
                        if box:
                            target_x = int(box['x'] + box['width'] / 2 + random.randint(-10, 10))
                            target_y = int(box['y'] + box['height'] / 2 + random.randint(-5, 5))
                            await self._human_mouse_move(page, target_x, target_y)
                            await asyncio.sleep(random.uniform(0.1, 0.4))

                        # 点击目标链接
                        await target_link.click()

                        # 等待页面加载
                        try:
                            await page.wait_for_load_state('load', timeout=15000)
                        except:
                            pass

                        # 在目标站模拟真人浏览
                        stay_time = random.randint(10, 30)
                        self._log_msg(f"  ⏱ 在目标站停留 {stay_time} 秒...")

                        # 多次滚动(模拟阅读)
                        for _ in range(random.randint(3, 6)):
                            await self._human_scroll(page)

                        # 30% 概率点击站内内链
                        if random.random() < 0.3:
                            try:
                                inner_links = await page.query_selector_all('a[href*="http"]')
                                # 过滤站内链接
                                same_domain_links = []
                                for ln in inner_links:
                                    href = await ln.get_attribute('href')
                                    if href and target_domain in href:
                                        same_domain_links.append(ln)
                                if same_domain_links:
                                    chosen = random.choice(same_domain_links[:5])
                                    box = await chosen.bounding_box()
                                    if box:
                                        await self._human_mouse_move(
                                            page,
                                            int(box['x'] + box['width']/2),
                                            int(box['y'] + box['height']/2)
                                        )
                                        self._log_msg(f"  🔗 点击站内链接")
                                        await chosen.click()
                                        try:
                                            await page.wait_for_load_state('load', timeout=10000)
                                        except:
                                            pass
                                        await asyncio.sleep(random.uniform(5, 15))
                            except:
                                pass

                        await asyncio.sleep(stay_time)
                    else:
                        self._log_msg(f"  ⚠️ 翻 5 页都没找到 {target_domain},只做普通浏览")
                        # 降级: 随机点一个非目标站
                        all_links = await page.query_selector_all('#content_left h3 a')
                        if all_links and random.random() < 0.4:
                            random_link = random.choice(all_links[:5])
                            box = await random_link.bounding_box()
                            if box:
                                await self._human_mouse_move(
                                    page,
                                    int(box['x'] + box['width']/2),
                                    int(box['y'] + box['height']/2)
                                )
                                await asyncio.sleep(random.uniform(0.1, 0.3))
                                await random_link.click()
                                self._log_msg(f"  🎲 随机点了非目标站(模拟真人)")
                                await asyncio.sleep(random.uniform(3, 8))
                                # 看一眼就退出
                                await page.go_back()
                        await asyncio.sleep(random.randint(3, 10))
                else:
                    # 无目标站: 简单浏览
                    stay_time = random.randint(3, 10)
                    self._log_msg(f"  ⏱ 停留 {stay_time} 秒")
                    await asyncio.sleep(stay_time)

            finally:
                await browser.close()

    def run_batch(self, keywords, delay_min=5, delay_max=30):
        self._stop_flag = False
        self.stats = {
            "total": 0, "success": 0, "fail": 0,
            "current_ip": "", "current_keyword": "",
            "proxy_source": self.proxy_source.name,
        }

        for kw in keywords:
            if self._stop_flag:
                break
            kw = kw.strip()
            if not kw:
                continue
            self.run_keyword(kw)
            if not self._stop_flag:
                wait = random.randint(delay_min, delay_max)
                self._log_msg(f"⏳ 等待 {wait} 秒...")
                time.sleep(wait)

        self._log_msg(f"📊 完成: 成功 {self.stats['success']} / 失败 {self.stats['fail']}")