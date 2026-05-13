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
import urllib.parse
import importlib.util

def install(package):
    """Install a missing Python dependency into the active interpreter."""
    subprocess.check_call([sys.executable, "-m", "pip", "--disable-pip-version-check", "install", package])

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
GENERIC_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)
YOUTUBE_HOST_MARKERS = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "googlevideo.com",
)
SPOTIFY_HOST_MARKERS = (
    "open.spotify.com",
    "spotify.link",
)
GENERIC_SITE_FALLBACK_FORMAT = "best/b"
QUALITY_MAP = {
    "Max": "bv*+ba/b",
    "1080p": "bestvideo[height<=1080]+bestaudio/best",
    "720p": "bestvideo[height<=720]+bestaudio/best",
    "480p": "bestvideo[height<=480]+bestaudio/best",
}
AUDIO_FILE_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".opus", ".aac", ".ogg"}
IMAGE_FILE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".avif",
    ".bmp",
    ".gif",
    ".jfif",
    ".tif",
    ".tiff",
}
SW_MINIMIZE = 6
WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
UI_QUEUE_INTERVAL_MS = 50
ELAPSED_TIMER_INTERVAL_MS = 1000


# =========================================================
# WINDOWS TASKBAR ICON FIX
# =========================================================
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        APP_USER_MODEL_ID
    )
except Exception:
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
DEFAULTS_PATH = os.path.join(SCRIPT_DIR, "Defaults.json")
ARIA2C_INSTALL_DIR = os.path.join(SCRIPT_DIR, "aria2c")
ARIA2C_RELEASE_API = "https://api.github.com/repos/aria2/aria2/releases/latest"
ARIA2C_ASSET_SUFFIX = "win-64bit-build1.zip"
FFMPEG_INSTALL_DIR = os.path.join(SCRIPT_DIR, "ffmpeg")
FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
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


def normalize_layout(value, default="1"):
    candidate = str(value or "").strip()

    if candidate in ("1", "2"):
        return candidate

    return default


def normalize_quality(value, default="Max"):
    candidate = str(value or "").strip()

    if candidate in QUALITY_MAP:
        return candidate

    return default


def normalize_bool(value, default=False):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        candidate = value.strip().lower()

        if candidate in ("1", "true", "yes", "on", "enabled"):
            return True

        if candidate in ("0", "false", "no", "off", "disabled"):
            return False

    return default


def normalize_resolution(resolution, default_width, default_height):
    try:
        width = int(resolution.get("width", default_width))
    except Exception:
        width = default_width

    try:
        height = int(resolution.get("height", default_height))
    except Exception:
        height = default_height

    return {
        "width": max(900, width),
        "height": max(620, height),
    }


