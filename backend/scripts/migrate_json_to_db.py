"""Migrate policy JSON files to the database.

Usage:
    cd backend && python scripts/migrate_json_to_db.py

Idempotent: skips enterprises that already have a published Policy.
"""

import sys
import os
import json
from datetime import datetime, timezone

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import engine, Base, SessionLocal
from app.infrastructure.orm import Policy, PolicyVersion
from app.domain.enums import PolicyStatus
from app.config import settings


def migrate():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    policies_dir = settings.policy.policies_dir
    if not os.path.isdir(policies_dir):
        print(f"Policies directory not found: {policies_dir}")
        return

    json_files = [f for f in os.listdir(policies_dir) if f.endswith(".json")]
    if not json_files:
        print("No .json policy files found.")
        return

    db = SessionLocal()
    try:
        migrated = 0
        skipped = 0

        for fname in json_files:
            enterprise = fname[:-5]  # strip .json
            filepath = os.path.join(policies_dir, fname)

            # Check if already migrated (idempotent)
            existing = db.query(Policy).filter(
                Policy.enterprise == enterprise,
                Policy.status == PolicyStatus.PUBLISHED,
            ).first()
            if existing:
                print(f"  SKIP {enterprise}: already has published policy (id={existing.id})")
                skipped += 1
                continue

            # Read JSON
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    policy_json = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"  ERROR {enterprise}: {e}")
                continue

            name = policy_json.get("description", fname) or enterprise
            description = policy_json.get("description", "")

            # Create Policy
            policy = Policy(
                name=name[:200],
                description=description,
                policy_type="expense",
                status=PolicyStatus.PUBLISHED,
                enterprise=enterprise,
                created_by=1,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(policy)
            db.flush()

            # Create PolicyVersion
            version = PolicyVersion(
                policy_id=policy.id,
                version_number=1,
                pdf_filename=None,
                pdf_content=None,
                ai_draft=None,
                policy_json=policy_json,
                status=PolicyStatus.PUBLISHED,
                created_by=1,
                created_at=datetime.now(timezone.utc),
                published_at=datetime.now(timezone.utc),
            )
            db.add(version)
            db.flush()

            # Link current version
            policy.current_version_id = version.id
            db.commit()

            print(f"  OK {enterprise}: policy_id={policy.id}, version_id={version.id}")
            migrated += 1

        print(f"\nDone. Migrated: {migrated}, Skipped: {skipped}")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
