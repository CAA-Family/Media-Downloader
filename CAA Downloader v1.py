import os
import tkinter as tk
from tkinter import messagebox, ttk, filedialog, scrolledtext
import threading
import requests
from PIL import Image, ImageTk
from io import BytesIO
import webbrowser
import queue
import shutil

try:
    from yt_dlp import YoutubeDL
except ImportError:
    YoutubeDL = None

# --- Configuration & Assets ---
APP_NAME = "CAA Downloader"
BG_COLOR = "#0f1419"
SIDEBAR_COLOR = "#1a1f2e"
CONTENT_COLOR = "#0f1419"
CARD_COLOR = "#1a1f2e"
PRIMARY_COLOR = "#667eea"
TEXT_COLOR_NORMAL = "#a0aec0"
TEXT_COLOR_BRIGHT = "#ffffff"
FONT_FAMILY = "Segoe UI"
PLACEHOLDER_TEXT = "Paste video link here..."

class CustomError(Exception): pass

class LogViewer(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master, bg=CONTENT_COLOR); self.title("Log Viewer"); self.geometry("800x400")
        self.log_area = scrolledtext.ScrolledText(self, state='disabled', bg=BG_COLOR, fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 9))
        self.log_area.pack(expand=True, fill='both'); self.protocol("WM_DELETE_WINDOW", self.withdraw)

    def log(self, message):
        if not self.winfo_exists(): return
        self.log_area.configure(state='normal'); self.log_area.insert(tk.END, message); self.log_area.configure(state='disabled'); self.log_area.see(tk.END)

class MyLogger:
    def __init__(self, log_queue): self.log_queue = log_queue
    def debug(self, msg):
        if msg.startswith('[debug] '): self.log_queue.put(f"DEBUG: {msg}\n")
    def info(self, msg): self.log_queue.put(f"INFO: {msg}\n")
    def warning(self, msg): self.log_queue.put(f"WARNING: {msg}\n")
    def error(self, msg): self.log_queue.put(f"ERROR: {msg}\n")

