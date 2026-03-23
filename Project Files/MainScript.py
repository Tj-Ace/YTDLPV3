# =========================================================
# AUTO INSTALL REQUIRED PACKAGES
# =========================================================
import subprocess
import sys
import os
import queue
import re
import shutil
import time
import atexit
import json
import tempfile
import zipfile
import urllib.request
import urllib.error

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

try:
    import yt_dlp
except ImportError:
    install("yt-dlp")
    import yt_dlp

try:
    from tkinterdnd2 import DND_TEXT, TkinterDnD
except ImportError:
    install("tkinterdnd2")
    from tkinterdnd2 import DND_TEXT, TkinterDnD

from tkinter import *
from tkinter import filedialog
from tkinter import ttk
import threading
import ctypes
import yt_dlp.downloader.external as yt_dlp_external

APP_USER_MODEL_ID = "yt_dlp.downloader.app"
HTTP_USER_AGENT = "YTDLP-Downloader"
SW_MINIMIZE = 6


# =========================================================
# WINDOWS TASKBAR ICON FIX
# =========================================================
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        APP_USER_MODEL_ID
    )
except:
    pass


def minimize_console_window():
    try:
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window:
            ctypes.windll.user32.ShowWindow(console_window, SW_MINIMIZE)
    except Exception:
        pass


minimize_console_window()


# =========================================================
# WINDOW SETUP
# =========================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "Config.json")
ARIA2C_INSTALL_DIR = os.path.join(SCRIPT_DIR, "aria2c")
ARIA2C_RELEASE_API = "https://api.github.com/repos/aria2/aria2/releases/latest"
ARIA2C_ASSET_SUFFIX = "win-64bit-build1.zip"
STARTUP_MESSAGES = []


def queue_startup_message(message):
    if message:
        STARTUP_MESSAGES.append(message.rstrip() + "\n")


def build_request(url, accept_json=False):
    headers = {"User-Agent": HTTP_USER_AGENT}

    if accept_json:
        headers["Accept"] = "application/vnd.github+json"

    return urllib.request.Request(url, headers=headers)


def normalize_color(value, default):
    candidate = str(value or "").strip()

    if not candidate:
        return default

    if not candidate.startswith("#"):
        candidate = f"#{candidate}"

    if re.fullmatch(r"#[0-9a-fA-F]{6}", candidate):
        return candidate

    return default


def load_app_config():
    default_config = {
        "version": "1.3.0",
        "fullscreen": False,
        "Accent": "#b478fa",
        "Terminal": "#00ff00",
        "default_download_location": "",
        "resolution": {
            "width": 1200,
            "height": 800,
        },
    }

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
            config_data = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return default_config

    resolution = config_data.get("resolution", {})

    return {
        "version": str(config_data.get("version", default_config["version"])).strip() or default_config["version"],
        "fullscreen": bool(config_data.get("fullscreen", False)),
        "Accent": normalize_color(
            config_data.get("Accent"),
            default_config["Accent"],
        ),
        "Terminal": normalize_color(
            config_data.get("Terminal"),
            default_config["Terminal"],
        ),
        "default_download_location": str(
            config_data.get(
                "default_download_location",
                default_config["default_download_location"],
            )
            or ""
        ).strip(),
        "resolution": {
            "width": int(resolution.get("width", default_config["resolution"]["width"])),
            "height": int(resolution.get("height", default_config["resolution"]["height"])),
        },
    }


APP_CONFIG = load_app_config()
APP_VERSION = APP_CONFIG["version"]
ACCENT_COLOR = APP_CONFIG["Accent"]
TERMINAL_COLOR = APP_CONFIG["Terminal"]
DEFAULT_DOWNLOAD_LOCATION = APP_CONFIG["default_download_location"]
WINDOW_WIDTH = APP_CONFIG["resolution"]["width"]
WINDOW_HEIGHT = APP_CONFIG["resolution"]["height"]
WINDOW_FULLSCREEN = APP_CONFIG["fullscreen"]

window = TkinterDnD.Tk()
window.title("YTDLP Downloader")
window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
window.config(bg="#2b2b2b")

