import ctypes
import os
import sys

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return os.geteuid() == 0  # Linux/macOS fallback


def elevate_self():
    """Re-launch the process with admin rights (Windows)."""
    if sys.platform == "win32":
        cwd = os.getcwd()
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            " ".join([f'"{a}"' for a in sys.argv]),
            cwd, 1
        )
        sys.exit(0)
