import importlib.util
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
import ctypes
import time
import atexit
from tkinter import BOTH, END, FLAT, LEFT, RIGHT, X, Button, Frame, Label, StringVar, Text, Tk
from tkinter import ttk


SHORTCUT_NAME = "YTDLPV3.lnk"
APP_USER_MODEL_ID = "yt_dlp.desktop.launcher"
SW_HIDE = 0
HTTP_USER_AGENT = "YTDLPV3-Launcher"
ARIA2C_RELEASE_API = "https://api.github.com/repos/aria2/aria2/releases/latest"
ARIA2C_ASSET_SUFFIX = "win-64bit-build1.zip"
FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "Config.json")
DEFAULTS_PATH = os.path.join(SCRIPT_DIR, "Defaults.json")
MAIN_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "MainScript.py")
ICON_PATH = os.path.join(SCRIPT_DIR, "favi.ico")
EXAMPLE_COLOURS_PATH = os.path.join(SCRIPT_DIR, "Example Colours.txt")
LOGS_DIR = os.path.join(SCRIPT_DIR, "Logs")
LAUNCHER_LOG_PATH = os.path.join(LOGS_DIR, f"Launcher_{time.strftime('%m_%d_%H_%M')}.log")
ARIA2C_INSTALL_DIR = os.path.join(SCRIPT_DIR, "aria2c")
FFMPEG_INSTALL_DIR = os.path.join(SCRIPT_DIR, "ffmpeg")
PYCACHE_DIR = os.path.join(SCRIPT_DIR, "__pycache__")
SPOTDL_CACHE_DIR = os.path.join(SCRIPT_DIR, ".spotdl")

# V2-inspired blue base palette.
PAGE_BG = "#11151d"
CARD_BG = "#1b2330"
SECTION_BG = "#141a25"
BORDER_COLOR = "#2f3d54"
BODY_TEXT = "#dbe6f5"
MUTED_TEXT = "#8aa0bd"
DEFAULT_ACCENT = "#4aa3ff"
DEFAULT_TERMINAL = "#9ae6ff"
DEFAULT_CONFIG_CONTENT = {
    "version": "3.0.0",
    "layout": "2",
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
EXAMPLE_COLOURS_CONTENT = """Lavender - #b478fa
White - #ffffff
Lime - #00ff00
Black - #000000
Red - #ff0000
Blue - #0000ff
Green - #008000
Yellow - #ffff00
Cyan - #00ffff
Magenta - #ff00ff
Orange - #ffa500
Purple - #800080
Pink - #ffc0cb
Brown - #a52a2a
Gray - #808080
Light Gray - #d3d3d3
Dark Gray - #404040
Gold - #ffd700
Silver - #c0c0c0
Navy - #000080
Teal - #008080
Olive - #808000
Sky Blue - #87ceeb
Violet - #ee82ee
Indigo - #4b0082
Coral - #ff7f50
Salmon - #fa8072
Mint - #98ff98
Turquoise - #40e0d0
Crimson - #dc143c
Beige - #f5f5dc
Ivory - #fffff0
"""


def format_example_colours_content(content):
    lines = []

    for raw_line in str(content).splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if " - " not in line:
            lines.append(line)
            continue

        name, hex_code = line.split(" - ", 1)
        normalized_name = " ".join(part.capitalize() for part in name.strip().split())
        lines.append(f"{normalized_name} - {hex_code.strip()}")

    return "\n".join(lines) + "\n"


def normalize_color(value, default):
    candidate = str(value or "").strip()

    if not candidate:
        return default

    if not candidate.startswith("#"):
        candidate = f"#{candidate}"

    if re.fullmatch(r"#[0-9a-fA-F]{6}", candidate):
        return candidate

    return default


def normalize_default_config(candidate):
    base = dict(DEFAULT_CONFIG_CONTENT)
    resolution = candidate.get("resolution", {})

    try:
        width = int(resolution.get("width", base["resolution"]["width"]))
    except Exception:
        width = base["resolution"]["width"]

    try:
        height = int(resolution.get("height", base["resolution"]["height"]))
    except Exception:
        height = base["resolution"]["height"]

    base["version"] = str(candidate.get("version", base["version"])).strip() or base["version"]
    base["layout"] = str(candidate.get("layout", base["layout"])).strip() or base["layout"]
    base["enable_layout_switch_easter_egg"] = bool(
        candidate.get(
            "enable_layout_switch_easter_egg",
            base["enable_layout_switch_easter_egg"],
        )
    )
    base["quality"] = str(candidate.get("quality", base["quality"])).strip() or base["quality"]
    base["fullscreen"] = bool(candidate.get("fullscreen", base["fullscreen"]))
    base["Accent"] = normalize_color(candidate.get("Accent"), base["Accent"])
    base["Terminal"] = normalize_color(candidate.get("Terminal"), base["Terminal"])
    base["default_download_location"] = str(
        candidate.get("default_download_location", base["default_download_location"])
    ).strip()
    base["resolution"] = {
        "width": max(900, width),
        "height": max(620, height),
    }

    return base


def load_default_config_template():
    try:
        with open(DEFAULTS_PATH, "r", encoding="utf-8") as defaults_file:
            loaded = json.load(defaults_file)
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG_CONTENT)

    if not isinstance(loaded, dict):
        return dict(DEFAULT_CONFIG_CONTENT)

    return normalize_default_config(loaded)


