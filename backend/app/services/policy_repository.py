"""Policy Repository — reads/writes policy JSON files.

Abstracts policy storage so callers never touch the file system directly.
"""

from __future__ import annotations

import json
import os
from typing import Any


class PolicyRepository:
    """Read/write enterprise policy JSON files."""

    def __init__(self, policies_dir: str):
        self.policies_dir = policies_dir
        os.makedirs(policies_dir, exist_ok=True)

    def _file_path(self, enterprise: str) -> str:
        """Return the JSON file path for a given enterprise."""
        safe_name = enterprise.replace("/", "_").replace("\\", "_")
        return os.path.join(self.policies_dir, f"{safe_name}.json")

    def get_policy(self, enterprise: str = "default") -> dict:
        """Read a policy file. Returns empty dict if not found."""
        path = self._file_path(enterprise)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_policy(self, enterprise: str, policy_data: dict) -> None:
        """Write a policy document to disk."""
        path = self._file_path(enterprise)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(policy_data, f, ensure_ascii=False, indent=2)

    def get_expense_type(self, enterprise: str, expense_code: str) -> dict | None:
        """Look up a single expense type by code. Returns None if not found."""
        policy = self.get_policy(enterprise)
        for et in policy.get("expense_types", []):
            if et.get("code") == expense_code:
                return et
        return None

    def list_enterprises(self) -> list[str]:
        """List available enterprises by scanning JSON files."""
        enterprises = []
        try:
            for fname in os.listdir(self.policies_dir):
                if fname.endswith(".json"):
                    enterprises.append(fname[:-5])  # strip .json
        except FileNotFoundError:
            pass
        if not enterprises:
            enterprises = ["default"]
        return enterprises
