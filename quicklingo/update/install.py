from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from quicklingo.paths import app_root

_UPDATER_NAME = "QuickLingoUpdater.exe"
_DETACHED = 0x00000008
_NEW_PROCESS_GROUP = 0x00000200


def updater_exe_path() -> Path:
    return app_root() / _UPDATER_NAME


def updater_available() -> bool:
    return updater_exe_path().is_file()


def copy_updater_to_temp() -> Path:
    from quicklingo.paths import user_data_dir

    source = updater_exe_path()
    if not source.is_file():
        raise FileNotFoundError(f"Updater not found: {source}")

    temp_dir = user_data_dir() / "updates"
    temp_dir.mkdir(parents=True, exist_ok=True)
    dest = temp_dir / _UPDATER_NAME
    shutil.copy2(source, dest)
    return dest


def launch_update(zip_path: Path, install_dir: Path | None = None, pid: int | None = None) -> None:
    if sys.platform != "win32":
        raise OSError("In-app update is supported on Windows only")

    install_dir = install_dir or app_root()
    zip_path = zip_path.resolve()
    if not zip_path.is_file():
        raise FileNotFoundError(f"Update zip not found: {zip_path}")

    updater = copy_updater_to_temp()
    args = [
        str(updater),
        "--install-dir",
        str(install_dir.resolve()),
        "--zip",
        str(zip_path),
        "--restart",
    ]
    if pid is not None:
        args.extend(["--pid", str(pid)])

    subprocess.Popen(
        args,
        cwd=str(updater.parent),
        creationflags=_DETACHED | _NEW_PROCESS_GROUP,
        close_fds=True,
    )