def load_launcher_config():
    default_template = load_default_config_template()
    default_resolution = default_template.get("resolution", {})

    try:
        template_width = int(default_resolution.get("width", 1040))
    except Exception:
        template_width = 1040

    try:
        template_height = int(default_resolution.get("height", 700))
    except Exception:
        template_height = 700

    defaults = {
        "Accent": normalize_color(default_template.get("Accent"), DEFAULT_ACCENT),
        "Terminal": normalize_color(default_template.get("Terminal"), DEFAULT_TERMINAL),
        "resolution": {
            "width": max(1040, template_width),
            "height": max(700, template_height),
        },
    }

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return defaults

    resolution = loaded.get("resolution", {})
    width = int(resolution.get("width", defaults["resolution"]["width"]))
    height = int(resolution.get("height", defaults["resolution"]["height"]))

    return {
        "Accent": normalize_color(loaded.get("Accent"), defaults["Accent"]),
        "Terminal": normalize_color(loaded.get("Terminal"), defaults["Terminal"]),
        "resolution": {
            "width": max(900, width),
            "height": max(620, height),
        },
    }


def desktop_dir():
    return os.path.join(os.path.expanduser("~"), "Desktop")


def get_pythonw_path():
    python_executable = sys.executable
    python_directory = os.path.dirname(python_executable)
    pythonw_candidate = os.path.join(python_directory, "pythonw.exe")

    if os.path.isfile(pythonw_candidate):
        return pythonw_candidate

    return python_executable


def create_shortcut(target_path, arguments, working_directory, icon_path, shortcut_path):
    escaped_target = target_path.replace("'", "''")
    escaped_arguments = arguments.replace("'", "''")
    escaped_icon = icon_path.replace("'", "''")
    escaped_shortcut = shortcut_path.replace("'", "''")
    escaped_workdir = working_directory.replace("'", "''")

    powershell_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{escaped_shortcut}')
$Shortcut.TargetPath = '{escaped_target}'
$Shortcut.Arguments = '{escaped_arguments}'
$Shortcut.WorkingDirectory = '{escaped_workdir}'
$Shortcut.IconLocation = '{escaped_icon}'
$Shortcut.Save()
""".strip()

    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            powershell_script,
        ],
        check=True,
    ) 


def invoke_shortcut_verb(shortcut_path, verb_candidates):
    escaped_shortcut = shortcut_path.replace("'", "''")
    escaped_verbs = ",".join("'" + verb.replace("'", "''") + "'" for verb in verb_candidates)
    powershell_script = f"""
