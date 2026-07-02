"""Policy lifecycle service — state machine guard, version activation, transition audit trail.

Architecture (see docs/superpowers/specs/2026-07-02-architecture-refactoring-design.md):

  3 states + internal sub-statuses:
    DRAFT → PUBLISHED → ARCHIVED
    ARCHIVED → PUBLISHED (activate / rollback)
    PUBLISHED → PUBLISHED (no-op)

  All state changes are recorded in policy_transitions for auditability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.enums import (
    PolicyStatus,
    assert_transition_allowed,
    InvalidPolicyTransitionError,
)
from app.infrastructure.orm import PolicyVersion, PolicyTransition

logger = logging.getLogger(__name__)


@dataclass
class VersionActivationResult:
    """Result of a version activation call."""
    success: bool
    message: str = ""
    previous_active_version_id: Optional[int] = None
    transition_id: Optional[int] = None


class PolicyLifecycleService:
    """Policy lifecycle management: state guards, version activation, audit.

    Usage::

        lifecycle = PolicyLifecycleService(db_session)
        result = lifecycle.activate_version(policy_id=1, version_id=2, actor_id=1)
        if result.success:
            print(f"Version activated: {result.message}")
    """

    def __init__(self, db: Session):
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def activate_version(
        self,
        policy_id: int,
        version_id: int,
        actor_id: int = 0,
    ) -> VersionActivationResult:
        """Activate *version_id* as the current published version.

        Behaviour depends on the target version's current state:

        * **DRAFT**     — check ``policy_json`` is present, then publish.
        * **ARCHIVED**  — reactivate (rollback) to published.
        * **PUBLISHED** — no-op (already active).

        Side effects:
        * Any previously-active version → ``ARCHIVED``.
        * ``Policy.current_version_id`` is updated.
        * A ``PolicyTransition`` record is written.
        """
        version = self._get_version(version_id)
        if version is None:
            return VersionActivationResult(
                success=False,
                message=f"Version {version_id} not found",
            )

        # Already active — no-op
        if version.status == PolicyStatus.PUBLISHED:
            return VersionActivationResult(
                success=True,
                message="Version is already active",
            )

        # Guard: DRAFT must have policy_json
        if version.status == PolicyStatus.DRAFT and version.policy_json is None:
            raise ValueError(
                "Cannot activate draft version: policy_json is required. "
                "Run normalize first."
            )

        # Guard: check transition is legal
        assert_transition_allowed(version.status, PolicyStatus.PUBLISHED)

        # Resolve the policy if not explicitly provided
        if policy_id == 0:
            policy_id = version.policy_id

        # Archive any currently-active version
        previous_id = None
        previous_active = self._get_current_active_version(policy_id)
        if previous_active and previous_active.id != version_id:
            previous_active.status = PolicyStatus.ARCHIVED
            previous_active.archived_at = datetime.utcnow()
            previous_id = previous_active.id
            self._record_transition(
                entity_type="policy_version",
                entity_id=str(previous_active.id),
                from_status=PolicyStatus.PUBLISHED.value,
                to_status=PolicyStatus.ARCHIVED.value,
                triggered_by="system_supersede",
                actor_id=actor_id,
            )

        # Activate target version
        old_status = version.status
        version.status = PolicyStatus.PUBLISHED
        version.published_at = datetime.utcnow()
        version.sub_status = None  # clear internal sub-status on publish

        # Update parent Policy record
        from app.infrastructure.orm import Policy
        policy = self._db.query(Policy).filter(Policy.id == policy_id).first()
        if policy:
            policy.status = PolicyStatus.PUBLISHED
            policy.current_version_id = version.id

        trans = self._record_transition(
            entity_type="policy_version",
            entity_id=str(version.id),
            from_status=old_status.value if old_status else None,
            to_status=PolicyStatus.PUBLISHED.value,
            triggered_by="user_activate",
            actor_id=actor_id,
        )

        self._db.flush()

        return VersionActivationResult(
            success=True,
            message=f"Version {version_id} ({old_status.value} → published)",
            previous_active_version_id=previous_id,
            transition_id=trans.id if trans else None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_version(self, version_id: int) -> Optional[PolicyVersion]:
        return (
            self._db.query(PolicyVersion)
            .filter(PolicyVersion.id == version_id)
            .first()
        )

    def _get_current_active_version(self, policy_id: int) -> Optional[PolicyVersion]:
        return (
            self._db.query(PolicyVersion)
            .filter(
                PolicyVersion.policy_id == policy_id,
                PolicyVersion.status == PolicyStatus.PUBLISHED,
            )
            .first()
        )

    def _record_transition(
        self,
        entity_type: str,
        entity_id: str,
        from_status: Optional[str],
        to_status: str,
        triggered_by: str,
        actor_id: int,
    ) -> PolicyTransition:
        trans = PolicyTransition(
            entity_type=entity_type,
            entity_id=entity_id,
            from_status=from_status,
            to_status=to_status,
            triggered_by=triggered_by,
            actor_id=actor_id if actor_id else None,
            metadata_json=None,
        )
        self._db.add(trans)
        return trans
