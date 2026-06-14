import os
import platform
import shutil
import subprocess
from pathlib import Path


def _sample_path_binaries(max_count: int = 80) -> list[str]:
    """Collect a deduplicated sample of binaries available on PATH."""
    seen: set[str] = set()
    bins: list[str] = []
    for dir_str in os.environ.get("PATH", "").split(os.pathsep):
        d = Path(dir_str)
        if not d.is_dir():
            continue
        try:
            for entry in sorted(d.iterdir()):
                if entry.is_file() and os.access(entry, os.X_OK):
                    name = entry.name
                    if name not in seen:
                        seen.add(name)
                        bins.append(name)
                        if len(bins) >= max_count:
                            return bins
        except PermissionError:
            continue
    return bins


def _git_branch() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_context() -> str:
    u = platform.uname()
    os_name = u.system       # Darwin / Linux / Windows
    os_version = u.release   # e.g. 24.3.0
    arch = u.machine         # arm64 / x86_64

    # Friendlier OS label
    if os_name == "Darwin":
        mac_ver = platform.mac_ver()[0]
        os_label = f"macOS {mac_ver} ({arch})"
    else:
        os_label = f"{os_name} {os_version} ({arch})"

    shell = Path(os.environ.get("SHELL", "unknown")).name
    cwd = os.getcwd()

    pkg_managers = [p for p in ["brew", "pip3", "pip", "npm", "yarn", "cargo", "apt", "apt-get", "dnf", "pacman"] if shutil.which(p)]

    bins = _sample_path_binaries()

    lines = [
        f"OS: {os_label}",
        f"Shell: {shell}",
        f"CWD: {cwd}",
    ]
    if pkg_managers:
        lines.append(f"Package managers: {', '.join(pkg_managers)}")

    branch = _git_branch()
    if branch:
        lines.append(f"Git branch: {branch}")

    if bins:
        lines.append(f"Installed tools (PATH sample): {', '.join(bins)}")

    return "\n".join(lines)
