"""百度关键词点击器 UI - 支持多种代理源"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clicker.clicker import (
    Clicker, ProxyHubAPI, CustomAPI, ProxyList, NoProxy
)
from clicker import theme


def bind_paste(entry):
    entry.bind('<Control-v>', lambda e: _paste_clipboard(entry))
    entry.bind('<Control-V>', lambda e: _paste_clipboard(entry))


def _paste_clipboard(entry):
    try:
        content = entry.clipboard_get()
        if content:
            entry.delete(0, 'end')
            entry.insert(0, content)
    except:
        pass
    return 'break'


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"🎯 百度关键词点击器 v1.2 - {theme.BRAND_NAME}")
        self.root.geometry("1000x720")
        self.root.configure(bg=theme.COLOR_BG)

        self.clicker = Clicker(proxy_source=ProxyHubAPI(), log_callback=self._log, target_domain="")
        self._worker = None
        self._build_ui()
        self._load_default_keywords()

    def _build_ui(self):
        # 顶部
        tk.Label(
            self.root, text="🎯 百度关键词点击器",
            font=("Microsoft YaHei", 18, "bold"),
            fg=theme.COLOR_PRIMARY_DARK, bg=theme.COLOR_BG
        ).pack(pady=(15, 2))

        tk.Label(
            self.root,
            text=f"支持 ProxyHub API / 付费代理 / SOCKS5 / HTTP 列表 / 直连 · {theme.BRAND_NAME}",
            font=("Microsoft YaHei", 10),
            fg=theme.COLOR_TEXT_LIGHT, bg=theme.COLOR_BG
        ).pack(pady=(0, 10))

        # ============== 代理源配置 ==============
        proxy_frame = tk.LabelFrame(
            self.root, text="  🔌 代理源(支持多种)  ", font=("Microsoft YaHei", 10, "bold"),
            fg=theme.COLOR_PRIMARY_DARK, bg=theme.COLOR_CARD, bd=1, relief="groove", padx=10, pady=8
        )
        proxy_frame.pack(fill="x", padx=12, pady=5)

        # 代理源类型
        tk.Label(proxy_frame, text="代理源类型:", bg=theme.COLOR_CARD, font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=5, sticky="w")
        self.proxy_type = tk.StringVar(value="ProxyHub API(免费)")
        proxy_options = [
            "ProxyHub API(免费)",
            "付费代理 API(自定义 URL)",
            "自定义 HTTP/SOCKS5 列表",
            "不使用代理(直连)",
        ]
        self.proxy_combo = ttk.Combobox(
            proxy_frame, textvariable=self.proxy_type,
            values=proxy_options, state="readonly", width=30
        )
        self.proxy_combo.grid(row=0, column=1, padx=5, sticky="w")
        self.proxy_combo.bind("<<ComboboxSelected>>", self._on_proxy_type_change)

        # 配置项容器
        self.proxy_config_frame = tk.Frame(proxy_frame, bg=theme.COLOR_CARD)
        self.proxy_config_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=8)
        proxy_frame.grid_columnconfigure(1, weight=1)

        # 按钮
        tk.Button(
            proxy_frame, text="✅ 应用代理源", bg=theme.COLOR_PRIMARY, fg="white",
            font=("Microsoft YaHei", 10, "bold"), padx=12, pady=4,
            command=self._apply_proxy_source
        ).grid(row=0, column=2, padx=10)

        self._build_proxy_configs()

        # ============== 目标站点配置(可选,用于真实点击)==============
        target_frame = tk.LabelFrame(
            self.root, text="  🎯 目标站点(可选,留空只搜不点)  ",
            font=("Microsoft YaHei", 10, "bold"),
            fg=theme.COLOR_PRIMARY_DARK, bg=theme.COLOR_CARD, bd=1, relief="groove", padx=10, pady=8
        )
        target_frame.pack(fill="x", padx=12, pady=5)

        tk.Label(
            target_frame, text="目标域名:",
            bg=theme.COLOR_CARD, font=("Microsoft YaHei", 10)
        ).grid(row=0, column=0, padx=5, sticky="w")

        self.target_domain = tk.StringVar(value="")
        target_entry = tk.Entry(
            target_frame, textvariable=self.target_domain,
            font=("Microsoft YaHei", 10), width=35
        )
        target_entry.grid(row=0, column=1, padx=5, sticky="ew")
        target_frame.grid_columnconfigure(1, weight=1)

        tk.Label(
            target_frame, text="(例: example.com - 留空则模拟真人浏览但找不到目标站)",
            bg=theme.COLOR_CARD, fg="#888",
            font=("Microsoft YaHei", 9)
        ).grid(row=0, column=2, padx=5, sticky="w")

        # ============== 主区域 ==============
        main = tk.Frame(self.root, bg=theme.COLOR_BG)
        main.pack(fill="both", expand=True, padx=12, pady=5)

        # 左侧:关键词
        left = tk.LabelFrame(
            main, text="  📝 关键词列表  ", font=("Microsoft YaHei", 10, "bold"),
            fg=theme.COLOR_PRIMARY_DARK, bg=theme.COLOR_CARD, bd=1, relief="groove", padx=8, pady=8
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))

        toolbar = tk.Frame(left, bg=theme.COLOR_CARD)
        toolbar.pack(fill="x", pady=(0, 5))
        for text, cmd in [
            ("➕ 添加", self._add_keyword),
            ("🗑️ 删除", self._del_keyword),
            ("📋 全部清空", self._clear_keywords),
            ("📁 从文件", self._load_from_file),
        ]:
            tk.Button(toolbar, text=text, font=("Microsoft YaHei", 10),
                      bg=theme.COLOR_BG, padx=8, pady=3, command=cmd).pack(side="left", padx=2)

        self.kw_list = tk.Listbox(left, font=("Microsoft YaHei", 11), height=15)
        scroll = tk.Scrollbar(left, command=self.kw_list.yview)
        self.kw_list.configure(yscrollcommand=scroll.set)
        self.kw_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        bind_paste(self.kw_list)

        # 右侧:日志
        right = tk.LabelFrame(
            main, text="  📊 实时日志  ", font=("Microsoft YaHei", 10, "bold"),
            fg=theme.COLOR_PRIMARY_DARK, bg=theme.COLOR_CARD, bd=1, relief="groove", padx=8, pady=8
        )
        right.pack(side="right", fill="both", expand=True, padx=(5, 0))

        stat_frame = tk.Frame(right, bg=theme.COLOR_CARD)
        stat_frame.pack(fill="x", pady=(0, 5))

        self.stat_labels = {}
        for i, (key, label) in enumerate([
            ("total", "总数"),
            ("success", "成功"),
            ("fail", "失败"),
        ]):
            card = tk.Frame(stat_frame, bg=theme.COLOR_BG, relief="groove", borderwidth=1)
            card.grid(row=0, column=i, padx=2, sticky="ew")
            stat_frame.grid_columnconfigure(i, weight=1)
            val = tk.Label(card, text="—", font=("Microsoft YaHei", 16, "bold"),
                          fg=theme.COLOR_PRIMARY_DARK, bg=theme.COLOR_BG)
            val.pack(pady=(6, 0))
            tk.Label(card, text=label, font=("Microsoft YaHei", 9),
                    fg=theme.COLOR_TEXT_LIGHT, bg=theme.COLOR_BG).pack(pady=(0, 6))
            self.stat_labels[key] = val

        # 当前关键词
        self.current_label = tk.Label(right, text="当前: —", font=("Microsoft YaHei", 10),
                                       fg=theme.COLOR_PRIMARY_DARK, bg=theme.COLOR_CARD, anchor="w")
        self.current_label.pack(fill="x")

        self.log_text = tk.Text(right, height=18, font=("Consolas", 10),
                                 bg="#0f172a", fg="#10b981",
                                 insertbackground="#10b981", relief="flat")
        log_scroll = tk.Scrollbar(right, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")
        bind_paste(self.log_text)

        # 间隔配置
        config = tk.Frame(self.root, bg=theme.COLOR_BG)
        config.pack(fill="x", padx=12, pady=5)
        tk.Label(config, text="间隔(秒):", bg=theme.COLOR_BG, font=("Microsoft YaHei", 10)).pack(side="left", padx=5)
        self.delay_min = tk.StringVar(value="5")
        self.delay_max = tk.StringVar(value="30")
        tk.Entry(config, textvariable=self.delay_min, width=5).pack(side="left", padx=2)
        tk.Label(config, text="-", bg=theme.COLOR_BG, font=("Microsoft YaHei", 10)).pack(side="left")
        tk.Entry(config, textvariable=self.delay_max, width=5).pack(side="left", padx=2)

        # 按钮
        bottom = tk.Frame(self.root, bg=theme.COLOR_BG)
        bottom.pack(fill="x", padx=12, pady=10)

        self.start_btn = tk.Button(
            bottom, text="▶ 开始点击", font=("Microsoft YaHei", 12, "bold"),
            bg=theme.COLOR_SUCCESS, fg="white", padx=25, pady=8,
            command=self._start
        )
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = tk.Button(
            bottom, text="⏹ 停止", font=("Microsoft YaHei", 12, "bold"),
            bg=theme.COLOR_DANGER, fg="white", padx=25, pady=8,
            command=self._stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)

        tk.Button(
            bottom, text="🧪 测试代理源", font=("Microsoft YaHei", 11),
            bg=theme.COLOR_PRIMARY, fg="white", padx=15, pady=8,
            command=self._test_proxy
        ).pack(side="left", padx=5)

        self.status = tk.Label(
            self.root, text=f"就绪 ·  © {theme.BRAND_NAME}",
            font=("Microsoft YaHei", 9), fg=theme.COLOR_TEXT_LIGHT, bg=theme.COLOR_CARD,
            anchor="w", padx=12, pady=4
        )
        self.status.pack(side="bottom", fill="x")

    def _build_proxy_configs(self):
        """根据当前代理源类型,显示对应配置项"""
        for w in self.proxy_config_frame.winfo_children():
            w.destroy()

        ptype = self.proxy_type.get()

        if ptype == "ProxyHub API(免费)":
            tk.Label(self.proxy_config_frame, text="API 地址:",
                     bg=theme.COLOR_CARD, font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w", padx=5)
            self.proxyhub_url = tk.StringVar(value="http://localhost:5010")
            e = tk.Entry(self.proxy_config_frame, textvariable=self.proxyhub_url,
                        width=50, font=("Consolas", 10))
            e.grid(row=0, column=1, sticky="ew", padx=5)
            bind_paste(e)
            tk.Label(self.proxy_config_frame,
                    text="💡 需要 ProxyHub.exe 在跑",
                    bg=theme.COLOR_CARD, font=("Microsoft YaHei", 9),
                    fg=theme.COLOR_TEXT_LIGHT).grid(row=1, column=1, sticky="w", padx=5)

        elif ptype == "付费代理 API(自定义 URL)":
            tk.Label(self.proxy_config_frame, text="API URL:",
                     bg=theme.COLOR_CARD, font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="nw", padx=5, pady=5)
            self.custom_api_url = tk.StringVar(value="http://api.ip3366.net/api/?key=YOUR_KEY")
            e = tk.Entry(self.proxy_config_frame, textvariable=self.custom_api_url,
                        width=50, font=("Consolas", 10))
            e.grid(row=0, column=1, sticky="ew", padx=5)
            bind_paste(e)
            tk.Label(self.proxy_config_frame,
                    text="💡 支持 JSON 或纯文本格式",
                    bg=theme.COLOR_CARD, font=("Microsoft YaHei", 9),
                    fg=theme.COLOR_TEXT_LIGHT).grid(row=1, column=1, sticky="w", padx=5)

        elif ptype == "自定义 HTTP/SOCKS5 列表":
            tk.Label(self.proxy_config_frame, text="代理列表(一行一个):",
                     bg=theme.COLOR_CARD, font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="nw", padx=5, pady=5)
            self.proxy_list_text = tk.Text(self.proxy_config_frame, height=6, font=("Consolas", 10),
                                            bg="#0f172a", fg="#10b981")
            self.proxy_list_text.grid(row=0, column=1, sticky="ew", padx=5)
            # 默认示例
            self.proxy_list_text.insert("1.0", "192.168.1.1:8080\nsocks5://10.0.0.1:1080\nhttp://proxy.example.com:3128")
            bind_paste(self.proxy_list_text)
            tk.Label(self.proxy_config_frame,
                    text="💡 格式:ip:port  或  socks5://ip:port  或  http://ip:port",
                    bg=theme.COLOR_CARD, font=("Microsoft YaHei", 9),
                    fg=theme.COLOR_TEXT_LIGHT).grid(row=1, column=1, sticky="w", padx=5)

        else:  # 不使用代理
            tk.Label(self.proxy_config_frame,
                    text="💡 直接连百度,不通过代理(可能被识别/限速)",
                    bg=theme.COLOR_CARD, font=("Microsoft YaHei", 10),
                    fg=theme.COLOR_WARNING).grid(row=0, column=0, columnspan=2, padx=5, pady=10)

        self.proxy_config_frame.grid_columnconfigure(1, weight=1)

    def _on_proxy_type_change(self, event=None):
        self._build_proxy_configs()

    def _apply_proxy_source(self):
        """根据 UI 设置创建 ProxySource"""
        ptype = self.proxy_type.get()
        if ptype == "ProxyHub API(免费)":
            url = self.proxyhub_url.get().strip() or "http://localhost:5010"
            source = ProxyHubAPI(url)
        elif ptype == "付费代理 API(自定义 URL)":
            url = self.custom_api_url.get().strip()
            if not url or "YOUR_KEY" in url:
                messagebox.showerror("错误", "请填入付费代理 API URL(替换 YOUR_KEY)")
                return
            source = CustomAPI(url)
        elif ptype == "自定义 HTTP/SOCKS5 列表":
            text = self.proxy_list_text.get("1.0", "end").strip()
            if not text:
                messagebox.showerror("错误", "请粘贴代理列表")
                return
            source = ProxyList(text)
        else:
            source = NoProxy()

        self.clicker.set_proxy_source(source)
        messagebox.showinfo("已应用", f"代理源已切换:\n{source.name}")

    def _load_default_keywords(self):
        for kw in ["Python 教程", "机器学习入门", "深度学习"]:
            self.kw_list.insert("end", kw)

    def _add_keyword(self):
        dlg = KeywordDialog(self.root)
        self.root.wait_window(dlg.top)
        if dlg.result:
            self.kw_list.insert("end", dlg.result)

    def _del_keyword(self):
        sel = self.kw_list.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先选择要删除的关键词")
            return
        for i in reversed(sel):
            self.kw_list.delete(i)

    def _clear_keywords(self):
        if messagebox.askyesno("确认", "清空所有关键词?"):
            self.kw_list.delete(0, "end")

    def _load_from_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
            title="从文件加载关键词(每行一个)"
        )
        if not path:
            return
        with open(path) as f:
            for line in f:
                kw = line.strip()
                if kw:
                    self.kw_list.insert("end", kw)
        messagebox.showinfo("完成", f"已加载 {self.kw_list.size()} 个关键词")

    def _log(self, msg):
        def _do():
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            s = self.clicker.stats
            self.stat_labels["total"].config(text=str(s["total"]))
            self.stat_labels["success"].config(text=str(s["success"]))
            self.stat_labels["fail"].config(text=str(s["fail"]))
            cur = s.get("current_keyword", "")[:20] if s.get("current_keyword") else "—"
            self.current_label.config(text=f"当前: {cur}  ·  IP: {s.get('current_ip','—')[:25]}")
        try:
            self.root.after(0, _do)
        except:
            print(msg)

    def _start(self):
        keywords = list(self.kw_list.get(0, "end"))
        if not keywords:
            messagebox.showinfo("提示", "请添加至少一个关键词")
            return

        # 应用当前代理源配置
        try:
            self._apply_proxy_source()
        except:
            return

        try:
            d_min = int(self.delay_min.get())
            d_max = int(self.delay_max.get())
        except:
            d_min, d_max = 5, 30

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status.config(text=f"▶ 运行中... 关键词 {len(keywords)} 个 · 代理:{self.clicker.proxy_source.name}")

        def run():
            try:
                # 同步 UI 上的目标站点配置到 clicker
                self.clicker.target_domain = self.target_domain.get().strip()
                if self.clicker.target_domain:
                    self._log(f"🎯 目标站点: {self.clicker.target_domain}(开启深度点击模式)")
                else:
                    self._log("🎯 未设目标站点(只搜不点)")
                self.clicker.run_batch(keywords, d_min, d_max)
            except Exception as e:
                self._log(f"❌ 异常: {e}")
            finally:
                self.root.after(0, self._on_complete)

        self._worker = threading.Thread(target=run, daemon=True)
        self._worker.start()

    def _stop(self):
        self.clicker.stop()
        self._on_complete()

    def _on_complete(self):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status.config(text=f"⏹ 已停止 · © {theme.BRAND_NAME}")

    def _test_proxy(self):
        """测试当前代理源"""
        try:
            self._apply_proxy_source()
        except:
            return
        source = self.clicker.proxy_source
        proxy, scheme = source.get_proxy()
        if proxy:
            messagebox.showinfo("成功", f"✅ 代理可用:\n{proxy}\n协议: {scheme}\n来源: {source.name}")
        else:
            messagebox.showerror("失败", f"❌ 没拿到代理\n来源: {source.name}\n\n请检查配置")


class KeywordDialog:
    def __init__(self, parent):
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title("添加关键词")
        self.top.geometry("380x140")
        self.top.transient(parent)
        self.top.grab_set()

        tk.Label(self.top, text="关键词:", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.entry = tk.Entry(self.top, width=30, font=("Microsoft YaHei", 11))
        self.entry.grid(row=0, column=1, padx=10, pady=10)
        self.entry.focus()
        bind_paste(self.entry)

        btn_frame = tk.Frame(self.top)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=15)
        tk.Button(btn_frame, text="确定", font=("Microsoft YaHei", 11, "bold"),
                  bg=theme.COLOR_SUCCESS, fg="white", padx=20, pady=5,
                  command=self._save).pack(side="left", padx=8)
        tk.Button(btn_frame, text="取消", font=("Microsoft YaHei", 11),
                  padx=20, pady=5, command=self.top.destroy).pack(side="left", padx=8)
        self.top.bind('<Return>', lambda e: self._save())

    def _save(self):
        kw = self.entry.get().strip()
        if kw:
            self.result = kw
            self.top.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()