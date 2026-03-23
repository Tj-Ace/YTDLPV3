import os
import subprocess
import sys


SHORTCUT_NAME = "YTDLPV3.lnk"


def script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def desktop_dir():
    return os.path.join(os.path.expanduser("~"), "Desktop")


def create_shortcut(target_path, icon_path, shortcut_path):
    escaped_target = target_path.replace("'", "''")
    escaped_icon = icon_path.replace("'", "''")
    escaped_shortcut = shortcut_path.replace("'", "''")
    escaped_workdir = os.path.dirname(target_path).replace("'", "''")

    powershell_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{escaped_shortcut}')
$Shortcut.TargetPath = '{escaped_target}'
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


def main():
    base_dir = script_dir()
    target_path = os.path.join(base_dir, "MainScript.py")
    icon_path = os.path.join(base_dir, "favi.ico")
    shortcut_path = os.path.join(desktop_dir(), SHORTCUT_NAME)

    if not os.path.isfile(target_path):
        print(f"MainScript.py not found: {target_path}")
        sys.exit(1)

    if not os.path.isfile(icon_path):
        print(f"favi.ico not found: {icon_path}")
        sys.exit(1)

    os.makedirs(os.path.dirname(shortcut_path), exist_ok=True)
    create_shortcut(target_path, icon_path, shortcut_path)
    print(f"Created shortcut: {shortcut_path}")


if __name__ == "__main__":
    main()