$ErrorActionPreference = 'Stop'
$shortcutPath = '{escaped_shortcut}'
if (!(Test-Path -LiteralPath $shortcutPath)) {{
    throw "Shortcut not found: $shortcutPath"
}}
$shell = New-Object -ComObject Shell.Application
$folderPath = Split-Path -LiteralPath $shortcutPath
$leafName = Split-Path -Leaf $shortcutPath
$item = $shell.Namespace($folderPath).ParseName($leafName)
if ($null -eq $item) {{
    throw "Unable to resolve shortcut shell item."
}}
$verbs = @({escaped_verbs})
foreach ($needle in $verbs) {{
    $match = $item.Verbs() | Where-Object {{
        $_.Name -and $_.Name.Replace('&','').ToLower().Contains($needle.ToLower())
    }} | Select-Object -First 1
    if ($match) {{
        $match.DoIt()
        Start-Sleep -Milliseconds 200
        exit 0
    }}
}}
throw "No matching pin verb found."
""".strip()

    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            powershell_script,
        ],
        check=True,
    )


def build_request(url, accept_json=False):
    headers = {"User-Agent": HTTP_USER_AGENT}

    if accept_json:
        headers["Accept"] = "application/vnd.github+json"

    return urllib.request.Request(url, headers=headers)


def find_aria2c():
    local_candidates = (
        os.path.join(SCRIPT_DIR, "aria2c.exe"),
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

    with urllib.request.urlopen(request, timeout=20) as response:
        release_data = json.load(response)

    for asset in release_data.get("assets", []):
        asset_name = str(asset.get("name", "")).strip()
        download_url = str(asset.get("browser_download_url", "")).strip()

        if asset_name.endswith(ARIA2C_ASSET_SUFFIX) and download_url:
            return download_url, str(release_data.get("tag_name", asset_name)).strip()

    raise RuntimeError("Latest aria2 Windows asset was not found in release metadata.")


def auto_install_aria2c(log):
    existing = find_aria2c()

    if existing:
        log(f"aria2c already available at: {existing}")
        return existing

    temp_dir = tempfile.mkdtemp(prefix="aria2c_")

    try:
        log("aria2c not found. Downloading latest release...")
        download_url, release_tag = fetch_latest_aria2_download()
        archive_name = os.path.basename(download_url.split("?", 1)[0]) or "aria2c.zip"
        archive_path = os.path.join(temp_dir, archive_name)
        download_request = build_request(download_url)

        with urllib.request.urlopen(download_request, timeout=60) as response, open(archive_path, "wb") as archive_file:
            shutil.copyfileobj(response, archive_file)

        os.makedirs(ARIA2C_INSTALL_DIR, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(ARIA2C_INSTALL_DIR)

        installed = find_aria2c()

        if not installed:
            raise RuntimeError("aria2c download completed but aria2c.exe was not located.")

        log(f"aria2c installed successfully from {release_tag}.")
        return installed
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


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


def auto_install_ffmpeg(log):
    existing = find_ffmpeg()

    if existing:
        log(f"ffmpeg already available at: {existing}")
        return existing

    temp_dir = tempfile.mkdtemp(prefix="ffmpeg_")

    try:
        log("ffmpeg not found. Downloading release build...")
        archive_path = os.path.join(temp_dir, "ffmpeg-release-essentials.zip")
        download_request = build_request(FFMPEG_DOWNLOAD_URL)

        with urllib.request.urlopen(download_request, timeout=90) as response, open(archive_path, "wb") as archive_file:
            shutil.copyfileobj(response, archive_file)

        os.makedirs(FFMPEG_INSTALL_DIR, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(FFMPEG_INSTALL_DIR)

        installed = find_ffmpeg()

        if not installed:
            raise RuntimeError("ffmpeg download completed but ffmpeg.exe was not located.")

        log("ffmpeg installed successfully.")
        return installed
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def ensure_within_script_dir(path):
    normalized_script = os.path.normcase(os.path.abspath(SCRIPT_DIR))
    normalized_target = os.path.normcase(os.path.abspath(path))
    shared = os.path.commonpath([normalized_script, normalized_target])

    if shared != normalized_script:
        raise RuntimeError(f"Refusing to modify path outside script directory: {path}")

    return normalized_target


def is_example_log_name(file_name):
    base_name, _ = os.path.splitext(str(file_name).strip())
    return base_name.lower() == "00_00_00_00"


class DesktopLauncher:
    def __init__(self):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except Exception:
            pass

        self.config = load_launcher_config()
        self.accent = self.config["Accent"]
        self.terminal_color = self.config["Terminal"]
        self.ui_queue = queue.Queue()
        self.is_busy = False
        self.log_lock = threading.Lock()
        self.log_file = None
        self._init_log_file()

        self.root = Tk()
        self.root.title("YTDLPV3 Desktop Launcher")
        self.root.geometry(
            f'{self.config["resolution"]["width"]}x{self.config["resolution"]["height"]}'
        )
        self.root.minsize(980, 620)
        self.root.configure(bg=PAGE_BG)

        self.ytdlp_status = StringVar(value="Checking...")
        self.spotdl_status = StringVar(value="Checking...")
        self.dnd_status = StringVar(value="Checking...")
        self.aria2_status = StringVar(value="Checking...")
        self.ffmpeg_status = StringVar(value="Checking...")
        self.config_status = StringVar(value=f'Accent {self.accent} | Terminal {self.terminal_color}')

        self._apply_icon()
        self._build_ui()
        self._refresh_dependency_statuses()
        self._pump_ui_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.log(f"Launcher log file: {LAUNCHER_LOG_PATH}")
        self.log("Launcher ready.")

    def _init_log_file(self):
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            self.log_file = open(LAUNCHER_LOG_PATH, "a", encoding="utf-8", buffering=1)
            atexit.register(self._close_log_file)
        except OSError:
            self.log_file = None

    def _close_log_file(self):
        if self.log_file:
            try:
                self.log_file.close()
            except OSError:
                pass
            self.log_file = None

    def _on_close(self):
        self._close_log_file()
        self.root.destroy()

    def _apply_icon(self):
        if not os.path.isfile(ICON_PATH):
            return

        try:
            self.root.iconbitmap(ICON_PATH)
            self.root.wm_iconbitmap(ICON_PATH)
        except Exception:
            pass

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Launcher.Horizontal.TProgressbar",
            troughcolor="#0d121a",
            background=self.accent,
            thickness=14,
        )

        root_frame = Frame(self.root, bg=PAGE_BG)
        root_frame.pack(fill=BOTH, expand=True, padx=16, pady=16)

        header = Frame(root_frame, bg=PAGE_BG)
        header.pack(fill=X, pady=(0, 10))

        Label(
            header,
            text="YTDLPV3",
            bg=PAGE_BG,
            fg=self.accent,
            font=("Segoe UI Semibold", 20),
        ).pack(side=LEFT)

        Label(
            header,
            text="Desktop Launcher",
            bg=PAGE_BG,
            fg=MUTED_TEXT,
            font=("Segoe UI", 11),
        ).pack(side=RIGHT)

        cards = Frame(root_frame, bg=PAGE_BG)
        cards.pack(fill=BOTH, expand=True)

        left_card = Frame(
            cards,
            bg=CARD_BG,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            padx=14,
            pady=14,
        )
        left_card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))

        right_card = Frame(
            cards,
            bg=CARD_BG,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            padx=10,
            pady=10,
        )
        right_card.pack(side=RIGHT, fill=BOTH, expand=True, padx=(8, 0))

        Label(
            left_card,
            text="Quick Actions",
            bg=CARD_BG,
            fg=BODY_TEXT,
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w")

        button_row_one = Frame(left_card, bg=CARD_BG)
        button_row_one.pack(fill=X, pady=(8, 8))

        self.install_button = Button(
            button_row_one,
            text="Auto Install Everything Needed",
            command=self.action_auto_install,
            bg=self.accent,
            fg="#11151d",
            activebackground=self.accent,
            activeforeground="#11151d",
            relief=FLAT,
            padx=12,
            pady=8,
            font=("Segoe UI Semibold", 10),
        )
        self.install_button.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        self.shortcut_button = Button(
            button_row_one,
            text="Create Desktop Shortcut",
            command=self.action_create_shortcut,
            bg="#2a3447",
            fg=BODY_TEXT,
            activebackground="#374862",
            activeforeground=BODY_TEXT,
            relief=FLAT,
            padx=12,
            pady=8,
            font=("Segoe UI Semibold", 10),
        )
        self.shortcut_button.pack(side=LEFT, fill=X, expand=True)

        button_row_two = Frame(left_card, bg=CARD_BG)
        button_row_two.pack(fill=X, pady=(0, 8))

        self.pin_start_button = Button(
            button_row_two,
            text="Pin To Start",
            command=self.action_pin_to_start,
            bg="#2a3447",
            fg=BODY_TEXT,
            activebackground="#374862",
            activeforeground=BODY_TEXT,
            relief=FLAT,
            padx=12,
            pady=8,
            font=("Segoe UI Semibold", 10),
        )
        self.pin_start_button.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        self.pin_taskbar_button = Button(
            button_row_two,
            text="Pin To Taskbar",
            command=self.action_pin_to_taskbar,
            bg="#2a3447",
            fg=BODY_TEXT,
            activebackground="#374862",
            activeforeground=BODY_TEXT,
            relief=FLAT,
            padx=12,
            pady=8,
            font=("Segoe UI Semibold", 10),
        )
        self.pin_taskbar_button.pack(side=LEFT, fill=X, expand=True)

        button_row_three = Frame(left_card, bg=CARD_BG)
        button_row_three.pack(fill=X, pady=(0, 10))

        self.clean_button = Button(
            button_row_three,
            text="Purge Files",
            command=self.action_purge_files,
            bg="#7a2830",
            fg=BODY_TEXT,
            activebackground="#9a343f",
            activeforeground=BODY_TEXT,
            relief=FLAT,
            padx=12,
            pady=8,
            font=("Segoe UI Semibold", 10),
        )
        self.clean_button.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        self.reset_config_button = Button(
            button_row_three,
            text="Reset Config To Defaults",
            command=self.action_reset_config_to_defaults,
            bg="#2a3447",
            fg=BODY_TEXT,
            activebackground="#374862",
            activeforeground=BODY_TEXT,
            relief=FLAT,
            padx=12,
            pady=8,
            font=("Segoe UI Semibold", 10),
        )
        self.reset_config_button.pack(side=LEFT, fill=X, expand=True)

        status_card = Frame(
            left_card,
            bg=SECTION_BG,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            padx=12,
            pady=10,
        )
        status_card.pack(fill=X, pady=(0, 10))

        Label(
            status_card,
            text="Dependency Status",
            bg=SECTION_BG,
            fg=MUTED_TEXT,
            font=("Segoe UI", 10),
        ).pack(anchor="w")

        self._status_line(status_card, "yt-dlp", self.ytdlp_status)
        self._status_line(status_card, "spotdl", self.spotdl_status)
        self._status_line(status_card, "tkinterdnd2", self.dnd_status)
        self._status_line(status_card, "aria2c", self.aria2_status)
        self._status_line(status_card, "ffmpeg", self.ffmpeg_status)

        Label(
            left_card,
            textvariable=self.config_status,
            bg=CARD_BG,
            fg=MUTED_TEXT,
            font=("Consolas", 10),
        ).pack(anchor="w")

        Label(
            right_card,
            text="Launcher Log",
            bg=CARD_BG,
            fg=BODY_TEXT,
            font=("Segoe UI Semibold", 11),
        ).pack(anchor="w", pady=(0, 6))

        self.log_box = Text(
            right_card,
            bg="#0d121a",
            fg=self.terminal_color,
            insertbackground=self.terminal_color,
            relief=FLAT,
            font=("Consolas", 10),
        )
        self.log_box.pack(fill=BOTH, expand=True)

    def _status_line(self, parent, label, variable):
        row = Frame(parent, bg=SECTION_BG)
        row.pack(fill=X, pady=1)

        Label(
            row,
            text=label,
            bg=SECTION_BG,
            fg=BODY_TEXT,
            font=("Segoe UI", 10),
            width=14,
            anchor="w",
        ).pack(side=LEFT)

        Label(
            row,
            textvariable=variable,
            bg=SECTION_BG,
            fg=MUTED_TEXT,
            font=("Consolas", 10),
            anchor="w",
        ).pack(side=LEFT, fill=X, expand=True)

    def _run_on_ui(self, callback, *args):
        self.ui_queue.put((callback, args))

    def _pump_ui_queue(self):
        try:
            while True:
                callback, args = self.ui_queue.get_nowait()
                callback(*args)
        except queue.Empty:
            pass

        self.root.after(40, self._pump_ui_queue)

    def _append_log(self, text):
        clean = text.rstrip()
        self.log_box.insert(END, clean + "\n")
        self.log_box.see(END)

        if self.log_file:
            timestamp = time.strftime("%H:%M:%S")
            line = f"[{timestamp}] {clean}\n"
            with self.log_lock:
                try:
                    self.log_file.write(line)
                    self.log_file.flush()
                except OSError:
                    pass

    def log(self, text):
        self._run_on_ui(self._append_log, text)

    def _set_busy(self, busy):
        self.is_busy = busy
        state = "disabled" if busy else "normal"

        self.install_button.configure(state=state)
        self.shortcut_button.configure(state=state)
        self.pin_start_button.configure(state=state)
        self.pin_taskbar_button.configure(state=state)
        self.clean_button.configure(state=state)
        self.reset_config_button.configure(state=state)

    def _run_background(self, work):
        if self.is_busy:
            self.log("Another task is still running. Please wait...")
            return

        self._set_busy(True)

        def runner():
            try:
                work()
            except Exception as exc:
                self.log(f"Task failed: {exc}")
            finally:
                self._run_on_ui(self._set_busy, False)
                self._run_on_ui(self._refresh_dependency_statuses)

        threading.Thread(target=runner, daemon=True, name="launcher-worker").start()

    def _refresh_dependency_statuses(self):
        self.ytdlp_status.set(self._module_state("yt_dlp"))
        self.spotdl_status.set(self._module_state("spotdl"))
        self.dnd_status.set(self._module_state("tkinterdnd2"))
        self.aria2_status.set(self._binary_state(find_aria2c()))
        self.ffmpeg_status.set(self._binary_state(find_ffmpeg()))

    def _module_state(self, module_name):
        found = importlib.util.find_spec(module_name) is not None
        return "Installed" if found else "Missing"

    def _binary_state(self, binary_path):
        if not binary_path:
            return "Missing"
        return os.path.basename(binary_path)

    def _run_command_with_logs(self, command):
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=SCRIPT_DIR,
        )

        assert process.stdout is not None

        for line in process.stdout:
            line = line.rstrip()
            if line:
                self.log(line)

        return_code = process.wait()

        if return_code != 0:
            raise RuntimeError(f"Command failed with exit code {return_code}: {' '.join(command)}")

    def _install_python_package(self, package_name, module_name):
        if importlib.util.find_spec(module_name) is not None:
            self.log(f"{package_name} already installed.")
            return

        self.log(f"Installing {package_name}...")
        self._run_command_with_logs(
            [sys.executable, "-m", "pip", "--disable-pip-version-check", "install", package_name]
        )
        self.log(f"{package_name} installed.")

    def action_auto_install(self):
        def work():
            self.log("Starting full setup install...")

            self._install_python_package("yt-dlp", "yt_dlp")
            self._install_python_package("setuptools", "pkg_resources")
            self._install_python_package("spotdl", "spotdl")
            self._install_python_package("tkinterdnd2", "tkinterdnd2")

            try:
                auto_install_aria2c(self.log)
            except (OSError, urllib.error.URLError, json.JSONDecodeError, RuntimeError, zipfile.BadZipFile) as exc:
                self.log(f"aria2c install skipped: {exc}")

            try:
                auto_install_ffmpeg(self.log)
            except (OSError, urllib.error.URLError, RuntimeError, zipfile.BadZipFile) as exc:
                self.log(f"ffmpeg install skipped: {exc}")

            safe_path = ensure_within_script_dir(EXAMPLE_COLOURS_PATH)
            with open(safe_path, "w", encoding="utf-8") as colours_file:
                colours_file.write(format_example_colours_content(EXAMPLE_COLOURS_CONTENT))
            self.log(f"Reinstalled Example Colours.txt: {safe_path}")

            self.log("Auto install finished.")

        self._run_background(work)

    def action_create_shortcut(self):
        def work():
            if not os.path.isfile(MAIN_SCRIPT_PATH):
                raise FileNotFoundError(f"MainScript.py not found: {MAIN_SCRIPT_PATH}")

            if not os.path.isfile(ICON_PATH):
                raise FileNotFoundError(f"favi.ico not found: {ICON_PATH}")

            target_path = get_pythonw_path()

            if not os.path.isfile(target_path):
                raise FileNotFoundError(f"Python executable not found: {target_path}")

            shortcut_path = os.path.join(desktop_dir(), SHORTCUT_NAME)
            shortcut_args = f'"{MAIN_SCRIPT_PATH}"'
            os.makedirs(os.path.dirname(shortcut_path), exist_ok=True)

            create_shortcut(target_path, shortcut_args, SCRIPT_DIR, ICON_PATH, shortcut_path)
            self.log(f"Desktop shortcut created: {shortcut_path}")

        self._run_background(work)

    def _ensure_start_menu_shortcut(self):
        start_menu_dir = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
        )
        if not start_menu_dir:
            raise RuntimeError("APPDATA is unavailable for Start Menu shortcut creation.")

        os.makedirs(start_menu_dir, exist_ok=True)
        shortcut_path = os.path.join(start_menu_dir, SHORTCUT_NAME)

        target_path = get_pythonw_path()
        if not os.path.isfile(target_path):
            raise FileNotFoundError(f"Python executable not found: {target_path}")

        if not os.path.isfile(MAIN_SCRIPT_PATH):
            raise FileNotFoundError(f"MainScript.py not found: {MAIN_SCRIPT_PATH}")

        if not os.path.isfile(ICON_PATH):
            raise FileNotFoundError(f"favi.ico not found: {ICON_PATH}")

        create_shortcut(
            target_path,
            f'"{MAIN_SCRIPT_PATH}"',
            SCRIPT_DIR,
            ICON_PATH,
            shortcut_path,
        )
        return shortcut_path

    def action_pin_to_start(self):
        def work():
            shortcut_path = self._ensure_start_menu_shortcut()
            self.log(f"Start menu shortcut ready: {shortcut_path}")
            try:
                invoke_shortcut_verb(shortcut_path, ["pin to start", "start pin"])
                self.log("Pin To Start command sent.")
            except subprocess.CalledProcessError:
                self.log(
                    "Pin To Start verb was not available on this Windows build. "
                    "You can pin it manually from the Start menu shortcut."
                )

        self._run_background(work)

    def action_pin_to_taskbar(self):
        def work():
            shortcut_path = self._ensure_start_menu_shortcut()
            self.log(f"Taskbar shortcut ready: {shortcut_path}")
            try:
                invoke_shortcut_verb(shortcut_path, ["pin to taskbar", "taskbar pin"])
                self.log("Pin To Taskbar command sent.")
            except subprocess.CalledProcessError:
                self.log(
                    "Pin To Taskbar verb was not available on this Windows build. "
                    "You can pin it manually from the shortcut context menu."
                )

        self._run_background(work)

    def _remove_directory_if_exists(self, path):
        safe_path = ensure_within_script_dir(path)

        if os.path.isdir(safe_path):
            shutil.rmtree(safe_path)
            self.log(f"Deleted folder: {safe_path}")
        else:
            self.log(f"Folder not found (skipped): {safe_path}")

    def _remove_file_if_exists(self, path):
        safe_path = ensure_within_script_dir(path)

        if os.path.isfile(safe_path):
            os.remove(safe_path)
            self.log(f"Deleted file: {safe_path}")
        else:
            self.log(f"File not found (skipped): {safe_path}")

    def action_purge_files(self):
        def work():
            self.log("Purging launcher files...")
            self._remove_directory_if_exists(PYCACHE_DIR)
            self._remove_directory_if_exists(ARIA2C_INSTALL_DIR)
            self._remove_directory_if_exists(FFMPEG_INSTALL_DIR)
            self._remove_directory_if_exists(SPOTDL_CACHE_DIR)
            self._remove_file_if_exists(EXAMPLE_COLOURS_PATH)
            self._clean_logs_keep_example()
            self.log("Purge files finished.")

        self._run_background(work)

    def action_clean_directory(self):
        # Backwards-compatible alias for any existing hooks.
        self.action_purge_files()

    def _clean_logs_keep_example(self):
        logs_path = ensure_within_script_dir(LOGS_DIR)

        if not os.path.isdir(logs_path):
            self.log(f"Logs folder not found (skipped): {logs_path}")
            return

        deleted_count = 0
        kept_count = 0

        for entry in os.listdir(logs_path):
            entry_path = ensure_within_script_dir(os.path.join(logs_path, entry))

            if not os.path.isfile(entry_path):
                continue

            if is_example_log_name(entry):
                kept_count += 1
                self.log(f"Keeping example log: {entry_path}")
                continue

            os.remove(entry_path)
            deleted_count += 1
            self.log(f"Deleted log: {entry_path}")

        self.log(f"Logs cleanup complete. Deleted {deleted_count}, kept {kept_count}.")

    def action_reset_config_to_defaults(self):
        def work():
            safe_path = ensure_within_script_dir(CONFIG_PATH)
            default_config = load_default_config_template()

            with open(safe_path, "w", encoding="utf-8") as config_file:
                json.dump(default_config, config_file, indent=4)
                config_file.write("\n")

            self.log("Config reset to defaults.")
            self.log(f"Config written to: {safe_path}")
            self.log("Restart launcher to apply accent/theme changes immediately.")

        self._run_background(work)

    def run(self):
        self.root.mainloop()


def hide_console_window():
    try:
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window:
            ctypes.windll.user32.ShowWindow(console_window, SW_HIDE)
    except Exception:
        pass


def main():
    hide_console_window()
    app = DesktopLauncher()
    app.run()


if __name__ == "__main__":
    main()