def load_default_config_template():
    fallback = {
        "version": "3.0.0",
        "layout": "1",
        "enable_layout_switch_easter_egg": False,
        "quality": "Max",
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
        with open(DEFAULTS_PATH, "r", encoding="utf-8") as defaults_file:
            loaded = json.load(defaults_file)
    except (OSError, json.JSONDecodeError):
        loaded = fallback

    if not isinstance(loaded, dict):
        loaded = fallback

    return {
        "version": str(loaded.get("version", fallback["version"])).strip() or fallback["version"],
        "layout": normalize_layout(loaded.get("layout"), fallback["layout"]),
        "enable_layout_switch_easter_egg": normalize_bool(
            loaded.get("enable_layout_switch_easter_egg"),
            fallback["enable_layout_switch_easter_egg"],
        ),
        "quality": normalize_quality(loaded.get("quality"), fallback["quality"]),
        "fullscreen": normalize_bool(loaded.get("fullscreen"), fallback["fullscreen"]),
        "Accent": normalize_color(loaded.get("Accent"), fallback["Accent"]),
        "Terminal": normalize_color(loaded.get("Terminal"), fallback["Terminal"]),
        "default_download_location": str(
            loaded.get("default_download_location", fallback["default_download_location"])
        ).strip(),
        "resolution": normalize_resolution(
            loaded.get("resolution", {}),
            fallback["resolution"]["width"],
            fallback["resolution"]["height"],
        ),
    }


def load_app_config():
    """Load persisted settings and fall back to sane defaults on bad config."""
    default_config = load_default_config_template()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
            config_data = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return default_config

    return {
        "version": str(config_data.get("version", default_config["version"])).strip() or default_config["version"],
        "layout": normalize_layout(
            config_data.get("layout"),
            default_config["layout"],
        ),
        "enable_layout_switch_easter_egg": normalize_bool(
            config_data.get("enable_layout_switch_easter_egg"),
            default_config["enable_layout_switch_easter_egg"],
        ),
        "quality": normalize_quality(
            config_data.get("quality"),
            default_config["quality"],
        ),
        "fullscreen": normalize_bool(config_data.get("fullscreen"), default_config["fullscreen"]),
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
        "resolution": normalize_resolution(
            config_data.get("resolution", {}),
            default_config["resolution"]["width"],
            default_config["resolution"]["height"],
        ),
    }


APP_CONFIG = load_app_config()
APP_VERSION = APP_CONFIG["version"]
APP_LAYOUT = APP_CONFIG["layout"]
EASTER_EGG_ENABLED = APP_CONFIG["enable_layout_switch_easter_egg"]
DEFAULT_QUALITY = APP_CONFIG["quality"]
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
ICON_HANDLES = []


def apply_window_icon(icon_path):
    """Apply icon both through Tk and Win32 to improve taskbar consistency."""
    if not os.path.isfile(icon_path):
        return

    try:
        window.iconbitmap(icon_path)
        window.wm_iconbitmap(icon_path)
    except Exception:
        pass

    # On some Windows setups, explicitly sending both icon sizes to the HWND
    # makes the taskbar icon update reliably.
    try:
        hwnd = window.winfo_id()
        load_image = ctypes.windll.user32.LoadImageW
        send_message = ctypes.windll.user32.SendMessageW
        handle_small = load_image(
            0,
            icon_path,
            IMAGE_ICON,
            16,
            16,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
        handle_big = load_image(
            0,
            icon_path,
            IMAGE_ICON,
            32,
            32,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )

        if handle_small:
            send_message(hwnd, WM_SETICON, ICON_SMALL, handle_small)
            ICON_HANDLES.append(handle_small)

        if handle_big:
            send_message(hwnd, WM_SETICON, ICON_BIG, handle_big)
            ICON_HANDLES.append(handle_big)
    except Exception:
        pass


try:
    apply_window_icon(os.path.join(SCRIPT_DIR, "favi.ico"))
except Exception as e:
    print("Icon load failed:", e)

download_folder = DEFAULT_DOWNLOAD_LOCATION
url_box = None
terminal = None
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


def ensure_path_contains(directory):
    if not directory:
        return

    normalized_target = os.path.normcase(os.path.abspath(directory))
    path_value = os.environ.get("PATH", "")
    existing = [segment for segment in path_value.split(os.pathsep) if segment]

    for segment in existing:
        if os.path.normcase(os.path.abspath(segment)) == normalized_target:
            return

    os.environ["PATH"] = (
        f"{directory}{os.pathsep}{path_value}" if path_value else directory
    )


def find_ffmpeg():
    local_candidates = (
        os.path.join(SCRIPT_DIR, "ffmpeg.exe"),
        os.path.join(FFMPEG_INSTALL_DIR, "ffmpeg.exe"),
        os.path.join(FFMPEG_INSTALL_DIR, "bin", "ffmpeg.exe"),
    )

    for candidate in local_candidates:
        if os.path.isfile(candidate):
            return candidate

    if os.path.isdir(FFMPEG_INSTALL_DIR):
        for root, _, files in os.walk(FFMPEG_INSTALL_DIR):
            for file_name in files:
                if file_name.lower() == "ffmpeg.exe":
                    return os.path.join(root, file_name)

    return shutil.which("ffmpeg")


def auto_install_ffmpeg():
    existing_path = find_ffmpeg()

    if existing_path:
        return (
            existing_path,
            "ffmpeg detected. Thumbnail conversion and media processing are enabled.",
        )

    temp_dir = tempfile.mkdtemp(prefix="ffmpeg_")

    try:
        queue_startup_message("ffmpeg not found. Attempting automatic install...")
        archive_path = os.path.join(temp_dir, "ffmpeg-release-essentials.zip")
        download_request = build_request(FFMPEG_DOWNLOAD_URL)

        with urllib.request.urlopen(download_request, timeout=30) as response, open(archive_path, "wb") as archive_file:
            shutil.copyfileobj(response, archive_file)

        os.makedirs(FFMPEG_INSTALL_DIR, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(FFMPEG_INSTALL_DIR)

        installed_path = find_ffmpeg()

        if installed_path:
            queue_startup_message("ffmpeg auto-installed successfully.")
            return (
                installed_path,
                "ffmpeg auto-installed. Thumbnail conversion and media processing are enabled.",
            )

        raise RuntimeError("Download finished, but ffmpeg.exe was not found after extraction.")
    except (OSError, urllib.error.URLError, zipfile.BadZipFile, RuntimeError) as exc:
        queue_startup_message(f"ffmpeg auto-install failed: {exc}")
        return (
            None,
            "ffmpeg auto-install failed. Some conversion features may be unavailable.",
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def ensure_ffmpeg_available():
    global FFMPEG_PATH

    ffmpeg_path = FFMPEG_PATH or find_ffmpeg()

    if not ffmpeg_path:
        ffmpeg_path, ffmpeg_status = auto_install_ffmpeg()
        ffmpeg_status_var.set(ffmpeg_status)

    if ffmpeg_path:
        FFMPEG_PATH = ffmpeg_path
        ensure_path_contains(os.path.dirname(ffmpeg_path))
        return ffmpeg_path

    return None


ARIA2C_PATH = find_aria2c()
if ARIA2C_PATH:
    ARIA2C_STATUS_TEXT = "aria2c detected. Faster multi-connection downloads are enabled by default."
else:
    ARIA2C_STATUS_TEXT = "aria2c missing. Auto-install will run in background."

FFMPEG_PATH = find_ffmpeg()
if FFMPEG_PATH:
    FFMPEG_STATUS_TEXT = "ffmpeg detected. Thumbnail conversion and media processing are enabled."
else:
    FFMPEG_STATUS_TEXT = "ffmpeg missing. Auto-install will run in background."

if FFMPEG_PATH:
    ensure_path_contains(os.path.dirname(FFMPEG_PATH))

UI_QUEUE = queue.Queue()
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
elapsed_started_at = None
elapsed_timer_job = None
location_var = StringVar(value=DEFAULT_DOWNLOAD_LOCATION)
quality_var = StringVar(value=DEFAULT_QUALITY)
thumbnail_var = BooleanVar()
audio_only_var = BooleanVar()
use_aria2_var = BooleanVar(value=bool(ARIA2C_PATH))
audio_mp4_var = BooleanVar()
aria2_status_var = StringVar(value=ARIA2C_STATUS_TEXT)
ffmpeg_status_var = StringVar(value=FFMPEG_STATUS_TEXT)
playlist_var = StringVar(value="0 / 0")
speed_var = StringVar(value="-")
eta_var = StringVar(value="-")
elapsed_var = StringVar(value="-")
progress_var = DoubleVar()
progress_text = StringVar(value="0%")


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

    window.after(UI_QUEUE_INTERVAL_MS, process_ui_queue)


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


DEPENDENCY_SETUP_STARTED = False


def start_optional_dependency_setup():
    global DEPENDENCY_SETUP_STARTED

    if DEPENDENCY_SETUP_STARTED:
        return

    DEPENDENCY_SETUP_STARTED = True

    def worker():
        global ARIA2C_PATH
        global FFMPEG_PATH

        append_terminal("Checking optional dependencies in background...\n")

        if not ARIA2C_PATH:
            aria2_path, aria2_status = auto_install_aria2c()
            if aria2_path:
                ARIA2C_PATH = aria2_path
            run_on_ui(aria2_status_var.set, aria2_status)
            if aria2_path:
                run_on_ui(use_aria2_var.set, True)

        if not FFMPEG_PATH:
            ffmpeg_path, ffmpeg_status = auto_install_ffmpeg()
            if ffmpeg_path:
                FFMPEG_PATH = ffmpeg_path
                ensure_path_contains(os.path.dirname(ffmpeg_path))
            run_on_ui(ffmpeg_status_var.set, ffmpeg_status)

        append_terminal("Optional dependency setup check complete.\n")

    threading.Thread(
        target=worker,
        daemon=True,
        name="startup-dependency-worker",
    ).start()


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
    elapsed_timer_job = window.after(ELAPSED_TIMER_INTERVAL_MS, _tick_elapsed_timer)


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
        "layout": APP_LAYOUT,
        "enable_layout_switch_easter_egg": EASTER_EGG_ENABLED,
        "quality": normalize_quality(quality_var.get()),
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


def restart_application():
    script_path = os.path.abspath(__file__)
    python_executable = sys.executable or "python"

    try:
        subprocess.Popen(
            [python_executable, script_path],
            cwd=SCRIPT_DIR,
            close_fds=True,
        )
        window.destroy()
    except OSError as exc:
        append_terminal(f"Error: Restart failed: {exc}\n")


def start_launcher():
    launcher_script_path = os.path.join(SCRIPT_DIR, "Desktop.py")

    if not os.path.isfile(launcher_script_path):
        append_terminal(f"Error: Desktop.py not found: {launcher_script_path}\n")
        return

    python_executable = sys.executable or "python"
    launcher_log_path = os.path.join(
        LOGS_DIR,
        time.strftime("LauncherBootstrap_%m_%d_%H_%M.log"),
    )

    launcher_log_file = None

    try:
        launcher_log_file = open(launcher_log_path, "a", encoding="utf-8", buffering=1)
        subprocess.Popen(
            [python_executable, launcher_script_path],
            cwd=SCRIPT_DIR,
            close_fds=True,
            stdout=launcher_log_file,
            stderr=launcher_log_file,
        )
        append_terminal("Launcher Started.\n")
        append_terminal(f"Launcher bootstrap log: {launcher_log_path}\n")
    except OSError as exc:
        append_terminal(f"Error: Failed To Start Launcher: {exc}\n")
    finally:
        if launcher_log_file:
            launcher_log_file.close()


def save_quality_preference():
    save_app_config()


def toggle_layout_and_restart():
    global APP_LAYOUT

    APP_LAYOUT = "1" if APP_LAYOUT == "2" else "2"
    save_app_config()
    append_terminal(f"Switched To Layout {APP_LAYOUT}. Restarting...\n")
    window.after(100, restart_application)


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


def bind_layout_toggle_easter_egg(widget):
    if EASTER_EGG_ENABLED:
        widget.bind("<Double-Button-1>", lambda _event: toggle_layout_and_restart())


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


def clean_status_token(value):
    token = str(value or "").strip()
    return token.strip("[]")


def update_stats_from_aria2_output(text):
    percent_match = re.search(r"\((\d{1,3})%\)", text)
    speed_match = re.search(r"\bDL:([^\s]+)", text)
    eta_match = re.search(r"\bETA:([^\s]+)", text)

    if not any((percent_match, speed_match, eta_match)):
        return

    percent = float(percent_match.group(1)) if percent_match else None
    speed = clean_status_token(speed_match.group(1)) if speed_match else None
    eta = clean_status_token(eta_match.group(1)) if eta_match else None

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
    """Capture aria2 stdout so progress can be shown inside the app terminal."""
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


def is_aria2_failure_message(message):
    normalized = str(message or "").lower()

    return (
        "aria2c exited with code" in normalized
        or ("aria2" in normalized and "errorcode=22" in normalized)
        or ("aria2" in normalized and "status=403" in normalized)
    )


def get_url_host(url):
    parsed = urllib.parse.urlparse(str(url or "").strip())
    return parsed.netloc.lower()


def is_youtube_like_url(url):
    host = get_url_host(url)
    return any(marker in host for marker in YOUTUBE_HOST_MARKERS)


def is_spotify_url(url):
    host = get_url_host(url)
    return any(marker in host for marker in SPOTIFY_HOST_MARKERS)


def build_generic_site_headers(url):
    headers = {
        "User-Agent": GENERIC_BROWSER_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
    }
    parsed = urllib.parse.urlparse(str(url or "").strip())

    if parsed.scheme and parsed.netloc:
        headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

    return headers


class YTDLPLogger:
    def __init__(self):
        self.aria2_failed = False

    def _track_message(self, message):
        text = str(message or "")

        if text and is_aria2_failure_message(text):
            self.aria2_failed = True

        return text

    def _write(self, prefix, message):
        text = self._track_message(message)

        if text:
            append_terminal(f"{prefix}{text}\n")

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
                speed = clean_status_token(speed)

        eta = d.get("eta")
        if eta is not None:
            eta = format_eta(eta)
        else:
            eta = d.get("_eta_str")
            if eta:
                eta = clean_status_token(eta)

        set_download_stats(percent=percent, speed=speed, eta=eta)

    if d["status"] == "finished":
        set_download_stats(percent=100, eta="0s")


def build_ydl_options(
    format_choice,
    target_folder,
    download_thumbnail,
    audio_only,
    audio_to_video_mp4=False,
    thumbnail_only=False,
    use_aria2=False,
    http_headers=None,
    hls_prefer_native=False,
):
    logger = YTDLPLogger()
    ydl_opts = {
        "format": format_choice,
        "merge_output_format": "mp4",
        "noplaylist": False,
        "retries": 10,
        "fragment_retries": 10,
        "ignoreerrors": True,
        "extract_flat": False,
        "progress_hooks": [progress_hook],
        "logger": logger,
        "outtmpl": os.path.join(target_folder, "%(title)s.%(ext)s"),
    }

    if http_headers:
        ydl_opts["http_headers"] = dict(http_headers)

    if hls_prefer_native:
        ydl_opts["hls_prefer_native"] = True

    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = os.path.dirname(FFMPEG_PATH)

    if use_aria2:
        ydl_opts["external_downloader"] = {
            "default": ARIA2C_PATH,
        }
        ydl_opts["external_downloader_args"] = {
            "default": ARIA2C_ARGS,
        }

    def enable_png_thumbnail_output():
        ydl_opts["writethumbnail"] = True
        ydl_opts["convertthumbnails"] = "png"
        ydl_opts.setdefault("postprocessors", []).append({
            "key": "FFmpegThumbnailsConvertor",
            "format": "png"
        })

    if thumbnail_only:
        ydl_opts["skip_download"] = True
        enable_png_thumbnail_output()
    elif download_thumbnail:
        enable_png_thumbnail_output()

    if audio_only and not audio_to_video_mp4:
        ydl_opts.setdefault("postprocessors", []).append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        })

    return ydl_opts, logger


def download_url_with_fallback(
    download_url,
    format_choice,
    target_folder,
    download_thumbnail,
    audio_only,
    audio_to_video_mp4,
    thumbnail_only,
    use_aria2,
):
    """Download a single media URL with retry/fallback strategy."""
    is_generic_site = not is_youtube_like_url(download_url)
    generic_headers = build_generic_site_headers(download_url) if is_generic_site else None
    generic_fallback_format = (
        format_choice
        if audio_only or thumbnail_only
        else GENERIC_SITE_FALLBACK_FORMAT
    )
    attempts = [
        {
            "label": None,
            "format_choice": format_choice,
            "use_aria2": use_aria2,
            "http_headers": None,
            "hls_prefer_native": False,
        }
    ]

    if use_aria2:
        attempts.append({
            "label": (
                "aria2c failed on this media URL. Retrying without aria2c and "
                "disabling acceleration for the rest of this batch.\n"
            ),
            "requires_aria2_failure": True,
            "format_choice": format_choice,
            "use_aria2": False,
            "http_headers": None,
            "hls_prefer_native": False,
        })

    if is_generic_site:
        attempts.append({
            "label": (
                "Applying generic-site fallback with browser headers and a "
                "simpler best-quality format.\n"
            ),
            "requires_aria2_failure": False,
            "format_choice": generic_fallback_format,
            "use_aria2": False,
            "http_headers": generic_headers,
            "hls_prefer_native": True,
        })

    last_exception = None
    previous_failure_was_aria2 = False

    for attempt_index, attempt in enumerate(attempts):
        if attempt.get("requires_aria2_failure") and not previous_failure_was_aria2:
            continue

        if attempt["label"]:
            append_terminal(attempt["label"])

        ydl_opts, logger = build_ydl_options(
            attempt["format_choice"],
            target_folder,
            download_thumbnail,
            audio_only,
            audio_to_video_mp4=audio_to_video_mp4,
            thumbnail_only=thumbnail_only,
            use_aria2=attempt["use_aria2"],
            http_headers=attempt["http_headers"],
            hls_prefer_native=attempt["hls_prefer_native"],
        )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                download_info = ydl.extract_info(download_url, download=True)
        except Exception as exc:
            last_exception = exc

            if attempt["use_aria2"] and (
                logger.aria2_failed or is_aria2_failure_message(exc)
            ):
                previous_failure_was_aria2 = True
                continue

            previous_failure_was_aria2 = False

            if attempt_index < len(attempts) - 1:
                continue

            raise

        if attempt["use_aria2"] and logger.aria2_failed:
            last_exception = RuntimeError("aria2c failed during download.")
            previous_failure_was_aria2 = True
            continue

        aria2_enabled_after_download = use_aria2 and attempt["use_aria2"]
        return aria2_enabled_after_download, download_info

    if last_exception is not None:
        raise last_exception

    return False, None


def get_downloaded_filepaths(download_info):
    filepaths = []
    seen_paths = set()

    if not isinstance(download_info, dict):
        return filepaths

    def add_path(candidate_path):
        normalized_path = str(candidate_path or "").strip()

        if not normalized_path:
            return

        absolute_path = os.path.abspath(normalized_path)
        dedupe_key = absolute_path.lower()

        if dedupe_key in seen_paths:
            return

        if os.path.isfile(absolute_path):
            seen_paths.add(dedupe_key)
            filepaths.append(absolute_path)

    for requested in download_info.get("requested_downloads", []):
        if isinstance(requested, dict):
            add_path(requested.get("filepath"))

    add_path(download_info.get("filepath"))
    add_path(download_info.get("_filename"))

    return filepaths


def convert_audio_file_to_black_mp4(audio_path):
    ffmpeg_path = ensure_ffmpeg_available()

    if not ffmpeg_path:
        raise RuntimeError(
            "ffmpeg was not found. Install ffmpeg to use Audio As MP4 (Black 16:9)."
        )

    source_path = os.path.abspath(audio_path)
    source_dir = os.path.dirname(source_path)
    source_name = os.path.splitext(os.path.basename(source_path))[0]
    output_path = os.path.join(source_dir, f"{source_name}.mp4")

    if output_path.lower() == source_path.lower():
        output_path = os.path.join(source_dir, f"{source_name}_black.mp4")

    ffmpeg_command = [
        ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1280x720:r=30",
        "-i",
        source_path,
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        output_path,
    ]

    completed = subprocess.run(
        ffmpeg_command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if completed.returncode != 0:
        error_tail = "\n".join((completed.stderr or "").splitlines()[-8:])
        raise RuntimeError(
            "ffmpeg failed while creating black-background MP4.\n"
            f"{error_tail}"
        )

    if source_path.lower() != output_path.lower():
        try:
            os.remove(source_path)
        except OSError:
            pass

    return output_path


def ensure_spotdl_installed():
    if importlib.util.find_spec("pkg_resources") is None:
        append_terminal("setuptools is missing. Installing setuptools...\n")
        install("setuptools")

    version_check = subprocess.run(
        [sys.executable, "-m", "spotdl", "--version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if version_check.returncode == 0:
        return

    combined_output = f"{version_check.stdout or ''}\n{version_check.stderr or ''}"

    if "pkg_resources" in combined_output.lower():
        append_terminal("spotdl is missing pkg_resources. Repairing setuptools...\n")
        install("setuptools")

    append_terminal("spotdl not found or unhealthy. Installing/repairing spotdl...\n")
    install("spotdl")

    retry_check = subprocess.run(
        [sys.executable, "-m", "spotdl", "--version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if retry_check.returncode != 0:
        raise RuntimeError(
            "spotdl is installed but failed to start. "
            "Try running: python -m pip install --upgrade setuptools spotdl"
        )


def collect_audio_files(root_folder):
    collected = set()

    for root, _, files in os.walk(root_folder):
        for file_name in files:
            extension = os.path.splitext(file_name)[1].lower()
            if extension in AUDIO_FILE_EXTENSIONS:
                collected.add(os.path.abspath(os.path.join(root, file_name)))

    return collected


def collect_image_files(root_folder, modified_after=None):
    collected = []
    modified_after = (
        float(modified_after) if modified_after is not None else None
    )

    for root, _, files in os.walk(root_folder):
        for file_name in files:
            extension = os.path.splitext(file_name)[1].lower()
            if extension not in IMAGE_FILE_EXTENSIONS:
                continue

            absolute_path = os.path.abspath(os.path.join(root, file_name))

            if modified_after is not None:
                try:
                    file_mtime = os.path.getmtime(absolute_path)
                except OSError:
                    continue

                if file_mtime < modified_after:
                    continue

            collected.append(absolute_path)

    return sorted(collected)


def convert_image_file_to_png(image_path):
    ffmpeg_path = ensure_ffmpeg_available()

    if not ffmpeg_path:
        raise RuntimeError("ffmpeg is required to convert thumbnails to PNG.")

    source_path = os.path.abspath(image_path)

    if source_path.lower().endswith(".png"):
        return source_path

    source_dir = os.path.dirname(source_path)
    source_name = os.path.splitext(os.path.basename(source_path))[0]
    output_path = os.path.join(source_dir, f"{source_name}.png")

    command = [
        ffmpeg_path,
        "-y",
        "-i",
        source_path,
        output_path,
    ]
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if completed.returncode != 0:
        error_tail = "\n".join((completed.stderr or "").splitlines()[-8:])
        raise RuntimeError(
            "ffmpeg failed while converting a thumbnail to PNG.\n"
            f"{error_tail}"
        )

    if source_path.lower() != output_path.lower():
        try:
            os.remove(source_path)
        except OSError:
            pass

    return output_path


def normalize_recent_images_to_png(root_folder, modified_after):
    recent_images = collect_image_files(
        root_folder,
        modified_after=modified_after,
    )

    for image_path in recent_images:
        if image_path.lower().endswith(".png"):
            continue

        png_path = convert_image_file_to_png(image_path)
        append_terminal(f"Converted Thumbnail To PNG: {png_path}\n")


def run_spotify_download(
    spotify_url,
    target_folder,
    audio_to_video_mp4=False,
):
    """Download Spotify tracks/playlists via spotdl and stream output to UI."""
    ensure_spotdl_installed()
    image_conversion_threshold = time.time() - 1

    output_template = os.path.join(target_folder, "{artists} - {title}.{output-ext}")
    command = [
        sys.executable,
        "-m",
        "spotdl",
        "download",
        spotify_url,
        "--output",
        output_template,
    ]
    before_files = collect_audio_files(target_folder)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    if process.stdout is not None:
        for output_line in process.stdout:
            normalized = output_line.rstrip()
            if normalized:
                append_terminal(normalized + "\n")

    return_code = process.wait()

    if return_code != 0:
        raise RuntimeError("spotdl failed while downloading from Spotify.")

    normalize_recent_images_to_png(target_folder, image_conversion_threshold)

    if audio_to_video_mp4:
        after_files = collect_audio_files(target_folder)
        new_audio_files = sorted(after_files - before_files)

        if not new_audio_files:
            append_terminal(
                "No New Audio Files Were Found For MP4 Conversion.\n"
            )

        for audio_path in new_audio_files:
            mp4_path = convert_audio_file_to_black_mp4(audio_path)
            append_terminal(f"Created MP4 Audio Video: {mp4_path}\n")


def get_format_choice():
    quality = quality_var.get()

    if audio_only_var.get():
        return "bestaudio/best"

    return QUALITY_MAP.get(quality, "bestvideo+bestaudio/best")


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


def resolve_download_options(download_mode):
    """Resolve mode-specific options from UI state and requested action."""
    if download_mode == "audio":
        return {
            "audio_only": True,
            "download_thumbnail": False,
            "audio_to_video_mp4": bool(audio_mp4_var.get()),
            "thumbnail_only": False,
            "format_choice": "bestaudio/best",
        }

    if download_mode == "thumbnail":
        return {
            "audio_only": False,
            "download_thumbnail": True,
            "audio_to_video_mp4": False,
            "thumbnail_only": True,
            "format_choice": "b/best",
        }

    if download_mode == "video":
        return {
            "audio_only": False,
            "download_thumbnail": bool(thumbnail_var.get()),
            "audio_to_video_mp4": False,
            "thumbnail_only": False,
            "format_choice": get_format_choice(),
        }

    return {
        "audio_only": bool(audio_only_var.get()),
        "download_thumbnail": bool(thumbnail_var.get()),
        "audio_to_video_mp4": False,
        "thumbnail_only": False,
        "format_choice": get_format_choice(),
    }


def extract_download_targets(info, source_url):
    """
    Return downloadable URLs from extracted info.
    Falls back to the source URL when no playlist entries are available.
    """
    entries = info.get("entries")

    if not entries:
        return [source_url], False

    targets = []
    for entry in entries:
        if not entry:
            continue

        entry_url = entry.get("webpage_url") or entry.get("url")
        if entry_url:
            targets.append(entry_url)
        else:
            append_terminal(
                "Skipping playlist item because no downloadable URL was returned.\n"
            )

    if not targets:
        return [source_url], False

    return targets, True


def finalize_audio_as_mp4(download_info):
    """Convert downloaded audio files into black-background MP4 videos."""
    for downloaded_path in get_downloaded_filepaths(download_info):
        mp4_path = convert_audio_file_to_black_mp4(downloaded_path)
        append_terminal(f"Created MP4 Audio Video: {mp4_path}\n")


# =========================================================
# MAIN DOWNLOAD FUNCTION
# =========================================================
def run_command(download_mode=None):
    """Validate user input and run the selected download workflow."""
    url = url_box.get("1.0","end-1c").strip()

    if not url:
        return

    spotify_mode = is_spotify_url(url)
    mode_options = resolve_download_options(download_mode)
    audio_only = mode_options["audio_only"]
    download_thumbnail = mode_options["download_thumbnail"]
    audio_to_video_mp4 = mode_options["audio_to_video_mp4"]
    thumbnail_only = mode_options["thumbnail_only"]
    format_choice = mode_options["format_choice"]

    target_folder = location_var.get().strip()

    if not target_folder:
        append_terminal("Error: Select a download location before downloading.\n")
        return

    if download_thumbnail or thumbnail_only or audio_to_video_mp4:
        if not ensure_ffmpeg_available():
            append_terminal(
                "Error: ffmpeg is required for thumbnail conversion and audio-to-MP4 mode.\n"
            )
            return

    if spotify_mode and thumbnail_only:
        append_terminal(
            "Spotify Thumbnail-Only Mode Is Not Supported. Use Download Audio Only.\n"
        )
        return

    if spotify_mode and download_mode == "video":
        append_terminal(
            "Spotify URLs Are Audio Sources. Downloading Audio Instead.\n"
        )
        audio_only = True
        download_thumbnail = False
        format_choice = "bestaudio/best"

    if spotify_mode and download_thumbnail:
        append_terminal(
            "Include Thumbnail Uses Youtube Post-Processing And Is Ignored For Spotify.\n"
        )

    use_aria2 = bool(
        use_aria2_var.get()
        and ARIA2C_PATH
        and not thumbnail_only
        and not spotify_mode
    )

    def task():

        reset_download_stats()
        start_elapsed_timer()
        if spotify_mode:
            if audio_to_video_mp4:
                append_terminal("Starting Spotify Download As MP4 (Black 16:9)...\n")
            else:
                append_terminal("Starting Spotify Download...\n")
        elif thumbnail_only:
            append_terminal("Starting Thumbnail-Only Download...\n")
        elif audio_only:
            if audio_to_video_mp4:
                append_terminal("Starting Audio-Only Download As MP4 (Black 16:9)...\n")
            else:
                append_terminal("Starting Audio-Only Download...\n")
        else:
            append_terminal("Starting Download...\n")
        aria2_enabled_for_batch = use_aria2

        if use_aria2:
            append_terminal(
                f"aria2c acceleration enabled ({' '.join(ARIA2C_ARGS)})\n"
            )

        try:
            if spotify_mode:
                run_on_ui(playlist_var.set, "Spotify Playlist")
                run_spotify_download(
                    url,
                    target_folder,
                    audio_to_video_mp4=audio_to_video_mp4,
                )
                run_on_ui(playlist_var.set, "Done")
                append_terminal("\nDownload Complete\n")
                return

            generic_site = not is_youtube_like_url(url)
            generic_headers = build_generic_site_headers(url) if generic_site else None

            info_opts, _ = build_ydl_options(
                format_choice,
                target_folder,
                download_thumbnail,
                audio_only,
                audio_to_video_mp4=audio_to_video_mp4,
                thumbnail_only=thumbnail_only,
                use_aria2=False,
                http_headers=generic_headers,
                hls_prefer_native=generic_site,
            )

            with yt_dlp.YoutubeDL(info_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            targets, is_playlist = extract_download_targets(info, url)
            total_targets = len(targets)

            if is_playlist:
                run_on_ui(playlist_var.set, f"0 / {total_targets}")
            else:
                run_on_ui(playlist_var.set, "1 / 1")

            for index, target_url in enumerate(targets, start=1):
                if is_playlist:
                    run_on_ui(playlist_var.set, f"{index} / {total_targets}")

                image_conversion_threshold = (
                    time.time() - 1
                    if (download_thumbnail or thumbnail_only)
                    else None
                )

                aria2_enabled_for_batch, download_info = download_url_with_fallback(
                    target_url,
                    format_choice,
                    target_folder,
                    download_thumbnail,
                    audio_only,
                    audio_to_video_mp4,
                    thumbnail_only,
                    aria2_enabled_for_batch,
                )

                if image_conversion_threshold is not None:
                    normalize_recent_images_to_png(
                        target_folder,
                        image_conversion_threshold,
                    )

                if audio_to_video_mp4 and download_info is not None:
                    finalize_audio_as_mp4(download_info)

            append_terminal("\nDownload Complete\n")

        except Exception as e:

            append_terminal(f"\nError: {e}\n")
        finally:
            stop_elapsed_timer()
            clear_download_location()

    threading.Thread(target=task, daemon=True, name="download-worker").start()


# =========================================================
# UI BUILDERS
# =========================================================
def build_layout_one():
    global url_box
    global terminal

    window.config(bg="#2b2b2b")
    left_frame = Frame(window, bg="#2b2b2b")
    left_frame.pack(side=LEFT, fill=BOTH, expand=True)

    right_frame = Frame(
        window,
        bg="#2b2b2b",
        width=420,
        highlightthickness=1,
        highlightbackground="#444",
    )
    right_frame.pack(side=RIGHT, fill=BOTH)
    right_frame.pack_propagate(False)

    Label(
        left_frame,
        text="Video URL / Playlist / Channel:",
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 12),
    ).pack(anchor="nw", padx=10, pady=(10, 0))

    url_box = Text(
        left_frame,
        height=3,
        bg="#1e1e1e",
        fg=ACCENT_COLOR,
        insertbackground=ACCENT_COLOR,
        font=("Consolas", 11),
    )
    url_box.pack(fill=X, padx=10, pady=5)
    url_box.drop_target_register(DND_TEXT)
    url_box.dnd_bind("<<Drop>>", drop_url)

    control_frame = Frame(left_frame, bg="#2b2b2b")
    control_frame.pack(fill=X, padx=10, pady=10)

    Button(
        control_frame,
        text="Download",
        command=run_command,
        bg="#444",
        fg=ACCENT_COLOR,
        font=("Consolas", 12),
    ).pack(side=LEFT)

    Button(
        control_frame,
        text="Location",
        command=browse_folder,
        bg="#444",
        fg=ACCENT_COLOR,
        font=("Consolas", 12),
    ).pack(side=LEFT, padx=10)

    Button(
        control_frame,
        text="Set Default",
        command=set_default_download_location,
        bg="#444",
        fg=ACCENT_COLOR,
        font=("Consolas", 12),
    ).pack(side=LEFT, padx=(0, 10))

    Entry(
        control_frame,
        textvariable=location_var,
        bg="#1e1e1e",
        fg=ACCENT_COLOR,
        insertbackground=ACCENT_COLOR,
        font=("Consolas", 12),
        relief=FLAT,
    ).pack(side=LEFT, fill=X, expand=True)

    quality_frame = Frame(left_frame, bg="#2b2b2b")
    quality_frame.pack(anchor="nw", padx=10, pady=(0, 10), fill=X)

    Label(
        quality_frame,
        text="Video Quality:",
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 11),
    ).pack(anchor="w")

    row = Frame(quality_frame, bg="#2b2b2b")
    row.pack(fill=X)

    style = ttk.Style()
    style.theme_use("default")
    style.configure(
        "Dark.TCombobox",
        fieldbackground="#1e1e1e",
        background="#1e1e1e",
        foreground=ACCENT_COLOR,
    )

    quality_dropdown = ttk.Combobox(
        row,
        textvariable=quality_var,
        values=["480p", "720p", "1080p", "Max"],
        state="readonly",
        font=("Consolas", 11),
        width=10,
        style="Dark.TCombobox",
    )
    quality_dropdown.pack(side=LEFT)
    quality_dropdown.bind("<<ComboboxSelected>>", lambda _event: save_quality_preference())

    options_frame = Frame(left_frame, bg="#2b2b2b")
    options_frame.pack(anchor="nw", padx=10, pady=10)

    Checkbutton(
        options_frame,
        text="Download thumbnails",
        variable=thumbnail_var,
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        selectcolor="#1e1e1e",
        font=("Consolas", 11),
    ).pack(anchor="w")

    Checkbutton(
        options_frame,
        text="Download audio only",
        variable=audio_only_var,
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        selectcolor="#1e1e1e",
        font=("Consolas", 11),
    ).pack(anchor="w")

    Checkbutton(
        options_frame,
        text="Use aria2c acceleration",
        variable=use_aria2_var,
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        selectcolor="#1e1e1e",
        font=("Consolas", 11),
        state=NORMAL if ARIA2C_PATH else DISABLED,
    ).pack(anchor="w")

    bottom_frame = Frame(left_frame, bg="#2b2b2b")
    bottom_frame.pack(side=BOTTOM, fill=X, padx=10, pady=10)

    Label(
        bottom_frame,
        text="Playlist Progress:",
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 11),
    ).pack(anchor="w")

    Label(
        bottom_frame,
        textvariable=playlist_var,
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 11),
    ).pack(anchor="w")

    stats_frame = Frame(bottom_frame, bg="#2b2b2b")
    stats_frame.pack(fill=X)

    left_stats_frame = Frame(stats_frame, bg="#2b2b2b")
    left_stats_frame.pack(side=LEFT)

    Label(
        left_stats_frame,
        text="Speed:",
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 10),
    ).pack(side=LEFT)

    Label(
        left_stats_frame,
        textvariable=speed_var,
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 10),
    ).pack(side=LEFT, padx=(5, 20))

    Label(
        left_stats_frame,
        text="ETA:",
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 10),
    ).pack(side=LEFT)

    Label(
        left_stats_frame,
        textvariable=eta_var,
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 10),
    ).pack(side=LEFT, padx=5)

    Label(
        bottom_frame,
        text="Progress...",
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 11),
    ).pack(anchor="w")

    progress_row = Frame(bottom_frame, bg="#2b2b2b")
    progress_row.pack(fill=X)

    Label(
        progress_row,
        textvariable=progress_text,
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 11),
    ).pack(side=LEFT)

    progress_meta_frame = Frame(progress_row, bg="#2b2b2b")
    progress_meta_frame.pack(side=RIGHT)

    Label(
        progress_meta_frame,
        text="Elapsed:",
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 10),
    ).pack(side=LEFT, padx=(0, 5))

    Label(
        progress_meta_frame,
        textvariable=elapsed_var,
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 10),
    ).pack(side=LEFT, padx=(0, 20))

    Label(
        progress_meta_frame,
        text="Version:",
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 10),
    ).pack(side=LEFT, padx=(0, 5))

    version_value_label = Label(
        progress_meta_frame,
        text=APP_VERSION,
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 10),
    )
    version_value_label.pack(side=LEFT)
    bind_layout_toggle_easter_egg(version_value_label)

    style.configure(
        "purple.Horizontal.TProgressbar",
        troughcolor="#1e1e1e",
        background=ACCENT_COLOR,
        thickness=20,
    )

    ttk.Progressbar(
        bottom_frame,
        variable=progress_var,
        maximum=100,
        style="purple.Horizontal.TProgressbar",
    ).pack(fill=X, pady=10)

    Label(
        right_frame,
        text="Terminal Output:",
        bg="#2b2b2b",
        fg=ACCENT_COLOR,
        font=("Consolas", 12),
    ).pack(anchor="nw", padx=10, pady=(10, 0))

    terminal = Text(
        right_frame,
        bg="black",
        fg=TERMINAL_COLOR,
        insertbackground=TERMINAL_COLOR,
        font=("Consolas", 10),
        width=48,
    )
    terminal.pack(fill=BOTH, expand=True, padx=10, pady=10)


