"""Tests for P13-01/P13-02: Docker packaging and bootstrap scripts.

AC-1 (P13-01): Bootstrap scripts create environment and install deps.
AC-2 (P13-01): Bootstrap seeds baseline config.
AC-3 (P13-02): Docker Compose profile runs API, frontend, DB.
AC-4 (P13-02): Non-Docker profile documented and equivalent.
AC-5 (P13-02): Ports, volumes, and service defaults standardized.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# AC-1: Bootstrap scripts exist
# ---------------------------------------------------------------------------

class TestBootstrapScripts:
    def test_bootstrap_py_exists(self):
        assert (PROJECT_ROOT / "scripts" / "bootstrap.py").is_file()

    def test_bootstrap_ps1_exists(self):
        assert (PROJECT_ROOT / "scripts" / "bootstrap.ps1").is_file()

    def test_bootstrap_sh_exists(self):
        assert (PROJECT_ROOT / "scripts" / "bootstrap.sh").is_file()

    def test_bootstrap_checks_python_version(self):
        content = (PROJECT_ROOT / "scripts" / "bootstrap.py").read_text()
        assert "check_python" in content
        assert "3, 11" in content or "MIN_PYTHON" in content

    def test_bootstrap_installs_deps(self):
        content = (PROJECT_ROOT / "scripts" / "bootstrap.py").read_text()
        assert "pip install" in content

    def test_bootstrap_runs_migrations(self):
        content = (PROJECT_ROOT / "scripts" / "bootstrap.py").read_text()
        assert "run_upgrade" in content or "migration" in content

    def test_bootstrap_installs_npm(self):
        content = (PROJECT_ROOT / "scripts" / "bootstrap.py").read_text()
        assert "npm" in content


# ---------------------------------------------------------------------------
# AC-2: Baseline config seeded
# ---------------------------------------------------------------------------

class TestBaselineConfig:
    def test_env_example_exists(self):
        assert (PROJECT_ROOT / ".env.example").is_file()

    def test_env_example_has_required_vars(self):
        content = (PROJECT_ROOT / ".env.example").read_text()
        assert "API_PORT" in content
        assert "DATABASE_URL" in content
        assert "WEB_PORT" in content

    def test_bootstrap_copies_env(self):
        content = (PROJECT_ROOT / "scripts" / "bootstrap.py").read_text()
        assert ".env.example" in content
        assert "setup_env" in content


# ---------------------------------------------------------------------------
# AC-3: Docker Compose profile
# ---------------------------------------------------------------------------

class TestDockerCompose:
    def test_docker_compose_exists(self):
        assert (PROJECT_ROOT / "docker-compose.yml").is_file()

    def test_dockerfile_exists(self):
        assert (PROJECT_ROOT / "Dockerfile").is_file()

    def test_dockerignore_exists(self):
        assert (PROJECT_ROOT / ".dockerignore").is_file()

    def test_compose_has_api_service(self):
        content = (PROJECT_ROOT / "docker-compose.yml").read_text()
        assert "api:" in content

    def test_compose_has_frontend_service(self):
        content = (PROJECT_ROOT / "docker-compose.yml").read_text()
        assert "frontend:" in content

    def test_compose_has_healthcheck(self):
        content = (PROJECT_ROOT / "docker-compose.yml").read_text()
        assert "healthcheck:" in content

    def test_compose_has_restart_policy(self):
        content = (PROJECT_ROOT / "docker-compose.yml").read_text()
        assert "restart:" in content

    def test_dockerfile_uses_non_editable_install(self):
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "-e" not in content or "pip install --no-cache-dir ." in content

    def test_compose_has_volume(self):
        content = (PROJECT_ROOT / "docker-compose.yml").read_text()
        assert "volumes:" in content
        assert "db-data" in content

    def test_dockerfile_has_backend_stage(self):
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "backend" in content
        assert "uvicorn" in content

    def test_dockerfile_has_frontend_stage(self):
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "frontend" in content
        assert "npm" in content

    def test_dockerfile_runs_migrations(self):
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "run_upgrade" in content

    def test_nginx_conf_exists(self):
        assert (PROJECT_ROOT / "ops" / "docker" / "nginx.conf").is_file()

    def test_nginx_proxies_api(self):
        content = (PROJECT_ROOT / "ops" / "docker" / "nginx.conf").read_text()
        assert "proxy_pass http://api:8010" in content

    def test_nginx_spa_fallback(self):
        content = (PROJECT_ROOT / "ops" / "docker" / "nginx.conf").read_text()
        assert "try_files" in content
        assert "index.html" in content


# ---------------------------------------------------------------------------
# AC-4/5: Port standardization
# ---------------------------------------------------------------------------

class TestPortStandardization:
    def test_api_port_in_env_example(self):
        content = (PROJECT_ROOT / ".env.example").read_text()
        assert "API_PORT=8010" in content

    def test_web_port_in_env_example(self):
        content = (PROJECT_ROOT / ".env.example").read_text()
        assert "WEB_PORT=8510" in content

    def test_start_api_reads_env_port(self):
        content = (PROJECT_ROOT / "start_api.py").read_text()
        assert "API_PORT" in content
        assert "8010" in content

    def test_compose_uses_env_ports(self):
        content = (PROJECT_ROOT / "docker-compose.yml").read_text()
        assert "API_PORT" in content
        assert "WEB_PORT" in content

    def test_cors_allows_both_ports(self):
        content = (PROJECT_ROOT / "apps" / "api" / "main.py").read_text()
        assert "5173" in content  # Vite dev
        assert "8510" in content  # Docker/production

    def test_dockerignore_excludes_secrets(self):
        content = (PROJECT_ROOT / ".dockerignore").read_text()
        assert ".env" in content
        assert "node_modules" in content
