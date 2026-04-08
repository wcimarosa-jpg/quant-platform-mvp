#!/usr/bin/env python3
"""Seed default local user accounts.

Creates admin, researcher, and reviewer accounts for local development.
Safe to run multiple times — skips users that already exist.

Usage:
    python scripts/seed_users.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.shared.auth import create_user
from packages.shared.db.engine import SessionLocal
from packages.shared.db.models import Base

DEFAULT_USERS = [
    {
        "email": "admin@egg.local",
        "display_name": "Admin User",
        "password": "password",
        "role": "admin",
    },
    {
        "email": "researcher@egg.local",
        "display_name": "Research Lead",
        "password": "password",
        "role": "researcher",
    },
    {
        "email": "reviewer@egg.local",
        "display_name": "QA Reviewer",
        "password": "password",
        "role": "reviewer",
    },
]


def seed_users() -> list[str]:
    """Create default users. Returns list of created emails."""
    db = SessionLocal()
    created = []
    try:
        for user_data in DEFAULT_USERS:
            try:
                user = create_user(
                    db,
                    email=user_data["email"],
                    display_name=user_data["display_name"],
                    password=user_data["password"],
                    role=user_data["role"],
                )
                created.append(user.email)
                print(f"  Created: {user.email} ({user.role})")
            except ValueError:
                print(f"  Exists:  {user_data['email']} — skipped")
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"  Error: {exc}")
    finally:
        db.close()
    return created


def main() -> int:
    print("Seeding default users...")
    created = seed_users()
    print(f"\n  {len(created)} new user(s) created.")
    print("  Login credentials: email / password")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
