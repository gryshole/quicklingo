"""Standalone updater for QuickLingo onedir installs (Windows)."""
from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
MB_OK = 0x00000000
MB_ICONERROR = 0x00000010

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)


def _log_path() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        base = Path(app_data) / "QuickLingo" / "logs"
    else:
        base = Path.home() / ".quicklingo" / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base / "updater.log"


def log(message: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{stamp}] {message}\n"
    try:
        with _log_path().open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def show_error(title: str, message: str) -> None:
    user32.MessageBoxW(None, message, title, MB_OK | MB_ICONERROR)


def wait_for_pid(pid: int, timeout_ms: int = 90000) -> bool:
    if pid <= 0:
        return True
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        log(f"OpenProcess failed for pid={pid}, assuming process exited")
        return True
    try:
        result = kernel32.WaitForSingleObject(handle, timeout_ms)
        if result == WAIT_OBJECT_0:
            log(f"Process {pid} exited")
            return True
        if result == WAIT_TIMEOUT:
            log(f"Timed out waiting for pid={pid}")
            return False
        log(f"WaitForSingleObject returned {result} for pid={pid}")
        return False
    finally:
        kernel32.CloseHandle(handle)


def _validated_install_dir(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_dir():
        raise ValueError(f"Install directory not found: {resolved}")
    exe = resolved / "QuickLingo.exe"
    if not exe.is_file():
        raise ValueError(f"QuickLingo.exe not found in install directory: {resolved}")
    return resolved


def _validated_zip(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.suffix.lower() != ".zip":
        raise ValueError(f"Update file must be a .zip: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"Update zip not found: {resolved}")
    return resolved


def _safe_extract_zip(archive: zipfile.ZipFile, dest_dir: Path) -> None:
    dest_root = dest_dir.resolve()
    for member in archive.namelist():
        if member.endswith("/"):
            continue
        target = (dest_root / member).resolve()
        try:
            target.relative_to(dest_root)
        except ValueError as exc:
            raise ValueError(f"Unsafe path in update zip: {member!r}") from exc
    archive.extractall(dest_root)


def extract_zip(zip_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        _safe_extract_zip(archive, dest_dir)

    entries = list(dest_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        nested = entries[0]
        if (nested / "QuickLingo.exe").is_file():
            return nested
    return dest_dir


def _copy_tree(source: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)


def _copy_file(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def apply_update(install_dir: Path, extracted_root: Path) -> None:
    install_dir = install_dir.resolve()
    extracted_root = extracted_root.resolve()

    exe_name = "QuickLingo.exe"
    updater_name = "QuickLingoUpdater.exe"
    internal_name = "_internal"
    config_name = "config_data"

    for required in (exe_name, internal_name):
        if not (extracted_root / required).exists():
            raise FileNotFoundError(f"Update package missing {required}")

    internal_bak = install_dir / f"{internal_name}.bak"
    if internal_bak.exists():
        shutil.rmtree(internal_bak)

    current_internal = install_dir / internal_name
    if current_internal.exists():
        log(f"Renaming {current_internal} -> {internal_bak}")
        current_internal.rename(internal_bak)

    try:
        log(f"Copying {exe_name}")
        _copy_file(extracted_root / exe_name, install_dir / exe_name)

        if (extracted_root / updater_name).is_file():
            log(f"Copying {updater_name}")
            _copy_file(extracted_root / updater_name, install_dir / updater_name)

        log(f"Copying {internal_name}")
        _copy_tree(extracted_root / internal_name, install_dir / internal_name)

        source_config = extracted_root / config_name
        if source_config.is_dir():
            log(f"Merging {config_name}")
            dest_config = install_dir / config_name
            dest_config.mkdir(parents=True, exist_ok=True)
            for item in source_config.rglob("*"):
                rel = item.relative_to(source_config)
                target = dest_config / rel
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
    except Exception:
        if internal_bak.exists() and not current_internal.exists():
            log("Restore _internal from backup after failure")
            internal_bak.rename(current_internal)
        raise
    finally:
        if internal_bak.exists():
            log(f"Removing backup {internal_bak}")
            shutil.rmtree(internal_bak, ignore_errors=True)


def restart_app(install_dir: Path) -> None:
    validated = _validated_install_dir(install_dir)
    exe = validated / "QuickLingo.exe"
    log(f"Restarting {exe}")
    subprocess.Popen(
        [str(exe)],
        cwd=str(validated),
        creationflags=0x00000008,
        close_fds=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="QuickLingo updater")
    parser.add_argument("--install-dir", required=True)
    parser.add_argument("--zip", required=True)
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()

    install_dir = _validated_install_dir(Path(args.install_dir))
    zip_path = _validated_zip(Path(args.zip))
    log(f"Updater started install_dir={install_dir} zip={zip_path} pid={args.pid}")

    try:
        if args.pid:
            if not wait_for_pid(args.pid):
                raise TimeoutError("QuickLingo did not exit in time")

        temp_root = Path(os.environ.get("TEMP", ".")) / "QuickLingo" / f"extract-{int(time.time())}"
        log(f"Extracting to {temp_root}")
        extracted = extract_zip(zip_path, temp_root)
        apply_update(install_dir, extracted)
        shutil.rmtree(temp_root, ignore_errors=True)

        if args.restart:
            restart_app(install_dir)
        log("Update completed successfully")
        return 0
    except Exception as exc:
        log(f"Update failed: {exc!r}")
        show_error("QuickLingo update failed", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