if WINDOW_FULLSCREEN:
    window.attributes("-fullscreen", True)

# =========================================================
# LOAD WINDOW ICON
# =========================================================
try:
    icon_path = os.path.join(SCRIPT_DIR, "favi.ico")

    if os.path.exists(icon_path):
        window.iconbitmap(icon_path)
        window.wm_iconbitmap(icon_path)

except Exception as e:
    print("Icon load failed:", e)

download_folder = DEFAULT_DOWNLOAD_LOCATION
LOGS_DIR = os.path.join(SCRIPT_DIR, "Logs")
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE_PATH = os.path.join(LOGS_DIR, time.strftime("%m_%d_%H_%M.log"))
LOG_FILE = open(LOG_FILE_PATH, "a", encoding="utf-8", buffering=1)
LOG_LOCK = threading.Lock()
atexit.register(LOG_FILE.close)
ARIA2C_ARGS = [
    "-x", "16",
    "-s", "16",
    "-k", "1M",
    "--summary-interval=1",
    "--console-log-level=notice",
    "--show-console-readout=true",
    "--enable-color=false",
]


def find_aria2c():
    local_candidates = (
        os.path.join(SCRIPT_DIR, "aria2c.exe"),
        os.path.join(SCRIPT_DIR, "aria2c"),
        os.path.join(ARIA2C_INSTALL_DIR, "aria2c.exe"),
        os.path.join(ARIA2C_INSTALL_DIR, "aria2c"),
    )

    for candidate in local_candidates:
        if os.path.isfile(candidate):
            return candidate

    if os.path.isdir(ARIA2C_INSTALL_DIR):
        for root, _, files in os.walk(ARIA2C_INSTALL_DIR):
            for file_name in files:
                if file_name.lower() == "aria2c.exe":
                    return os.path.join(root, file_name)

    return shutil.which("aria2c")


def fetch_latest_aria2_download():
    request = build_request(ARIA2C_RELEASE_API, accept_json=True)

    with urllib.request.urlopen(request, timeout=15) as response:
        release_data = json.load(response)

    for asset in release_data.get("assets", []):
        asset_name = str(asset.get("name", "")).strip()
        download_url = str(asset.get("browser_download_url", "")).strip()

        if asset_name.endswith(ARIA2C_ASSET_SUFFIX) and download_url:
            return download_url, str(release_data.get("tag_name", asset_name)).strip()

    raise RuntimeError("Official Windows aria2 asset was not found in the latest release.")


