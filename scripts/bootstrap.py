#!/usr/bin/env python3
"""Bootstrap script — sets up the platform from a fresh clone.

Usage:
    python scripts/bootstrap.py              # full setup
    python scripts/bootstrap.py --skip-npm   # backend only

Steps:
1. Check Python version
2. Install Python dependencies
3. Copy .env from .env.example if missing
4. Run database migrations
5. Install frontend dependencies (npm)
6. Verify setup
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 11)


def step(msg: str) -> None:
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print(f"{'='*50}")


def check_python() -> bool:
    v = sys.version_info
    if (v.major, v.minor) < MIN_PYTHON:
        print(f"  Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, got {v.major}.{v.minor}.{v.micro}")
        return False
    print(f"  Python {v.major}.{v.minor}.{v.micro} — OK")
    return True


def install_python_deps() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode == 0


def setup_env() -> None:
    env_file = PROJECT_ROOT / ".env"
    example = PROJECT_ROOT / ".env.example"
    if env_file.exists():
        print("  .env already exists — skipping")
    elif example.exists():
        shutil.copy(example, env_file)
        print("  Copied .env.example → .env")
        print("  Edit .env to set OPENAI_API_KEY and other secrets")
    else:
        print("  WARNING: No .env.example found")


def run_migrations() -> bool:
    result = subprocess.run(
        [sys.executable, "-c", "from packages.shared.db.migrate import run_upgrade; run_upgrade()"],
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode == 0


def install_npm() -> bool:
    frontend_dir = PROJECT_ROOT / "apps" / "web" / "frontend"
    if not (frontend_dir / "package.json").exists():
        print("  No frontend package.json — skipping npm install")
        return True
    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        print("  npm not found — skipping frontend install")
        print("  Install Node.js 18+ to enable the frontend")
        return True
    result = subprocess.run([npm_cmd, "install"], cwd=str(frontend_dir))
    return result.returncode == 0


def verify() -> bool:
    result = subprocess.run(
        [sys.executable, "scripts/check_ci_gates.py"],
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("  CI quality gates: PASS")
        return True
    print("  CI quality gates: FAIL")
    print(result.stdout)
    return False


def main() -> int:
    skip_npm = "--skip-npm" in sys.argv

    step("1. Checking Python version")
    if not check_python():
        return 1

    step("2. Installing Python dependencies")
    if not install_python_deps():
        print("  pip install failed")
        return 1
    print("  Dependencies installed")

    step("3. Setting up environment")
    setup_env()

    step("4. Running database migrations")
    if not run_migrations():
        print("  Migration failed — check DATABASE_URL in .env")
        return 1
    print("  Migrations applied")

    if not skip_npm:
        step("5. Installing frontend dependencies")
        if not install_npm():
            print("  npm install failed")
            return 1
        print("  Frontend dependencies installed")
    else:
        step("5. Skipping frontend (--skip-npm)")

    step("6. Verifying setup")
    if not verify():
        print("  WARNING: Verification failed — check output above")

    step("DONE")
    print("  Start the API:      python -m uvicorn apps.api.main:app --port 8010 --reload")
    print("  Start the frontend: cd apps/web/frontend && npm run dev")
    print("  Or use Docker:      docker compose up")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
