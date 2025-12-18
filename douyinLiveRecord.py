import os
import re
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import uuid
from pathlib import Path
from tools import get_stream_qualities, get_app_dir
from config import gen_startup_cmd, file_version_info_cmd
from loguru import logger
import psutil
import logging
from datetime import datetime

# 初始化日志
LOG_DIR = get_app_dir() / Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger(__name__)


# 确保 output 目录存在
OUTPUT_DIR = get_app_dir() / Path("recordings")
OUTPUT_DIR.mkdir(exist_ok=True)
FFMPEG_PATH = get_app_dir() / Path("bin") / Path("ffmpeg.exe")


# ================== 录制管理器 ==================
class Recorder:
    def __init__(self):
        self.processes = {}  # {task_id: {"proc", "title", "quality", "output_file"}}
        self.ffmpeg_path = FFMPEG_PATH
        self.error_callback = None  # 用于向主窗口报告错误
        self.stopped_tasks = set()  # 新增：记录哪些任务是用户主动停止的

    def set_error_callback(self, callback):
        """设置错误回调函数，用于弹窗提示"""
        self.error_callback = callback

    def start_record(self, task_id: str, play_url: str, room_id: str, quality_name: str, title: str):
        if 'u0026' in play_url:
            play_url = play_url.replace('u0026', '&')
            logger.info(f"task_id: {task_id} title: {title} URL 包含非法字符，已进行转义")
        timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{title}_{quality_name}_{timestamp}.mp4"
        filename = filename.replace(" ", "_").replace(os.sep, "_").replace("<", "").replace(">", "").replace('"', "").replace("|", "").replace("?", "").replace("*", "")
        output_file = os.path.join(OUTPUT_DIR, filename)

        # 构造带合法请求头的 headers（关键！防 403）
        headers = (
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36\r\n"
            f"Referer: https://live.douyin.com/{room_id}/\r\n"
        )

        cmd = [
            str(self.ffmpeg_path),
            "-headers", headers,
            "-y",
            "-i", play_url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "faststart+empty_moov",
            "-f", "mp4",
            "-loglevel", "error",
            output_file
        ]

        try:
            logger.info(f"开始录制：task_id: {task_id} title: {title}")

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            self.processes[task_id] = {
                "proc": proc,
                "title": title,
                "quality": quality_name,
                "output_file": output_file,
                "stopped_by_user": False  # 标记是否由用户停止
            }

            # 启动监控线程
            threading.Thread(target=self._monitor_ffmpeg, args=(task_id,), daemon=True).start()

            logger.info(f"录制任务启动成功：{title} pid: {proc.pid} task_id: {task_id}")
            return True

        except FileNotFoundError:
            messagebox.showerror("FFmpeg 未找到", "请确保 FFmpeg 已安装并加入系统 PATH。")
            return False
        except Exception as e:
            messagebox.showerror("录制失败", f"启动录制失败：{e}")
            return False

    def _monitor_ffmpeg(self, task_id):
        """监控 ffmpeg 进程，异常退出时通知主窗口"""
        if task_id not in self.processes:
            return

        proc = self.processes[task_id]["proc"]
        title = self.processes[task_id]["title"]
        output_file = self.processes[task_id]["output_file"]
        stopped_by_user = self.processes[task_id].get("stopped_by_user", False)  # 获取标记

        stdout, stderr = proc.communicate()
        return_code = proc.returncode

        # 清理进程记录
        self.processes.pop(task_id, None)

        # 如果是用户主动停止，不报错
        if stopped_by_user:
            logger.info(f"【录制停止】{title} 已由用户停止。")
            return  # 直接返回，不触发错误回调

        # 否则，视为异常退出，但需过滤掉“正常终止”的版本信息
        if return_code != 0:
            error_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
            
            logger.info(f"【录制异常】{title} 错误信息：{error_str} <end_error_str>")
            
            # 关键：如果 stderr 只包含版本信息，且没有实际错误关键词，则忽略
            if "ffmpeg version" in error_str and len(error_str.strip()) < 500:
                # 这很可能是用户停止导致的正常退出，不报错
                logger.info(f"【录制停止】{title} 正常结束（可能由用户停止）。")
                return
            if not error_str:
                logger.info(f"【录制异常】{title} 错误信息为空，可能由用户停止。")
                return

            # 检查是否有真正的错误
            if "403 Forbidden" in error_str:
                msg = "直播流已失效（403 Forbidden）！\n请重新获取直播间地址。"
            elif "Connection refused" in error_str or "Server returned" in error_str:
                msg = "无法连接直播流，请检查直播间是否已关闭或网络是否正常。"
            elif "404 Not Found" in error_str:
                msg = "直播间不存在！请检查直播间地址是否正确。"
            elif "Invalid data found" in error_str or "moov atom not found" in error_str:
                msg = "直播流无效或已结束，录制中断。"
            elif "No such file or directory" in error_str:
                msg = "输出文件路径无效或无权限写入。"
            else:
                # 其他情况，显示完整错误信息（截取前300字符）
                msg = f"录制异常终止（退出码 {return_code}）\n{error_str[:300]}..."

            if self.error_callback:
                self.error_callback(msg)

            # 通知主窗口更新状态
            if hasattr(recorder, '_notify_task_failed'):
                recorder._notify_task_failed(task_id, "录制失败")
        else:
            # 正常结束（如手动 stop），由 stop_record 处理状态
            pass

    def stop_record(self, task_id):
        if task_id not in self.processes:
            return None

        proc = self.processes[task_id]["proc"]
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        try:
            if task_id in self.processes:
                self.processes[task_id]["stopped_by_user"] = True
                title = self.processes[task_id]["title"]
                self.processes.pop(task_id, None)
                return title
        except Exception:
            pass
        logger.info(f"【录制停止】任务 task_id: {task_id} 已由用户停止。")  # 添加日志
        return None