def build_layout_two():
    global url_box
    global terminal

    page_bg = "#11151d"
    card_bg = "#1b2330"
    section_bg = "#141a25"
    border_color = "#2f3d54"
    body_text = "#dbe6f5"

    window.config(bg=page_bg)
    style = ttk.Style()
    style.theme_use("default")
    style.configure(
        "Layout2.Horizontal.TProgressbar",
        troughcolor="#0d121a",
        background=ACCENT_COLOR,
        thickness=16,
    )
    style.configure(
        "Layout2.TCombobox",
        fieldbackground=section_bg,
        background=section_bg,
        foreground=body_text,
        arrowcolor=body_text,
    )
    style.map(
        "Layout2.TCombobox",
        fieldbackground=[("readonly", section_bg)],
        background=[("readonly", section_bg)],
        foreground=[("readonly", body_text)],
        selectbackground=[("readonly", section_bg)],
        selectforeground=[("readonly", body_text)],
    )

    root = Frame(window, bg=page_bg)
    root.pack(fill=BOTH, expand=True, padx=16, pady=16)

    header = Frame(root, bg=page_bg)
    header.pack(fill=X, pady=(0, 10))

    Label(
        header,
        text="YTDLPV3",
        bg=page_bg,
        fg=ACCENT_COLOR,
        font=("Segoe UI Semibold", 18),
    ).pack(side=LEFT)

    layout_hint_label = Label(
        header,
        text=f"Layout 2 | V{APP_VERSION}",
        bg=page_bg,
        fg="#8aa0bd",
        font=("Segoe UI", 10),
    )
    layout_hint_label.pack(side=RIGHT)
    bind_layout_toggle_easter_egg(layout_hint_label)

    top_row = Frame(root, bg=page_bg)
    top_row.pack(fill=BOTH, expand=True)

    left_card = Frame(
        top_row,
        bg=card_bg,
        highlightthickness=1,
        highlightbackground=border_color,
        padx=14,
        pady=14,
    )
    left_card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))

    right_card = Frame(
        top_row,
        bg=card_bg,
        highlightthickness=1,
        highlightbackground=border_color,
        padx=10,
        pady=10,
    )
    right_card.pack(side=RIGHT, fill=BOTH, expand=True, padx=(8, 0))

    Label(
        left_card,
        text="Paste Url Or Drop Video",
        bg=card_bg,
        fg=body_text,
        font=("Segoe UI Semibold", 11),
    ).pack(anchor="w")

    url_box = Text(
        left_card,
        height=4,
        bg=section_bg,
        fg=body_text,
        insertbackground=ACCENT_COLOR,
        relief=FLAT,
        font=("Consolas", 11),
    )
    url_box.pack(fill=X, pady=(6, 10))
    url_box.drop_target_register(DND_TEXT)
    url_box.dnd_bind("<<Drop>>", drop_url)

    download_row = Frame(left_card, bg=card_bg)
    download_row.pack(fill=X, pady=(0, 10))

    Button(
        download_row,
        text="Download Videos",
        command=lambda: run_command("video"),
        bg=ACCENT_COLOR,
        fg="#11151d",
        activebackground=ACCENT_COLOR,
        activeforeground="#11151d",
        relief=FLAT,
        padx=12,
        pady=7,
        font=("Segoe UI Semibold", 10),
    ).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

    Button(
        download_row,
        text="Download Audio Only",
        command=lambda: run_command("audio"),
        bg="#2a3447",
        fg=body_text,
        activebackground="#374862",
        activeforeground=body_text,
        relief=FLAT,
        padx=12,
        pady=7,
        font=("Segoe UI Semibold", 10),
    ).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

    Button(
        download_row,
        text="Download Thumbnails Only",
        command=lambda: run_command("thumbnail"),
        bg="#2a3447",
        fg=body_text,
        activebackground="#374862",
        activeforeground=body_text,
        relief=FLAT,
        padx=12,
        pady=7,
        font=("Segoe UI Semibold", 10),
    ).pack(side=LEFT, fill=X, expand=True)

    location_row = Frame(left_card, bg=card_bg)
    location_row.pack(fill=X, pady=(0, 10))

    Entry(
        location_row,
        textvariable=location_var,
        bg=section_bg,
        fg=body_text,
        insertbackground=ACCENT_COLOR,
        relief=FLAT,
        font=("Consolas", 11),
    ).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

    Button(
        location_row,
        text="Location",
        command=browse_folder,
        bg="#2a3447",
        fg=body_text,
        activebackground="#374862",
        activeforeground=body_text,
        relief=FLAT,
        font=("Segoe UI", 10),
    ).pack(side=LEFT, padx=(0, 8))

    Button(
        location_row,
        text="Set Default",
        command=set_default_download_location,
        bg="#2a3447",
        fg=body_text,
        activebackground="#374862",
        activeforeground=body_text,
        relief=FLAT,
        font=("Segoe UI", 10),
    ).pack(side=LEFT)

    settings_row = Frame(left_card, bg=card_bg)
    settings_row.pack(fill=X, pady=(0, 8))

    Label(
        settings_row,
        text="Quality",
        bg=card_bg,
        fg="#9fb3ce",
        font=("Segoe UI", 10),
    ).pack(side=LEFT)

    quality_dropdown = ttk.Combobox(
        settings_row,
        textvariable=quality_var,
        values=["480p", "720p", "1080p", "Max"],
        state="readonly",
        width=10,
        style="Layout2.TCombobox",
    )
    quality_dropdown.pack(side=LEFT, padx=(8, 16))
    quality_dropdown.bind(
        "<<ComboboxSelected>>",
        lambda _event: (
            save_quality_preference(),
            window.after(1, window.focus_set),
        ),
    )

    Checkbutton(
        settings_row,
        text="Include Thumbnail",
        variable=thumbnail_var,
        bg=card_bg,
        fg=body_text,
        activebackground=card_bg,
        activeforeground=body_text,
        selectcolor=section_bg,
        font=("Segoe UI", 10),
    ).pack(side=LEFT, padx=(0, 14))

    Checkbutton(
        settings_row,
        text="Audio As MP4",
        variable=audio_mp4_var,
        bg=card_bg,
        fg=body_text,
        activebackground=card_bg,
        activeforeground=body_text,
        selectcolor=section_bg,
        font=("Segoe UI", 10),
    ).pack(side=LEFT)

    Button(
        settings_row,
        text="Start Launcher",
        command=start_launcher,
        bg="#2a3447",
        fg=body_text,
        activebackground="#374862",
        activeforeground=body_text,
        relief=FLAT,
        padx=10,
        font=("Segoe UI", 10),
    ).pack(side=RIGHT)

    Checkbutton(
        left_card,
        text="Use Aria2c Acceleration",
        variable=use_aria2_var,
        bg=card_bg,
        fg=body_text,
        activebackground=card_bg,
        activeforeground=body_text,
        selectcolor=section_bg,
        font=("Segoe UI", 10),
        state=NORMAL if ARIA2C_PATH else DISABLED,
    ).pack(anchor="w")

    Label(
        right_card,
        text="Terminal Log",
        bg=card_bg,
        fg=body_text,
        font=("Segoe UI Semibold", 11),
    ).pack(anchor="w", pady=(0, 6))

    terminal = Text(
        right_card,
        bg="#0d121a",
        fg=TERMINAL_COLOR,
        insertbackground=TERMINAL_COLOR,
        relief=FLAT,
        font=("Consolas", 10),
    )
    terminal.pack(fill=BOTH, expand=True)

    left_bottom_card = Frame(
        left_card,
        bg=card_bg,
        highlightthickness=1,
        highlightbackground=border_color,
        padx=12,
        pady=10,
    )
    left_bottom_card.pack(side=BOTTOM, fill=X, pady=(2, 0))

    status_frame = Frame(left_card, bg=card_bg)
    status_frame.pack(side=BOTTOM, fill=X, pady=(0, 2))

    Label(
        status_frame,
        textvariable=aria2_status_var,
        bg=card_bg,
        fg="#8294b0",
        justify=RIGHT,
        wraplength=720,
        font=("Segoe UI", 9),
    ).pack(anchor="e")

    Label(
        status_frame,
        textvariable=ffmpeg_status_var,
        bg=card_bg,
        fg="#8294b0",
        justify=RIGHT,
        wraplength=720,
        font=("Segoe UI", 9),
    ).pack(anchor="e", pady=(2, 0))

    stat_strip = Frame(
        left_bottom_card,
        bg=section_bg,
        highlightthickness=1,
        highlightbackground=border_color,
    )
    stat_strip.pack(fill=X, pady=(0, 10))

    Label(
        stat_strip,
        text="Playlist",
        bg=section_bg,
        fg="#8ba0bd",
        font=("Segoe UI", 9),
    ).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 0))

    Label(
        stat_strip,
        text="Speed",
        bg=section_bg,
        fg="#8ba0bd",
        font=("Segoe UI", 9),
    ).grid(row=0, column=1, sticky="w", padx=8, pady=(6, 0))

    Label(
        stat_strip,
        text="Eta",
        bg=section_bg,
        fg="#8ba0bd",
        font=("Segoe UI", 9),
    ).grid(row=0, column=2, sticky="w", padx=8, pady=(6, 0))

    Label(
        stat_strip,
        text="Elapsed",
        bg=section_bg,
        fg="#8ba0bd",
        font=("Segoe UI", 9),
    ).grid(row=0, column=3, sticky="w", padx=8, pady=(6, 0))

    Label(
        stat_strip,
        textvariable=playlist_var,
        bg=section_bg,
        fg=body_text,
        font=("Consolas", 10),
    ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 6))

    Label(
        stat_strip,
        textvariable=speed_var,
        bg=section_bg,
        fg=body_text,
        font=("Consolas", 10),
    ).grid(row=1, column=1, sticky="w", padx=8, pady=(0, 6))

    Label(
        stat_strip,
        textvariable=eta_var,
        bg=section_bg,
        fg=body_text,
        font=("Consolas", 10),
    ).grid(row=1, column=2, sticky="w", padx=8, pady=(0, 6))

    Label(
        stat_strip,
        textvariable=elapsed_var,
        bg=section_bg,
        fg=body_text,
        font=("Consolas", 10),
    ).grid(row=1, column=3, sticky="w", padx=8, pady=(0, 6))

    for column in range(4):
        stat_strip.grid_columnconfigure(column, weight=1)

    progress_row = Frame(left_bottom_card, bg=card_bg)
    progress_row.pack(fill=X)

    Label(
        progress_row,
        textvariable=progress_text,
        bg=card_bg,
        fg=ACCENT_COLOR,
        font=("Segoe UI Semibold", 12),
    ).pack(side=LEFT)

    Label(
        progress_row,
        text="Made By Tj, With Love <3",
        bg=card_bg,
        fg="#8aa0bd",
        font=("Segoe UI", 10),
    ).pack(side=RIGHT)

    ttk.Progressbar(
        left_bottom_card,
        variable=progress_var,
        maximum=100,
        style="Layout2.Horizontal.TProgressbar",
    ).pack(fill=X, pady=(4, 0))


def build_ui():
    if APP_LAYOUT == "2":
        build_layout_two()
    else:
        build_layout_one()


build_ui()

process_ui_queue()

for startup_message in STARTUP_MESSAGES:
    append_terminal(startup_message)

append_terminal("Terminal ready...\n")
start_optional_dependency_setup()

sys.stdout = TerminalRedirect()
sys.stderr = TerminalRedirect()


# =========================================================
# APP LOOP
# =========================================================
window.mainloop()