class SettingsWindow(tk.Toplevel):
    def __init__(self, master, app_instance):
        super().__init__(master, bg=CONTENT_COLOR); self.transient(master); self.title("Settings"); self.geometry("550x520"); self.resizable(False, False); self.app = app_instance
        tk.Label(self, text="Application Settings", bg=CONTENT_COLOR, fg=TEXT_COLOR_BRIGHT, font=(FONT_FAMILY, 14, "bold")).pack(pady=(15, 20))
        path_frame = tk.Frame(self, bg=CONTENT_COLOR); path_frame.pack(fill="x", padx=20, pady=5); tk.Label(path_frame, text="Download Path:", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 10)).pack(side="left"); self.path_entry = tk.Entry(path_frame, textvariable=self.app.download_path_var, font=(FONT_FAMILY, 9), bg=CARD_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat"); self.path_entry.pack(side="left", fill="x", expand=True, padx=10); browse_btn = tk.Button(path_frame, text="Browse", command=self.browse_directory, bg=SIDEBAR_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat"); browse_btn.pack(side="left")
        network_frame = tk.LabelFrame(self, text="Network Settings", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, padx=10, pady=10, font=(FONT_FAMILY, 10)); network_frame.pack(fill="x", padx=20, pady=10)
        timeout_frame = tk.Frame(network_frame, bg=CONTENT_COLOR); timeout_frame.pack(fill='x'); tk.Label(timeout_frame, text="Network Timeout (seconds):", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL).pack(side="left"); self.timeout_entry = tk.Entry(timeout_frame, textvariable=self.app.socket_timeout_var, font=(FONT_FAMILY, 9), width=10, bg=CARD_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat"); self.timeout_entry.pack(side="left", padx=5)
        ipv4_check = tk.Checkbutton(network_frame, text="Force IPv4 for connections", variable=self.app.force_ipv4_var, bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, selectcolor=BG_COLOR, activebackground=CONTENT_COLOR, activeforeground=TEXT_COLOR_NORMAL); ipv4_check.pack(anchor='w', pady=(5,0))
        proxy_method_frame = tk.Frame(network_frame, bg=CONTENT_COLOR); proxy_method_frame.pack(fill='x', pady=(10, 5), anchor='w'); tk.Label(proxy_method_frame, text="Proxy Method:", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL).pack(side="left", padx=(0, 10)); tk.Radiobutton(proxy_method_frame, text="None", variable=self.app.proxy_method_var, value="none", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, selectcolor=BG_COLOR, activebackground=CONTENT_COLOR, command=self.toggle_manual_proxy_entry).pack(side="left"); tk.Radiobutton(proxy_method_frame, text="System", variable=self.app.proxy_method_var, value="system", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, selectcolor=BG_COLOR, activebackground=CONTENT_COLOR, command=self.toggle_manual_proxy_entry).pack(side="left", padx=5); tk.Radiobutton(proxy_method_frame, text="Manual", variable=self.app.proxy_method_var, value="manual", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, selectcolor=BG_COLOR, activebackground=CONTENT_COLOR, command=self.toggle_manual_proxy_entry).pack(side="left")
        self.manual_proxy_frame = tk.Frame(network_frame, bg=CONTENT_COLOR); self.manual_proxy_frame.pack(fill='x', pady=5); self.manual_proxy_label = tk.Label(self.manual_proxy_frame, text="Manual Proxy Address:", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL); self.manual_proxy_label.pack(side="left", padx=(20,0)); self.proxy_entry = tk.Entry(self.manual_proxy_frame, textvariable=self.app.proxy_address_var, font=(FONT_FAMILY, 9), bg=CARD_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat"); self.proxy_entry.pack(side="left", fill="x", expand=True, padx=10)
        cookie_main_frame = tk.LabelFrame(self, text="Cookie Settings", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, padx=10, pady=10, font=(FONT_FAMILY, 10)); cookie_main_frame.pack(fill="x", padx=20, pady=10); self.cookie_check = tk.Checkbutton(cookie_main_frame, text="Use Cookies", variable=self.app.use_cookies_var, bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, selectcolor=BG_COLOR, activebackground=CONTENT_COLOR, command=self.toggle_cookie_widgets); self.cookie_check.pack(anchor="w"); self.radio_frame = tk.Frame(cookie_main_frame, bg=CONTENT_COLOR); self.radio_frame.pack(fill="x", pady=(5,0)); tk.Radiobutton(self.radio_frame, text="From File", variable=self.app.cookie_source_var, value="file", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, selectcolor=BG_COLOR, activebackground=CONTENT_COLOR, command=self.toggle_cookie_source_widgets).pack(side="left"); tk.Radiobutton(self.radio_frame, text="From Browser (Recommended)", variable=self.app.cookie_source_var, value="browser", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, selectcolor=BG_COLOR, activebackground=CONTENT_COLOR, command=self.toggle_cookie_source_widgets).pack(side="left", padx=10)
        tk.Label(cookie_main_frame, text="Note: For browser cookies, fully close your browser first for best results.", font=(FONT_FAMILY, 8, "italic"), bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL).pack(anchor='w', pady=5)
        self.file_cookie_frame = tk.Frame(cookie_main_frame, bg=CONTENT_COLOR); self.file_cookie_frame.pack(fill="x", pady=5); self.cookie_file_entry = tk.Entry(self.file_cookie_frame, textvariable=self.app.cookie_path_var, font=(FONT_FAMILY, 9), bg=CARD_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat"); self.cookie_file_entry.pack(side="left", fill="x", expand=True); browse_cookie_btn = tk.Button(self.file_cookie_frame, text="Browse File", command=self.browse_cookie_file, bg=SIDEBAR_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat"); browse_cookie_btn.pack(side="left", padx=(5,0))
        self.browser_cookie_frame = tk.Frame(cookie_main_frame, bg=CONTENT_COLOR); self.browser_cookie_frame.pack(fill="x", pady=5); tk.Label(self.browser_cookie_frame, text="Browser:", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL).pack(side="left"); self.browser_combo = ttk.Combobox(self.browser_cookie_frame, textvariable=self.app.browser_cookie_var, state="readonly", values=["chrome", "firefox", "edge", "opera", "vivaldi", "brave"]); self.browser_combo.pack(side="left", padx=10)
        self.browser_profile_frame = tk.Frame(cookie_main_frame, bg=CONTENT_COLOR); self.browser_profile_frame.pack(fill="x", pady=5); tk.Label(self.browser_profile_frame, text="Profile (Optional):", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL).pack(side="left"); self.browser_profile_entry = tk.Entry(self.browser_profile_frame, textvariable=self.app.browser_profile_var, font=(FONT_FAMILY, 9), bg=CARD_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat"); self.browser_profile_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.toggle_manual_proxy_entry(); self.toggle_cookie_widgets()
        save_btn = tk.Button(self, text="Save & Close", command=self.destroy, bg=PRIMARY_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat", font=(FONT_FAMILY, 10, "bold"), padx=15, pady=8); save_btn.pack(side="bottom", pady=20)
        self.grab_set()

    def toggle_manual_proxy_entry(self): state = "normal" if self.app.proxy_method_var.get() == "manual" else "disabled"; self.manual_proxy_label.config(state=state); self.proxy_entry.config(state=state)
    def toggle_cookie_widgets(self): state = "normal" if self.app.use_cookies_var.get() else "disabled"; [w.config(state=state) for w in self.radio_frame.winfo_children()]; self.toggle_cookie_source_widgets()
    def toggle_cookie_source_widgets(self):
        if not self.app.use_cookies_var.get(): [w.config(state="disabled") for frame in [self.file_cookie_frame, self.browser_cookie_frame, self.browser_profile_frame] for w in frame.winfo_children()]; return
        source = self.app.cookie_source_var.get(); file_state, browser_state = ("normal", "disabled") if source == "file" else ("disabled", "normal")
        [w.config(state=file_state) for w in self.file_cookie_frame.winfo_children()]; [w.config(state=browser_state) for w in self.browser_cookie_frame.winfo_children()]; [w.config(state=browser_state) for w in self.browser_profile_frame.winfo_children()]
    def browse_directory(self): path = filedialog.askdirectory(initialdir=self.app.download_path_var.get());_ = path and self.app.download_path_var.set(path)
    def browse_cookie_file(self): path = filedialog.askopenfilename(title="Select Cookie File", filetypes=[("Text files", "*.txt"), ("All files", "*.*")]); _ = path and self.app.cookie_path_var.set(path)

class QualitySelectionWindow(tk.Toplevel):
    def __init__(self, master, app_instance, info):
        super().__init__(master, bg=CONTENT_COLOR); self.transient(master); self.title("Select Quality"); self.geometry("450x300"); self.resizable(False, False); self.app, self.info = app_instance, info
        tk.Label(self, text="Select Download Quality", bg=CONTENT_COLOR, fg=TEXT_COLOR_BRIGHT, font=(FONT_FAMILY, 12, "bold")).pack(pady=10)
        tk.Label(self, text=info.get('title', '')[:50], bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 9)).pack(pady=(0, 10))
        self.format_id_var = tk.StringVar()
        qualities = {"Best Available": "bestvideo*+bestaudio/best", "1080p": "bestvideo[height<=1080]+bestaudio/best", "720p": "bestvideo[height<=720]+bestaudio/best", "Audio Only (MP3)": "bestaudio/best"}
        
        for text, format_id in qualities.items():
            rb = tk.Radiobutton(self, text=text, variable=self.format_id_var, value=format_id, bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, selectcolor=BG_COLOR, activebackground=CONTENT_COLOR)
            rb.pack(anchor='w', padx=20)
            if "bestvideo" in format_id and not self.app.ffmpeg_installed:
                rb.config(state="disabled")

        self.format_id_var.set(qualities["Audio Only (MP3)"] if not self.app.ffmpeg_installed else qualities["Best Available"])
        
        start_btn = tk.Button(self, text="Start Download", command=self.start_download, bg=PRIMARY_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat", font=(FONT_FAMILY, 10, "bold"), padx=15, pady=8); start_btn.pack(side="bottom", pady=20)
        self.grab_set()

    def start_download(self):
        format_id = self.format_id_var.get()
        if not format_id: messagebox.showerror("Error", "Please select a quality.", parent=self); return
        self.app._create_download_task(self.info['original_url'], format_id, self.info)
        self.destroy()

class DownloadCard(tk.Frame):
    def __init__(self, parent, info, url, format_id, app):
        super().__init__(parent, bg=CARD_COLOR); self.info, self.url, self.format_id, self.app = info, url, format_id, app
        self.state = "queued"; self.download_thread = None
        self.thumb_label = tk.Label(self, bg=BG_COLOR, width=20, height=9, text="🖼️", fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 20)); self.thumb_label.pack(side="left", padx=15, pady=15)
        main_info_frame = tk.Frame(self, bg=self['bg']); main_info_frame.pack(side="left", fill="both", expand=True, padx=(0, 15))
        self.title_label = tk.Label(main_info_frame, text=info.get('title', 'Unknown')[:45], bg=self['bg'], fg=TEXT_COLOR_BRIGHT, font=(FONT_FAMILY, 11, "bold"), anchor="w", justify="left"); self.title_label.pack(fill="x", pady=(10, 2))
        self.channel_label = tk.Label(main_info_frame, text=f"Uploader: {info.get('uploader', 'N/A')}", bg=self['bg'], fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 9), anchor="w"); self.channel_label.pack(fill="x")
        status_frame = tk.Frame(main_info_frame, bg=self['bg']); status_frame.pack(fill='x', pady=2)
        self.status_label = tk.Label(status_frame, text="Status: Queued", bg=self['bg'], fg=PRIMARY_COLOR, font=(FONT_FAMILY, 9, "italic"), anchor="w"); self.status_label.pack(side="left")
        self.speed_label = tk.Label(status_frame, text="", bg=self['bg'], fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 9), anchor="e"); self.speed_label.pack(side="right")
        self.progress_var = tk.DoubleVar(); self.progress_bar = ttk.Progressbar(main_info_frame, variable=self.progress_var, maximum=100, style="TProgressbar"); self.progress_bar.pack(fill="x", pady=(0, 5))
        controls_frame = tk.Frame(main_info_frame, bg=self['bg']); controls_frame.pack(fill='x', pady=(0,5))
        self.pause_resume_button = tk.Button(controls_frame, text="Pause", command=self.toggle_pause_resume, bg="#4a5568", fg=TEXT_COLOR_BRIGHT, relief="flat", font=(FONT_FAMILY, 8, "bold"), width=10); self.pause_resume_button.pack(side="right")
        self.cancel_button = tk.Button(controls_frame, text="Cancel", command=self.cancel_download, bg="#c94444", fg=TEXT_COLOR_BRIGHT, relief="flat", font=(FONT_FAMILY, 8, "bold"), width=10); self.cancel_button.pack(side="right", padx=5)
        self.load_thumbnail(info.get('thumbnail'))

    def load_thumbnail(self, url):
        if url: threading.Thread(target=self._load_image_task, args=(url,), daemon=True).start()
    def _load_image_task(self, url):
        try:
            response = requests.get(url, timeout=10)
            img = Image.open(BytesIO(response.content)); img.thumbnail((160, 90), Image.Resampling.LANCZOS); photo = ImageTk.PhotoImage(img)
            self.thumb_label.config(image=photo, width=160, height=90, text=""); self.thumb_label.image = photo
        except Exception: self.thumb_label.config(text="No Preview", font=(FONT_FAMILY, 10))
    
    def update_progress(self, d):
        if self.state in ["pausing", "cancelled"]: raise CustomError("Download Interrupted")
        if d['status'] == 'downloading':
            self.state = "downloading"
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total_bytes: percent = (d['downloaded_bytes'] / total_bytes) * 100; self.progress_var.set(percent); self.status_label.config(text=f"Downloading... {percent:.1f}%")
            speed = d.get('speed'); self.speed_label.config(text=f"{speed / 1024 / 1024:.2f} MiB/s" if speed else "")
        elif d['status'] == 'finished':
            self.state = "finished"
            self.progress_var.set(100); self.status_label.config(text="Completed!", fg="#4ade80"); self.speed_label.config(text="")
            self.pause_resume_button.config(state="disabled"); self.cancel_button.config(text="Remove", command=self.destroy)

    def toggle_pause_resume(self):
        if self.state == "downloading": self.state = "pausing"; self.status_label.config(text="Pausing..."); self.pause_resume_button.config(text="Pausing...", state="disabled")
        elif self.state == "paused": self.state = "resuming"; self.status_label.config(text="Resuming..."); self.pause_resume_button.config(text="Pause", state="normal"); self.app.start_download_thread(self)

    def cancel_download(self): self.state = "cancelled"; self.destroy()

class App:
    def __init__(self, root):
        self.root = root; self.root.title(APP_NAME); self.root.geometry("1000x700"); self.root.configure(bg=BG_COLOR); self.root.minsize(900, 600)
        
        default_folder = os.path.join(os.path.expanduser("~"), "Videos", "CAA Downloader")
        self.download_path_var = tk.StringVar(value=default_folder)
        self.socket_timeout_var = tk.StringVar(value="60"); self.force_ipv4_var = tk.BooleanVar(value=False); self.proxy_method_var = tk.StringVar(value="none"); self.proxy_address_var = tk.StringVar(value="http://127.0.0.1:8080"); self.use_cookies_var = tk.BooleanVar(value=False); self.cookie_source_var = tk.StringVar(value="browser"); self.cookie_path_var = tk.StringVar(); self.browser_cookie_var = tk.StringVar(value="chrome"); self.browser_profile_var = tk.StringVar()
        self.platforms = {'youtube': {'name': 'YouTube', 'icon': '🔴', 'supported': True}, 'aparat': {'name': 'Aparat', 'icon': '🟠', 'supported': False}, 'instagram': {'name': 'Instagram', 'icon': '🟣', 'supported': False}}
        self.log_queue = queue.Queue(); self.log_viewer = LogViewer(self.root); self.log_viewer.withdraw()
        
        self.ffmpeg_installed = self.check_ffmpeg()
        
        self.setup_styles(); self.create_widgets(); self.root.bind('<Configure>', self.on_resize); self.select_platform('youtube'); self.process_log_queue()
        threading.Thread(target=self.check_youtube_connection, daemon=True).start()
        
        if not self.ffmpeg_installed:
            self.root.after(500, self.show_ffmpeg_warning)

    def check_ffmpeg(self):
        self.log_queue.put("Checking for FFmpeg...\n")
        if shutil.which("ffmpeg"):
            self.log_queue.put("FFmpeg found.\n")
            return True
        self.log_queue.put("FFmpeg not found. Merging formats will be disabled.\n")
        return False
        
    def show_ffmpeg_warning(self):
        messagebox.showwarning("FFmpeg Not Found",
                               "FFmpeg is not installed on your system. You will not be able to download high-quality videos (which require merging video and audio).\n\n"
                               "Please install FFmpeg and add it to your system's PATH to enable all quality options.\n\n"
                               "You can download it from: gyan.dev/ffmpeg/builds/")

    def check_youtube_connection(self):
        self.log_queue.put("Pinging youtube.com...\n")
        try: requests.head("https://www.youtube.com", timeout=5); self.log_queue.put("YouTube connection successful.\n")
        except requests.exceptions.RequestException as e:
            self.log_queue.put(f"YouTube connection failed: {e}\n")
            self.root.after(0, lambda: messagebox.showwarning("Connection Error", "Could not connect to YouTube. Please check your network or proxy settings."))

    def process_log_queue(self):
        try:
            while True: self.log_viewer.log(self.log_queue.get_nowait())
        except queue.Empty: pass
        self.root.after(100, self.process_log_queue)

    def setup_styles(self):
        style = ttk.Style(); style.theme_use('clam')
        style.configure("TProgressbar", background=PRIMARY_COLOR, troughcolor="#2d3748", borderwidth=0)
        style.configure("TCombobox", selectbackground=PRIMARY_COLOR, fieldbackground=CARD_COLOR, background=CARD_COLOR, foreground=TEXT_COLOR_BRIGHT, arrowcolor=TEXT_COLOR_BRIGHT)
        style.map('TCombobox', fieldbackground=[('readonly', CARD_COLOR)], selectbackground=[('readonly', CARD_COLOR)], selectforeground=[('readonly', TEXT_COLOR_BRIGHT)])

    def create_widgets(self):
        self.sidebar = tk.Frame(self.root, bg=SIDEBAR_COLOR, width=220); self.sidebar.pack(side="left", fill="y"); self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text=APP_NAME, bg=SIDEBAR_COLOR, fg=TEXT_COLOR_BRIGHT, font=(FONT_FAMILY, 16, "bold")).pack(pady=20, padx=15)
        self.platform_buttons = {}; [self.create_platform_button(id, info) for id, info in self.platforms.items()]
        tg_link = tk.Label(self.sidebar, text="📢 @CAA_Premium", bg=SIDEBAR_COLOR, fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 10, "bold"), cursor="hand2"); tg_link.pack(side="bottom", fill="x", pady=20); tg_link.bind("<Button-1>", lambda e: webbrowser.open_new("https://t.me/CAA_Premium")); self.add_hover_effect(tg_link, TEXT_COLOR_NORMAL, TEXT_COLOR_BRIGHT, is_label=True)
        self.content_area = tk.Frame(self.root, bg=CONTENT_COLOR); self.content_area.pack(side="right", fill="both", expand=True)
        self.main_view = tk.Frame(self.content_area, bg=CONTENT_COLOR); header = tk.Frame(self.main_view, bg=CONTENT_COLOR); header.pack(fill="x", padx=30, pady=20); tk.Label(header, text="Video Downloader", bg=CONTENT_COLOR, fg=TEXT_COLOR_BRIGHT, font=(FONT_FAMILY, 22, "bold")).pack(side="left")
        controls_frame = tk.Frame(header, bg=CONTENT_COLOR); controls_frame.pack(side="right"); log_btn = tk.Button(controls_frame, text="Show Log", command=self.toggle_log_viewer, bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 9), relief="flat"); log_btn.pack(side="right", padx=5); self.add_hover_effect(log_btn, TEXT_COLOR_NORMAL, TEXT_COLOR_BRIGHT, is_label=True); settings_btn = tk.Button(controls_frame, text="⚙️", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 16), relief="flat", command=self.open_settings_window); settings_btn.pack(side="right"); self.add_hover_effect(settings_btn, TEXT_COLOR_NORMAL, TEXT_COLOR_BRIGHT, is_label=True)
        url_frame = tk.Frame(self.main_view, bg=CARD_COLOR); url_frame.pack(fill="x", padx=30); self.url_entry = tk.Entry(url_frame, font=(FONT_FAMILY, 12), bg=CARD_COLOR, fg=TEXT_COLOR_NORMAL, insertbackground=PRIMARY_COLOR, relief="flat", bd=0); self.url_entry.pack(side="left", fill="x", expand=True, ipady=12, padx=(10, 0)); self.url_entry.insert(0, PLACEHOLDER_TEXT); self.url_entry.bind("<FocusIn>", self.on_url_focus_in); self.url_entry.bind("<FocusOut>", self.on_url_focus_out); self.create_url_context_menu(); self.url_entry.bind("<Button-3>", self.show_url_context_menu); clear_btn = tk.Label(url_frame, text="×", bg=CARD_COLOR, fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 16)); clear_btn.pack(side="right", padx=(0, 10)); clear_btn.bind("<Button-1>", self.clear_url_entry)
        self.add_to_queue_btn = tk.Button(self.main_view, text="Get Info 📥", bg=PRIMARY_COLOR, fg=TEXT_COLOR_BRIGHT, font=(FONT_FAMILY, 10, "bold"), relief="flat", padx=20, pady=10, command=self.fetch_video_info); self.add_to_queue_btn.pack(anchor="e", padx=30, pady=(15, 20)); self.add_hover_effect(self.add_to_queue_btn, PRIMARY_COLOR, "#5a6fd8")
        tk.Label(self.main_view, text="Download Queue", bg=CONTENT_COLOR, fg=TEXT_COLOR_BRIGHT, font=(FONT_FAMILY, 16, "bold")).pack(anchor="w", padx=30)
        canvas_frame = tk.Frame(self.main_view, bg=CONTENT_COLOR); canvas_frame.pack(fill="both", expand=True, padx=30, pady=(10, 20)); self.canvas = tk.Canvas(canvas_frame, bg=CONTENT_COLOR, highlightthickness=0); scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview); self.scrollable_frame = tk.Frame(self.canvas, bg=CONTENT_COLOR); self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))); self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw"); self.canvas.configure(yscrollcommand=scrollbar.set); self.canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        self.coming_soon_view = tk.Frame(self.content_area, bg=CONTENT_COLOR); tk.Label(self.coming_soon_view, text="Coming Soon!", bg=CONTENT_COLOR, fg=PRIMARY_COLOR, font=(FONT_FAMILY, 30, "bold")).pack(pady=20); tk.Label(self.coming_soon_view, text="Support for this platform will be added in future updates.", bg=CONTENT_COLOR, fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 12)).pack()

    def create_platform_button(self, id, info): btn = tk.Button(self.sidebar, text=f" {info['icon']} {info['name']}", bg=SIDEBAR_COLOR, fg=TEXT_COLOR_NORMAL, font=(FONT_FAMILY, 11), relief="flat", anchor="w", command=lambda p=id: self.select_platform(p)); btn.pack(fill="x", padx=10, pady=5); self.platform_buttons[id] = btn; self.add_hover_effect(btn, SIDEBAR_COLOR, "#2c3a4f")
    def toggle_log_viewer(self):_ = self.log_viewer.state() == "normal" and self.log_viewer.withdraw() or self.log_viewer.deiconify()
    def add_hover_effect(self, w, c_def, c_hov, is_label=False): prop = 'fg' if is_label else 'bg'; w.bind("<Enter>", lambda e: w.config(**{prop: c_hov})); w.bind("<Leave>", lambda e: w.config(**{prop: c_def}))
    def create_url_context_menu(self): self.url_context_menu = tk.Menu(self.root, tearoff=0, bg=CARD_COLOR, fg=TEXT_COLOR_BRIGHT, relief="flat", font=(FONT_FAMILY, 9)); self.url_context_menu.add_command(label="Cut", command=lambda: self.url_entry.event_generate("<<Cut>>")); self.url_context_menu.add_command(label="Copy", command=lambda: self.url_entry.event_generate("<<Copy>>")); self.url_context_menu.add_command(label="Paste", command=lambda: self.url_entry.event_generate("<<Paste>>"))
    def show_url_context_menu(self, e): self.url_context_menu.tk_popup(e.x_root, e.y_root)
    def on_url_focus_in(self, e):_ = self.url_entry.get() == PLACEHOLDER_TEXT and (self.url_entry.delete(0, "end"), self.url_entry.config(fg=TEXT_COLOR_BRIGHT))
    def on_url_focus_out(self, e):_ = not self.url_entry.get() and (self.url_entry.insert(0, PLACEHOLDER_TEXT), self.url_entry.config(fg=TEXT_COLOR_NORMAL))
    def clear_url_entry(self, e=None): self.url_entry.delete(0, "end"); self.on_url_focus_out(None)
    def select_platform(self, p_id): _ = self.platforms[p_id]['supported'] and (self.coming_soon_view.pack_forget(), self.main_view.pack(fill="both", expand=True)) or (self.main_view.pack_forget(), self.coming_soon_view.pack(fill="both", expand=True, pady=100))
    def open_settings_window(self): SettingsWindow(self.root, self)
    def fetch_video_info(self): url = self.url_entry.get().strip();_ = url and url != PLACEHOLDER_TEXT and (self.add_to_queue_btn.config(text="Getting Info...", state="disabled"), threading.Thread(target=self._fetch_info_task, args=(url,), daemon=True).start())

    def _get_ydl_opts(self):
        ydl_opts = {'noplaylist': True, 'quiet': True, 'verbose': True, 'logger': MyLogger(self.log_queue)}
        try: ydl_opts['socket_timeout'] = int(self.socket_timeout_var.get())
        except (ValueError, tk.TclError): ydl_opts['socket_timeout'] = 60
        if self.force_ipv4_var.get(): ydl_opts['source_address'] = '0.0.0.0'
        proxy_method = self.proxy_method_var.get()
        if proxy_method == "system": ydl_opts['proxy'] = ":".join(webbrowser.get().name.split())
        elif proxy_method == "manual":
            proxy_address = self.proxy_address_var.get().strip();_ = proxy_address and ydl_opts.update({'proxy': proxy_address})
        if self.use_cookies_var.get():
            if self.cookie_source_var.get() == "file" and self.cookie_path_var.get() and os.path.exists(self.cookie_path_var.get()): ydl_opts['cookiefile'] = self.cookie_path_var.get()
            elif self.cookie_source_var.get() == "browser" and self.browser_cookie_var.get():
                browser, profile = self.browser_cookie_var.get(), self.browser_profile_var.get().strip()
                ydl_opts['cookies_from_browser'] = (browser, profile) if profile else (browser,)
        return ydl_opts

    def _fetch_info_task(self, url):
        try:
            self.log_queue.put(f"--- Getting info for: {url} ---\n"); ydl_opts = self._get_ydl_opts()
            with YoutubeDL(ydl_opts) as ydl: info = ydl.extract_info(url, download=False); info['original_url'] = url; self.root.after(0, self.show_quality_selection, info)
        except Exception as e: self.root.after(0, messagebox.showerror, "Error", f"Could not get video info:\n{e}")
        finally: self.root.after(0, self.add_to_queue_btn.config, {'text': "Get Info 📥", 'state': "normal"})
    
    def show_quality_selection(self, info): QualitySelectionWindow(self.root, self, info)
    
    def _create_download_task(self, url, format_id, info):
        download_dir = self.download_path_var.get()
        if not os.path.exists(download_dir):
            if messagebox.askyesno("Create Folder?", f"The download folder '{download_dir}' does not exist.\n\nDo you want to create it?"):
                try: os.makedirs(download_dir); self.log_queue.put(f"Created download directory: {download_dir}\n")
                except Exception as e: messagebox.showerror("Error", f"Could not create directory:\n{e}"); return
            else: return
        card = DownloadCard(self.scrollable_frame, info, url, format_id, self); self.on_resize(); self.start_download_thread(card)

    def start_download_thread(self, card):
        card.state = "downloading"; card.download_thread = threading.Thread(target=self.download_thread, args=(card,), daemon=True); card.download_thread.start()

    def download_thread(self, card):
        try:
            self.log_queue.put(f"--- Starting/Resuming download for: {card.url} ---\n")
            download_dir = self.download_path_var.get()
            ydl_opts = self._get_ydl_opts()
            ydl_opts.update({'quiet': False, 'progress_hooks': [card.update_progress], 'format': card.format_id, 'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'), 'merge_output_format': 'mp4'})
            with YoutubeDL(ydl_opts) as ydl: ydl.download([card.url])
        except CustomError: self.root.after(0, self.handle_pause, card)
        except Exception as e: self.root.after(0, self.handle_error, card, e)

    def handle_pause(self, card): card.state = "paused"; card.status_label.config(text="Paused"); card.pause_resume_button.config(text="Resume", state="normal"); self.log_queue.put(f"Download paused for {card.url}\n")
    def handle_error(self, card, error): card.state = "error"; card.status_label.config(text="Error!", fg="#ff6b6b"); card.pause_resume_button.config(state="disabled"); self.log_queue.put(f"--- DOWNLOAD FAILED FOR: {card.url} ---\nERROR: {error}\n")
    def on_resize(self, event=None):
        self.root.update_idletasks(); container_width = self.scrollable_frame.winfo_width()
        max_cols = max(1, (container_width - 20) // 420)
        for i, card in enumerate(self.scrollable_frame.winfo_children()): card.grid(row=i // max_cols, column=i % max_cols, padx=10, pady=10, sticky="ew")
        for i in range(max_cols): self.scrollable_frame.grid_columnconfigure(i, weight=1)

if __name__ == "__main__":
    if YoutubeDL is None: print("Error: yt-dlp library is required to run this application.\nPlease install it using: pip install yt-dlp")
    else: root = tk.Tk(); app = App(root); root.mainloop()