recorder = Recorder()


# ================== 主应用 ==================
class App:
    def __init__(self, root, version='1.0.0.0', program_title='抖音直播录制工具'):
        self.root = root
        self.program_title = program_title
        self.version = version

        self.productName = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]
        self.productDescription = self.program_title
        self.companyName = self.program_title

        self.root.title(f"{self.program_title}-v{self.version}")
        self.root.geometry("980x680")
        self.root.minsize(920, 600)

        self.gen_file_version_info()

        # 配色
        self.bg_color = "#f5f7fa"
        self.fg_color = "#1a1f29"
        self.accent_color = "#2563eb"
        self.border_color = "#cbd5e1"
        self.input_bg = "#ffffff"
        root.configure(bg=self.bg_color)

        # 状态
        self.current_qualities = []
        self.current_room_id = ""
        self.current_title = ""
        self.quality_var = tk.StringVar(value="")
        self.task_items = {}  # {task_id: {"item_id", "start_time", "status"}}
        self.placeholder_text = "请输入直播分享链接或直播间号"

        self.create_widgets()
        self._start_global_monitor()

        # 设置错误回调
        recorder.set_error_callback(self._show_ffmpeg_error)
        # 设置失败通知回调
        recorder._notify_task_failed = self._mark_task_failed

    def _show_ffmpeg_error(self, msg):
        self.root.after(0, lambda: messagebox.showerror("录制错误", msg))

    def _mark_task_failed(self, task_id, reason="录制失败"):
        info = self.task_items.get(task_id)
        if info:
            item_id = info["item_id"]
            try:
                values = self.tree.item(item_id, "values")
                new_values = (values[0], values[1], reason, values[3], "--:--:--", "● 已结束")
                self.tree.item(item_id, values=new_values, tags=("completed",))
                self.task_items[task_id]["status"] = "失败"
            except tk.TclError:
                pass

    def gen_file_version_info(self):
        """生成版本信息"""
        current_program = os.path.join(os.path.dirname(__file__), f'{self.productName}.exe')
        if not os.path.exists(current_program):
            try:
                version_info_file = os.path.join(os.path.dirname(__file__), 'file_version_info.txt')
                with open(version_info_file, 'w', encoding='utf-8', errors='ignore') as f:
                    filevers = self.version.replace('.', ',')
                    info = file_version_info_cmd.replace('FILEVERS', filevers).replace('VERSION_NO', self.version) \
                        .replace('COMPANY_NAME', self.companyName) \
                        .replace('PRODUCT_NAME', self.productName) \
                        .replace('PRODUCT_DESCRIPTION', self.productDescription).strip()
                    f.write(info)
            except:
                pass

    def create_widgets(self):
        # ===== 标题 =====
        title = tk.Label(self.root, text=f"{self.program_title}", font=("Microsoft YaHei", 18, "bold"),
                         fg=self.fg_color, bg=self.bg_color)
        title.pack(pady=(12, 6))

        # ===== 输入区域 =====
        input_frame = tk.Frame(self.root, bg=self.bg_color)
        input_frame.pack(fill=tk.X, padx=50, pady=6)

        self.url_entry = tk.Entry(
            input_frame,
            font=("Microsoft YaHei", 10),
            relief="solid",
            bd=1,
            bg=self.input_bg,
            fg="#94a0b4",
            insertbackground=self.fg_color
        )
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(8, 8))

        self.url_entry.insert(0, self.placeholder_text)
        self.url_entry.bind("<FocusIn>", self.on_entry_focus_in)
        self.url_entry.bind("<FocusOut>", self.on_entry_focus_out)
        self.url_entry.bind("<Return>", lambda e: self.fetch_qualities())

        self.fetch_btn = tk.Button(
            input_frame, text="获取清晰度", font=("Microsoft YaHei", 9, "bold"),
            bg=self.accent_color, fg="white", relief="flat", cursor="hand2",
            command=self.fetch_qualities, padx=10, pady=4
        )
        self.fetch_btn.pack(side=tk.RIGHT)

        # ===== 视频标题 =====
        title_frame = tk.Frame(self.root, bg=self.bg_color)
        title_frame.pack(fill=tk.X, padx=50, pady=(2, 8))
        tk.Label(title_frame, text="视频标题：", bg=self.bg_color, fg=self.fg_color, font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        self.title_entry = tk.Entry(title_frame, font=("Microsoft YaHei", 10), relief="solid", bd=1,
                                    bg=self.input_bg, fg=self.fg_color, state="disabled")
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3, padx=(6, 0))

        # ===== 清晰度 =====
        quality_label = tk.Label(self.root, text="清晰度：", bg=self.bg_color, fg=self.fg_color, font=("Microsoft YaHei", 10))
        quality_label.pack(padx=50, anchor="w")
        self.quality_frame = tk.Frame(self.root, bg=self.bg_color)
        self.quality_frame.pack(pady=(2, 10))

        # ===== 操作按钮 =====
        btn_frame = tk.Frame(self.root, bg=self.bg_color)
        btn_frame.pack(pady=6)

        self.record_btn = tk.Button(
            btn_frame, text="▶ 开始录制", font=("Microsoft YaHei", 10, "bold"),
            bg="#16a34a", fg="white", relief="flat", cursor="hand2",
            command=self.start_record, padx=14, pady=5, state="disabled"
        )
        self.record_btn.pack(side=tk.LEFT, padx=8)

        self.stop_all_btn = tk.Button(
            btn_frame, text="⏹ 全部停止", font=("Microsoft YaHei", 10, "bold"),
            bg="#dc2626", fg="white", relief="flat",
            command=self.stop_all_tasks, padx=12, pady=5
        )
        self.stop_all_btn.pack(side=tk.LEFT, padx=8)

        self.open_dir_btn = tk.Button(
            btn_frame, text="📁 打开目录", font=("Microsoft YaHei", 10),
            bg="#e2e8f0", fg=self.fg_color, relief="solid", bd=1,
            command=self.open_output_dir, padx=12, pady=4
        )
        self.open_dir_btn.pack(side=tk.LEFT, padx=8)

        # ===== 分割线 =====
        sep = tk.Frame(self.root, height=1, bg=self.border_color)
        sep.pack(fill=tk.X, padx=40, pady=10)

        # ===== 任务区标题 + 清除按钮 =====
        task_top_frame = tk.Frame(self.root, bg=self.bg_color)
        task_top_frame.pack(fill=tk.X, padx=50, pady=(0, 6))
        task_title = tk.Label(task_top_frame, text="录制任务", font=("Microsoft YaHei", 12, "bold"),
                              bg=self.bg_color, fg=self.fg_color)
        task_title.pack(side=tk.LEFT)
        self.clear_done_btn = tk.Button(
            task_top_frame, text="🗑 清除已完成", font=("Microsoft YaHei", 9),
            bg="#f1f5f9", fg="#dc2626", relief="solid", bd=1,
            command=self.clear_completed_tasks, padx=8, pady=2
        )
        self.clear_done_btn.pack(side=tk.RIGHT)

        # ===== Treeview 表格任务列表 =====
        tree_frame = tk.Frame(self.root, bg=self.bg_color)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=(0, 15))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", font=("Microsoft YaHei", 9), rowheight=30)
        style.map("Treeview",
                  background=[("selected", "#3b82f6")],
                  foreground=[("selected", "white")])
        style.configure("Treeview.Heading", font=("Microsoft YaHei", 10, "bold"))

        self.tree = ttk.Treeview(tree_frame, columns=("Title", "Quality", "Status", "Created", "Duration", "Action"), show="headings", height=8)
        self.tree.heading("Title", text="视频标题")
        self.tree.heading("Quality", text="清晰度")
        self.tree.heading("Status", text="状态")
        self.tree.heading("Created", text="创建时间")
        self.tree.heading("Duration", text="录制时长")
        self.tree.heading("Action", text="操作")

        self.tree.column("Title", width=180, anchor="w", stretch=True)
        self.tree.column("Quality", width=60, anchor="center")
        self.tree.column("Status", width=70, anchor="center")
        self.tree.column("Created", width=100, anchor="center")
        self.tree.column("Duration", width=80, anchor="center")
        self.tree.column("Action", width=70, anchor="center")

        self.tree.tag_configure("recording", background="#fef2f2", foreground="#dc2626")
        self.tree.tag_configure("completed", background="#f0fdf4", foreground="#16a34a")
        self.tree.tag_configure("failed", background="#fef2f2", foreground="#dc2626")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Button-1>", self.on_tree_click)

    def on_entry_focus_in(self, event):
        if self.url_entry.get() == self.placeholder_text:
            self.url_entry.delete(0, tk.END)
            self.url_entry.config(fg=self.fg_color)

    def on_entry_focus_out(self, event):
        if not self.url_entry.get().strip():
            self.url_entry.insert(0, self.placeholder_text)
            self.url_entry.config(fg="#94a0b4")

    def clear_quality_options(self):
        for widget in self.quality_frame.winfo_children():
            widget.destroy()
        self.quality_var.set("")
        if hasattr(self, 'record_btn'):
            self.record_btn.config(state="disabled")

    def fetch_qualities(self):
        raw_text = self.url_entry.get()
        if raw_text == self.placeholder_text or not raw_text.strip():
            messagebox.showwarning("输入为空", "请输入直播链接或房间号")
            return
        url_or_id = raw_text.strip()
        self.fetch_btn.config(state="disabled", text="获取中...")
        self.root.update()
        threading.Thread(target=self._fetch_worker, args=(url_or_id,), daemon=True).start()

    def _fetch_worker(self, url_or_id):
        try:
            result = get_stream_qualities(url_or_id)
        except Exception as e:
            result = {'code': 10001, 'msg': f'解析失败: {str(e)}'}
        self.root.after(0, self._on_fetch_done, result)

    def _on_fetch_done(self, result):
        self.fetch_btn.config(state="normal", text="获取清晰度")
        if result['code'] != 0:
            messagebox.showerror("失败", result['msg'])
            self.clear_quality_options()
            if hasattr(self, 'title_entry'):
                self.title_entry.config(state="normal")
                self.title_entry.delete(0, tk.END)
                self.title_entry.config(state="disabled")
            return

        data = result.get('data', {})
        self.current_title = data.get('title', f"抖音直播_{self._extract_room_id_from_url(self.url_entry.get())}")
        self.current_room_id = data.get('room_id') or self._extract_room_id_from_url(self.url_entry.get()) or "unknown"
        self.current_qualities = result.get('qualities', [])

        self.title_entry.config(state="normal")
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, self.current_title)

        self.clear_quality_options()
        if not self.current_qualities:
            messagebox.showinfo("无流", "未获取到清晰度选项")
            return

        QUALITY_ORDER = {"标清": 1, "高清": 2, "超清": 3, "蓝光": 4, "蓝光4M": 5, "蓝光8M": 6}
        self.current_qualities.sort(key=lambda x: QUALITY_ORDER.get(x['name'], 99))

        for q in self.current_qualities:
            rb_frame = tk.Frame(self.quality_frame, bg=self.bg_color)
            rb_frame.pack(side=tk.LEFT, padx=6, pady=2)

            rb = tk.Radiobutton(
                rb_frame,
                variable=self.quality_var,
                value=q['name'],
                bg=self.bg_color,
                fg=self.fg_color,
                selectcolor="#dbeafe",
                indicatoron=1,
                font=("Microsoft YaHei", 11, "bold"),
                padx=0,
                pady=4
            )
            rb.pack(side=tk.LEFT)

            label = tk.Label(
                rb_frame,
                text=q['name'],
                font=("Microsoft YaHei", 9),
                bg=self.bg_color,
                fg=self.fg_color
            )
            label.pack(side=tk.LEFT, padx=(2, 0))

        self.quality_var.set(self.current_qualities[0]['name'])
        self.record_btn.config(state="normal")

    def _extract_room_id_from_url(self, url):
        if str(url).isdigit():
            return url
        match = re.search(r'live\.douyin\.com/(\d+)', url)
        return match.group(1) if match else "unknown"

    def start_record(self):
        if not os.path.exists(recorder.ffmpeg_path):
            messagebox.showerror("错误", "文件缺失~！")
            return
        selected = self.quality_var.get()
        if not selected:
            messagebox.showwarning("未选择", "请选择清晰度")
            return
        title = self.title_entry.get().strip() or "未命名直播"
        play_url = next((q['playUrl'] for q in self.current_qualities if q['name'] == selected), None)
        if not play_url:
            messagebox.showerror("错误", "未找到播放地址")
            return

        task_id = f"{self.current_room_id}_{selected}_{uuid.uuid4().hex[:8]}"
        success = recorder.start_record(task_id, play_url, self.current_room_id, selected, title)
        if success:
            self.add_task_row(task_id, title, selected, "录制中")
        else:
            return

    def add_task_row(self, task_id, title, quality, status):
        now = __import__('datetime').datetime.now()
        start_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        duration_str = "00:00:00" if status == "录制中" else "--:--:--"
        tag = "recording" if status == "录制中" else "completed"

        item_id = self.tree.insert("", tk.END, values=(
            title, quality, status, start_time_str, duration_str, "⏹ 停止"
        ), tags=(tag,))
        self.task_items[task_id] = {
            "item_id": item_id,
            "start_time": now,
            "status": status
        }

    def _start_global_monitor(self):
        def monitor():
            while True:
                now = __import__('datetime').datetime.now()
                for task_id, info in list(self.task_items.items()):
                    if info["status"] == "录制中" and task_id in recorder.processes:
                        start = info["start_time"]
                        duration = now - start
                        h, m, s = duration.seconds // 3600, (duration.seconds // 60) % 60, duration.seconds % 60
                        duration_str = f"{h:02d}:{m:02d}:{s:02d}"
                        item_id = info["item_id"]
                        try:
                            values = self.tree.item(item_id, "values")
                            if len(values) >= 6 and values[2] == "录制中":
                                new_values = (values[0], values[1], "录制中", values[3], duration_str, "⏹ 停止")
                                self.root.after(0, lambda iid=item_id, v=new_values: self.tree.item(iid, values=v))
                        except tk.TclError:
                            pass
                    elif info["status"] == "录制中" and task_id not in recorder.processes:
                        self.root.after(0, self._mark_task_completed, task_id)
                time.sleep(1)
        threading.Thread(target=monitor, daemon=True).start()

    def _mark_task_completed(self, task_id):
        info = self.task_items.get(task_id)
        if info and info["status"] == "录制中":
            item_id = info["item_id"]
            try:
                values = self.tree.item(item_id, "values")
                start = info["start_time"]
                duration = __import__('datetime').datetime.now() - start
                h, m, s = duration.seconds // 3600, (duration.seconds // 60) % 60, duration.seconds % 60
                duration_str = f"{h:02d}:{m:02d}:{s:02d}"
                new_values = (values[0], values[1], "录制完成", values[3], duration_str, "✅ 已结束")
                self.tree.item(item_id, values=new_values, tags=("completed",))
                self.task_items[task_id]["status"] = "录制完成"
            except tk.TclError:
                pass

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        column = self.tree.identify_column(event.x)
        if region == "cell" and column == "#6":  # 第6列是“操作”
            item_id = self.tree.identify_row(event.y)
            if not item_id:
                return
            try:
                values = self.tree.item(item_id, "values")
                if len(values) < 3:
                    return
                status = values[2]
                if status != "录制中":
                    return

                task_id = None
                for tid, info in self.task_items.items():
                    if info["item_id"] == item_id:
                        task_id = tid
                        break
                if not task_id:
                    return

                if messagebox.askyesno("停止录制", f"确定停止录制？\n标题: {values[0]}\n清晰度: {values[1]}"):
                    self.stop_task(task_id)
            except tk.TclError:
                pass

    def stop_task(self, task_id, show_tips=False):
        title = recorder.stop_record(task_id)
        if title is not None:
            info = self.task_items.get(task_id)
            if info:
                item_id = info["item_id"]
                try:
                    values = self.tree.item(item_id, "values")
                    start = info["start_time"]
                    duration = __import__('datetime').datetime.now() - start
                    h, m, s = duration.seconds // 3600, (duration.seconds // 60) % 60, duration.seconds % 60
                    duration_str = f"{h:02d}:{m:02d}:{s:02d}"
                    new_values = (values[0], values[1], "已停止", values[3], duration_str, "● 已结束")
                    self.tree.item(item_id, values=new_values, tags=("completed",))
                    self.task_items[task_id]["status"] = "已停止"
                    if show_tips:
                        messagebox.showinfo("已停止", f"录制任务已停止：\n{values[0]}")
                except tk.TclError:
                    pass
        else:
            # 如果任务已不存在，可选择静默处理或提示
            logger.info(f"【提示】任务 {task_id} 已不存在，可能已自动结束。")


    def stop_all_tasks(self):
        # 1. 停止已知任务
        recording_tasks = [
            tid for tid, info in self.task_items.items()
            if info["status"] == "录制中"
        ]


        stopped_count = len(recording_tasks)

        if not stopped_count:
            messagebox.showinfo("提示", "没有正在录制的任务")
            return
        if not messagebox.askyesno("全部停止", f"确定要停止 {stopped_count} 个正在录制的任务？"):
            return
        for task_id in recording_tasks:
            self.stop_task(task_id, show_tips=False)

        # 2. 扫描并终止所有 bin/ffmpeg.exe 进程
        ffmpeg_path_str = str(FFMPEG_PATH).lower()
        extra_killed = 0
        for proc in psutil.process_iter(['pid', 'exe', 'cmdline']):
            try:
                if proc.info['exe'] and ffmpeg_path_str in proc.info['exe'].lower():
                    proc.kill()
                    extra_killed += 1
                    logger.info(f"强制终止残留 ffmpeg 进程: PID={proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        total_stopped = stopped_count + extra_killed

        if total_stopped > 0:
            messagebox.showinfo("完成", f"已停止 {total_stopped} 个录制任务（含 {extra_killed} 个残留进程）")
        else:
            messagebox.showinfo("提示", "没有正在录制的任务")

    def clear_completed_tasks(self):
        to_remove = []
        for task_id, info in list(self.task_items.items()):
            item_id = info["item_id"]
            try:
                values = self.tree.item(item_id, "values")
                if len(values) >= 3:
                    status = values[2]
                    if status in ("录制完成", "已停止", "录制失败"):
                        to_remove.append(task_id)
                        self.tree.delete(item_id)
            except tk.TclError:
                to_remove.append(task_id)
        for tid in to_remove:
            self.task_items.pop(tid, None)
        if not to_remove:
            messagebox.showinfo("提示", "没有已完成的任务可清除")

    def open_output_dir(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        try:
            if os.name == 'nt':
                os.startfile(OUTPUT_DIR)
            else:
                subprocess.run(["xdg-open", OUTPUT_DIR])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开目录：{e}")


# ================== 启动 ==================
if __name__ == "__main__":
    root = tk.Tk()
    root.eval('tk::PlaceWindow . center')
    app = App(root, version='1.0.0.1')
    root.mainloop()