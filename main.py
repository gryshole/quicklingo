from pathlib import Path

from dotenv import load_dotenv

from quicklingo.paths import app_root

load_dotenv(app_root() / ".env")

from quicklingo.app import run


if __name__ == "__main__":
    raise SystemExit(run())