def auto_install_aria2c():
    existing_path = find_aria2c()

    if existing_path:
        return (
            existing_path,
            "aria2c detected. Faster multi-connection downloads are enabled by default.",
        )

    temp_dir = tempfile.mkdtemp(prefix="aria2c_")

    try:
        queue_startup_message("aria2c not found. Attempting automatic install...")
        download_url, release_tag = fetch_latest_aria2_download()
        archive_name = os.path.basename(download_url.split("?", 1)[0]) or "aria2c.zip"
        archive_path = os.path.join(temp_dir, archive_name)
        download_request = build_request(download_url)

        with urllib.request.urlopen(download_request, timeout=30) as response, open(archive_path, "wb") as archive_file:
            shutil.copyfileobj(response, archive_file)

        os.makedirs(ARIA2C_INSTALL_DIR, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(ARIA2C_INSTALL_DIR)

        installed_path = find_aria2c()

        if installed_path:
            queue_startup_message(f"aria2c auto-installed successfully from {release_tag}.")
            return (
                installed_path,
                "aria2c auto-installed. Faster multi-connection downloads are enabled by default.",
            )

        raise RuntimeError("Download finished, but aria2c.exe was not found after extraction.")
    except (OSError, urllib.error.URLError, zipfile.BadZipFile, RuntimeError, json.JSONDecodeError) as exc:
        queue_startup_message(f"aria2c auto-install failed: {exc}")
        return (
            None,
            "aria2c auto-install failed. The app will continue without acceleration.",
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


ARIA2C_PATH, ARIA2C_STATUS_TEXT = auto_install_aria2c()
UI_QUEUE = queue.Queue()
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
elapsed_started_at = None
elapsed_timer_job = None


# =========================================================
# TERMINAL REDIRECT
# =========================================================
class TerminalRedirect:
    def write(self, text):
        append_terminal(text)
    def flush(self):
        pass


def run_on_ui(callback, *args, **kwargs):
    UI_QUEUE.put((callback, args, kwargs))


def process_ui_queue():
    try:
        while True:
            callback, args, kwargs = UI_QUEUE.get_nowait()
            callback(*args, **kwargs)
    except queue.Empty:
        pass

    window.after(50, process_ui_queue)


def append_terminal(text):
    if not text:
        return

    write_log(text)
    run_on_ui(_append_terminal, text)


def _append_terminal(text):
    terminal.insert(END, text)
    terminal.see(END)


def write_log(text):
    if not text:
        return

    with LOG_LOCK:
        LOG_FILE.write(text)
        LOG_FILE.flush()


def set_download_stats(percent=None, speed=None, eta=None):
    run_on_ui(_set_download_stats, percent, speed, eta)


def _set_download_stats(percent=None, speed=None, eta=None):
    if percent is not None:
        clamped_percent = max(0, min(100, float(percent)))
        progress_var.set(clamped_percent)
        progress_text.set(f"{clamped_percent:.0f}%")

    if speed is not None:
        speed_var.set(speed)

    if eta is not None:
        eta_var.set(eta)


def reset_download_stats():
    set_download_stats(percent=0, speed="-", eta="-")
    run_on_ui(elapsed_var.set, "-")


def format_eta(seconds):
    try:
        total_seconds = max(0, int(seconds))
    except (TypeError, ValueError):
        return "-"

    minutes, remaining_seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {minutes}m {remaining_seconds}s"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def start_elapsed_timer():
    run_on_ui(_start_elapsed_timer)


def _start_elapsed_timer():
    global elapsed_started_at
    global elapsed_timer_job

    elapsed_started_at = time.monotonic()
    elapsed_var.set("0s")

    if elapsed_timer_job is not None:
        window.after_cancel(elapsed_timer_job)
        elapsed_timer_job = None

    _tick_elapsed_timer()


def _tick_elapsed_timer():
    global elapsed_timer_job

    if elapsed_started_at is None:
        elapsed_timer_job = None
        return

    elapsed_seconds = int(time.monotonic() - elapsed_started_at)
    elapsed_var.set(format_eta(elapsed_seconds))
    elapsed_timer_job = window.after(1000, _tick_elapsed_timer)


def stop_elapsed_timer():
    run_on_ui(_stop_elapsed_timer)


def _stop_elapsed_timer():
    global elapsed_started_at
    global elapsed_timer_job

    if elapsed_started_at is not None:
        elapsed_seconds = int(time.monotonic() - elapsed_started_at)
        elapsed_var.set(format_eta(elapsed_seconds))

    elapsed_started_at = None

    if elapsed_timer_job is not None:
        window.after_cancel(elapsed_timer_job)
        elapsed_timer_job = None


def clear_download_location():
    global download_folder
    download_folder = DEFAULT_DOWNLOAD_LOCATION
    run_on_ui(location_var.set, DEFAULT_DOWNLOAD_LOCATION)


def save_app_config():
    config_to_save = {
        "version": APP_VERSION,
        "fullscreen": WINDOW_FULLSCREEN,
        "Accent": ACCENT_COLOR,
        "Terminal": TERMINAL_COLOR,
        "default_download_location": DEFAULT_DOWNLOAD_LOCATION,
        "resolution": {
            "width": WINDOW_WIDTH,
            "height": WINDOW_HEIGHT,
        },
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
        json.dump(config_to_save, config_file, indent=4)


def set_default_download_location():
    global DEFAULT_DOWNLOAD_LOCATION
    global download_folder

    folder = location_var.get().strip()

    if not folder:
        folder = filedialog.askdirectory()

        if not folder:
            return

        location_var.set(folder)

    DEFAULT_DOWNLOAD_LOCATION = folder
    download_folder = folder
    save_app_config()
    append_terminal(f"Default download location saved: {folder}\n")


def is_aria2_command(args):
    if isinstance(args, (list, tuple)):
        executable = str(args[0]) if args else ""
    else:
        command = str(args or "").strip()
        executable = command.split()[0] if command else ""

    executable = executable.strip().strip('"')
    return os.path.basename(executable).lower() in ("aria2c", "aria2c.exe")


def normalize_aria2_line(text):
    return ANSI_ESCAPE_RE.sub("", text).replace("\r", "").strip()


def update_stats_from_aria2_output(text):
    percent_match = re.search(r"\((\d{1,3})%\)", text)
    speed_match = re.search(r"\bDL:([^\s]+)", text)
    eta_match = re.search(r"\bETA:([^\s]+)", text)

    if not any((percent_match, speed_match, eta_match)):
        return

    percent = float(percent_match.group(1)) if percent_match else None
    speed = speed_match.group(1) if speed_match else None
    eta = eta_match.group(1) if eta_match else None

    if speed and not speed.endswith("/s"):
        speed = f"{speed}/s"

    set_download_stats(percent=percent, speed=speed, eta=eta)


def handle_aria2_output_line(text):
    cleaned = normalize_aria2_line(text)

    if not cleaned:
        return

    append_terminal(cleaned + "\n")
    update_stats_from_aria2_output(cleaned)


def stream_aria2_output(stream):
    buffer = []

    while True:
        chunk = stream.read(1)

        if chunk == "":
            break

        if chunk in ("\r", "\n"):
            if buffer:
                handle_aria2_output_line("".join(buffer))
                buffer.clear()
            continue

        buffer.append(chunk)

    if buffer:
        handle_aria2_output_line("".join(buffer))


class UIPopen(yt_dlp_external.Popen):
    def __init__(self, args, *remaining, **kwargs):
        self._capture_aria2 = is_aria2_command(args)
        self._aria2_output_thread = None

        if self._capture_aria2:
            kwargs = kwargs.copy()
            kwargs.setdefault("stdout", subprocess.PIPE)

        super().__init__(args, *remaining, **kwargs)

        if self._capture_aria2 and self.stdout is not None:
            self._aria2_output_thread = threading.Thread(
                target=stream_aria2_output,
                args=(self.stdout,),
                daemon=True,
            )
            self._aria2_output_thread.start()

    def communicate(self, input=None, timeout=None):
        if not self._capture_aria2:
            return super().communicate(input=input, timeout=timeout)

        stderr_data = None

        try:
            if input is not None:
                if self.stdin is None:
                    raise ValueError("stdin was not opened as a pipe")
                self.stdin.write(input)
                self.stdin.flush()
                self.stdin.close()

            self.wait(timeout=timeout)

            if self.stderr is not None:
                stderr_data = self.stderr.read()
        except BaseException:
            self.kill()
            raise
        finally:
            self._join_aria2_output()

        return "", stderr_data

    def _join_aria2_output(self):
        if self._aria2_output_thread and self._aria2_output_thread.is_alive():
            self._aria2_output_thread.join(timeout=1)


yt_dlp_external.Popen = UIPopen


class YTDLPLogger:
    def _write(self, prefix, message):
        if message:
            append_terminal(f"{prefix}{message}\n")

    def debug(self, message):
        self._write("", message)

    def info(self, message):
        self._write("", message)

    def warning(self, message):
        self._write("WARNING: ", message)

    def error(self, message):
        self._write("ERROR: ", message)


# =========================================================
# DOWNLOAD PROGRESS HOOK
# =========================================================
def progress_hook(d):

    if d["status"] == "downloading":
        percent = None

        if d.get("total_bytes"):
            percent = d["downloaded_bytes"] / d["total_bytes"] * 100
        elif d.get("total_bytes_estimate"):
            percent = d["downloaded_bytes"] / d["total_bytes_estimate"] * 100
        elif d.get("_percent_str"):
            percent_match = re.search(r"(\d+(?:\.\d+)?)%", d["_percent_str"])
            if percent_match:
                percent = float(percent_match.group(1))

        speed = d.get("speed")
        if speed:
            speed = f"{speed/1024/1024:.2f} MB/s"
        else:
            speed = d.get("_speed_str")
            if speed:
                speed = speed.strip()

        eta = d.get("eta")
        if eta is not None:
            eta = format_eta(eta)
        else:
            eta = d.get("_eta_str")
            if eta:
                eta = eta.strip()

        set_download_stats(percent=percent, speed=speed, eta=eta)

    if d["status"] == "finished":
        set_download_stats(percent=100, eta="0s")


def get_format_choice():

    quality = quality_var.get()
    quality_map = {
        "Max": "bv*+ba/b",
        "1080p": "bestvideo[height<=1080]+bestaudio/best",
        "720p": "bestvideo[height<=720]+bestaudio/best",
        "480p": "bestvideo[height<=480]+bestaudio/best",
    }

    if audio_only_var.get():
        return "bestaudio/best"

    return quality_map.get(quality, "bestvideo+bestaudio/best")


# =========================================================
# DRAG & DROP URL
# =========================================================
def drop_url(event):
    url_box.delete("1.0", END)
    url_box.insert(END, event.data.strip())


# =========================================================
# SELECT DOWNLOAD FOLDER
# =========================================================
def browse_folder():
    global download_folder
    folder = filedialog.askdirectory()
    if folder:
        download_folder = folder
        location_var.set(folder)


# =========================================================
# MAIN DOWNLOAD FUNCTION
# =========================================================
def run_command():

    url = url_box.get("1.0","end-1c").strip()

    if not url:
        return

    format_choice = get_format_choice()
    target_folder = location_var.get().strip()

    if not target_folder:
        append_terminal("Error: Select a download location before downloading.\n")
        return

    use_aria2 = bool(use_aria2_var.get() and ARIA2C_PATH)
    download_thumbnail = thumbnail_var.get()
    audio_only = audio_only_var.get()

    def task():

        reset_download_stats()
        start_elapsed_timer()
        append_terminal("Starting download...\n")

        ydl_opts = {
            "format": format_choice,
            "merge_output_format": "mp4",
            "noplaylist": False,
            "retries": 10,
            "fragment_retries": 10,
            "ignoreerrors": True,
            "extract_flat": False,
            "progress_hooks": [progress_hook],
            "logger": YTDLPLogger(),
            "outtmpl": os.path.join(target_folder, "%(title)s.%(ext)s"),
        }

        if use_aria2:
            ydl_opts["external_downloader"] = {
                "default": ARIA2C_PATH,
            }
            ydl_opts["external_downloader_args"] = {
                "default": ARIA2C_ARGS,
            }
            append_terminal(
                f"aria2c acceleration enabled ({' '.join(ARIA2C_ARGS)})\n"
            )

        if download_thumbnail:
            ydl_opts["writethumbnail"] = True
            ydl_opts.setdefault("postprocessors", []).append({
                "key": "FFmpegThumbnailsConvertor",
                "format": "png"
            })

        if audio_only:
            ydl_opts.setdefault("postprocessors", []).append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })

        try:

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                info = ydl.extract_info(url, download=False)

                if 'entries' in info:

                    entries = [e for e in info['entries'] if e]
                    total = len(entries)

                    run_on_ui(playlist_var.set, f"0 / {total}")

                    for i, entry in enumerate(entries, start=1):

                        run_on_ui(playlist_var.set, f"{i} / {total}")

                        ydl.download([entry['webpage_url']])

                else:

                    run_on_ui(playlist_var.set, "1 / 1")

                    ydl.download([url])

            append_terminal("\nDownload complete\n")

        except Exception as e:

            append_terminal(f"\nError: {e}\n")
        finally:
            stop_elapsed_timer()
            clear_download_location()

    threading.Thread(target=task,daemon=True).start()


# =========================================================
# UI PANELS
# =========================================================
left_frame = Frame(window,bg="#2b2b2b")
left_frame.pack(side=LEFT,fill=BOTH,expand=True)

right_frame = Frame(
    window,
    bg="#2b2b2b",
    width=420,
    highlightthickness=1,
    highlightbackground="#444",
)
right_frame.pack(side=RIGHT,fill=BOTH)
right_frame.pack_propagate(False)


# =========================================================
# URL INPUT
# =========================================================
Label(left_frame,text="YouTube URL / Playlist / Channel:",
bg="#2b2b2b",fg=ACCENT_COLOR,font=("Consolas",12)).pack(anchor="nw",padx=10,pady=(10,0))

url_box = Text(left_frame,height=3,bg="#1e1e1e",fg=ACCENT_COLOR,
insertbackground=ACCENT_COLOR,font=("Consolas",11))
url_box.pack(fill=X,padx=10,pady=5)

url_box.drop_target_register(DND_TEXT)
url_box.dnd_bind('<<Drop>>', drop_url)


# =========================================================
# BUTTON ROW
# =========================================================
control_frame = Frame(left_frame,bg="#2b2b2b")
control_frame.pack(fill=X,padx=10,pady=10)

Button(control_frame,text="Download",command=run_command,
bg="#444",fg=ACCENT_COLOR,font=("Consolas",12)).pack(side=LEFT)

Button(control_frame,text="Location",command=browse_folder,
bg="#444",fg=ACCENT_COLOR,font=("Consolas",12)).pack(side=LEFT,padx=10)

Button(control_frame,text="Set Default",command=set_default_download_location,
bg="#444",fg=ACCENT_COLOR,font=("Consolas",12)).pack(side=LEFT,padx=(0,10))

location_var = StringVar(value=DEFAULT_DOWNLOAD_LOCATION)

Entry(control_frame,textvariable=location_var,
bg="#1e1e1e",fg=ACCENT_COLOR,insertbackground=ACCENT_COLOR,
font=("Consolas",12),relief=FLAT).pack(side=LEFT,fill=X,expand=True)


# =========================================================
# QUALITY
# =========================================================
quality_frame = Frame(left_frame,bg="#2b2b2b")
quality_frame.pack(anchor="nw",padx=10,pady=(0,10),fill=X)

Label(quality_frame,text="Video Quality:",
bg="#2b2b2b",fg=ACCENT_COLOR,font=("Consolas",11)).pack(anchor="w")

row = Frame(quality_frame,bg="#2b2b2b")
row.pack(fill=X)

quality_var = StringVar(value="Max")

style = ttk.Style()
style.theme_use('default')

style.configure("Dark.TCombobox",
fieldbackground="#1e1e1e",
background="#1e1e1e",
foreground=ACCENT_COLOR)

quality_dropdown = ttk.Combobox(
row,
textvariable=quality_var,
values=["480p","720p","1080p","Max"],
state="readonly",
font=("Consolas",11),
width=10,
style="Dark.TCombobox"
)

quality_dropdown.pack(side=LEFT)


# =========================================================
# OPTIONS
# =========================================================
options_frame = Frame(left_frame,bg="#2b2b2b")
options_frame.pack(anchor="nw",padx=10,pady=10)

thumbnail_var = BooleanVar()
audio_only_var = BooleanVar()
use_aria2_var = BooleanVar(value=bool(ARIA2C_PATH))

Checkbutton(options_frame,text="Download thumbnails",
variable=thumbnail_var,bg="#2b2b2b",fg=ACCENT_COLOR,
selectcolor="#1e1e1e",font=("Consolas",11)).pack(anchor="w")

Checkbutton(options_frame,text="Download audio only",
variable=audio_only_var,bg="#2b2b2b",fg=ACCENT_COLOR,
selectcolor="#1e1e1e",font=("Consolas",11)).pack(anchor="w")

Checkbutton(options_frame,text="Use aria2c acceleration",
variable=use_aria2_var,bg="#2b2b2b",fg=ACCENT_COLOR,
selectcolor="#1e1e1e",font=("Consolas",11),
state=NORMAL if ARIA2C_PATH else DISABLED).pack(anchor="w")

aria2_status_var = StringVar(value=ARIA2C_STATUS_TEXT)

Label(
    options_frame,
    textvariable=aria2_status_var,
    bg="#2b2b2b",
    fg="#888",
    font=("Consolas",10),
    justify=LEFT,
    wraplength=520,
).pack(anchor="w",pady=(2,0))


# =========================================================
# BOTTOM INFO PANEL
# =========================================================
bottom_frame = Frame(left_frame,bg="#2b2b2b")
bottom_frame.pack(side=BOTTOM,fill=X,padx=10,pady=10)

playlist_var = StringVar(value="0 / 0")

Label(bottom_frame,text="Playlist Progress:",
bg="#2b2b2b",fg=ACCENT_COLOR,font=("Consolas",11)).pack(anchor="w")

Label(bottom_frame,textvariable=playlist_var,
bg="#2b2b2b",fg=ACCENT_COLOR,font=("Consolas",11)).pack(anchor="w")

stats_frame = Frame(bottom_frame,bg="#2b2b2b")
stats_frame.pack(fill=X)

left_stats_frame = Frame(stats_frame,bg="#2b2b2b")
left_stats_frame.pack(side=LEFT)

speed_var = StringVar(value="-")
eta_var = StringVar(value="-")
elapsed_var = StringVar(value="-")

Label(left_stats_frame,text="Speed:",bg="#2b2b2b",
fg=ACCENT_COLOR,font=("Consolas",10)).pack(side=LEFT)

Label(left_stats_frame,textvariable=speed_var,bg="#2b2b2b",
fg=ACCENT_COLOR,font=("Consolas",10)).pack(side=LEFT,padx=(5,20))

Label(left_stats_frame,text="ETA:",bg="#2b2b2b",
fg=ACCENT_COLOR,font=("Consolas",10)).pack(side=LEFT)

Label(left_stats_frame,textvariable=eta_var,bg="#2b2b2b",
fg=ACCENT_COLOR,font=("Consolas",10)).pack(side=LEFT,padx=5)

progress_var = DoubleVar()
progress_text = StringVar(value="0%")

Label(bottom_frame,text="Progress...",
bg="#2b2b2b",fg=ACCENT_COLOR,font=("Consolas",11)).pack(anchor="w")

progress_row = Frame(bottom_frame,bg="#2b2b2b")
progress_row.pack(fill=X)

Label(progress_row,textvariable=progress_text,
bg="#2b2b2b",fg=ACCENT_COLOR,font=("Consolas",11)).pack(side=LEFT)

progress_meta_frame = Frame(progress_row,bg="#2b2b2b")
progress_meta_frame.pack(side=RIGHT)

Label(progress_meta_frame,text="Elapsed:",bg="#2b2b2b",
fg=ACCENT_COLOR,font=("Consolas",10)).pack(side=LEFT,padx=(0,5))

Label(progress_meta_frame,textvariable=elapsed_var,bg="#2b2b2b",
fg=ACCENT_COLOR,font=("Consolas",10)).pack(side=LEFT,padx=(0,20))

Label(progress_meta_frame,text="Version:",bg="#2b2b2b",
fg=ACCENT_COLOR,font=("Consolas",10)).pack(side=LEFT,padx=(0,5))

Label(progress_meta_frame,text=APP_VERSION,bg="#2b2b2b",
fg=ACCENT_COLOR,font=("Consolas",10)).pack(side=LEFT)

style.configure(
"purple.Horizontal.TProgressbar",
troughcolor="#1e1e1e",
background=ACCENT_COLOR,
thickness=20
)

progress_bar = ttk.Progressbar(bottom_frame,
variable=progress_var,
maximum=100,
style="purple.Horizontal.TProgressbar")

progress_bar.pack(fill=X,pady=10)


# =========================================================
# TERMINAL PANEL
# =========================================================
Label(right_frame,text="Terminal Output:",
bg="#2b2b2b",fg=ACCENT_COLOR,font=("Consolas",12)).pack(anchor="nw",padx=10,pady=(10,0))

terminal = Text(
    right_frame,
    bg="black",
    fg=TERMINAL_COLOR,
    insertbackground=TERMINAL_COLOR,
    font=("Consolas",10),
    width=48,
)

terminal.pack(fill=BOTH,expand=True,padx=10,pady=10)

process_ui_queue()

for startup_message in STARTUP_MESSAGES:
    append_terminal(startup_message)

append_terminal("Terminal ready...\n")

sys.stdout = TerminalRedirect()
sys.stderr = TerminalRedirect()


# =========================================================
# AUTO UPDATE
# =========================================================
window.mainloop()
