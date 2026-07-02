"""Tests for PolicyLifecycleService — state guards, version activation, audit."""
import pytest
from unittest.mock import Mock, patch
from app.domain.enums import PolicyStatus, InvalidPolicyTransitionError
from app.services.policy_lifecycle import PolicyLifecycleService


@pytest.fixture
def lifecycle():
    db = Mock(spec_set=["query", "add", "flush"])
    db.add = Mock()
    db.flush = Mock()
    return PolicyLifecycleService(db=db)


def make_mock_version(id=1, policy_id=1, status=PolicyStatus.DRAFT, policy_json=None):
    v = Mock(spec=["id", "policy_id", "status", "policy_json", "published_at", "archived_at", "sub_status"])
    v.id = id
    v.policy_id = policy_id
    v.status = status
    v.policy_json = policy_json
    v.published_at = None
    v.archived_at = None
    v.sub_status = None
    return v


def make_mock_policy(id=1, status=PolicyStatus.PUBLISHED, current_version_id=1):
    p = Mock(spec=["id", "status", "current_version_id"])
    p.id = id
    p.status = status
    p.current_version_id = current_version_id
    return p


class TestActivateVersion:
    def test_activate_archived_version_success(self, lifecycle):
        """ARCHIVED → PUBLISHED should succeed and archive current active."""
        version = make_mock_version(id=1, policy_id=1, status=PolicyStatus.ARCHIVED, policy_json={"valid": True})
        previous = make_mock_version(id=2, policy_id=1, status=PolicyStatus.PUBLISHED, policy_json={"valid": True})

        lifecycle._get_version = Mock(return_value=version)
        lifecycle._get_current_active_version = Mock(return_value=previous)
        lifecycle._record_transition = Mock()

        with patch("app.infrastructure.orm.Policy") as MockPolicy:
            mock_policy = make_mock_policy(id=1)
            lifecycle._db.query.return_value.filter.return_value.first.return_value = mock_policy

            result = lifecycle.activate_version(policy_id=1, version_id=1, actor_id=1)

        assert result.success is True
        assert version.status == PolicyStatus.PUBLISHED
        assert previous.status == PolicyStatus.ARCHIVED
        assert result.previous_active_version_id == 2

    def test_activate_draft_version_success(self, lifecycle):
        """DRAFT with policy_json → PUBLISHED should succeed."""
        version = make_mock_version(id=3, policy_id=2, status=PolicyStatus.DRAFT, policy_json={"valid": True})

        lifecycle._get_version = Mock(return_value=version)
        lifecycle._get_current_active_version = Mock(return_value=None)
        lifecycle._record_transition = Mock()

        with patch("app.infrastructure.orm.Policy") as MockPolicy:
            mock_policy = make_mock_policy(id=2)
            lifecycle._db.query.return_value.filter.return_value.first.return_value = mock_policy

            result = lifecycle.activate_version(policy_id=2, version_id=3, actor_id=1)

        assert result.success is True
        assert version.status == PolicyStatus.PUBLISHED
        assert result.previous_active_version_id is None

    def test_activate_published_is_noop(self, lifecycle):
        """PUBLISHED → PUBLISHED should be no-op."""
        version = make_mock_version(id=4, status=PolicyStatus.PUBLISHED)

        lifecycle._get_version = Mock(return_value=version)

        result = lifecycle.activate_version(policy_id=1, version_id=4, actor_id=1)

        assert result.success is True
        assert version.status == PolicyStatus.PUBLISHED  # unchanged
        assert result.message == "Version is already active"

    def test_activate_draft_without_policy_json_raises(self, lifecycle):
        """DRAFT without policy_json should raise ValueError."""
        version = make_mock_version(id=5, status=PolicyStatus.DRAFT, policy_json=None)

        lifecycle._get_version = Mock(return_value=version)

        with pytest.raises(ValueError, match="policy_json is required"):
            lifecycle.activate_version(policy_id=1, version_id=5, actor_id=1)

    def test_activate_nonexistent_version(self, lifecycle):
        """Non-existent version should return failure."""
        lifecycle._get_version = Mock(return_value=None)

        result = lifecycle.activate_version(policy_id=1, version_id=999, actor_id=1)

        assert result.success is False
        assert "not found" in result.message.lower()


class TestStateGuard:
    def test_invalid_transition_published_to_draft_raises(self):
        """PUBLISHED → DRAFT is illegal."""
        with pytest.raises(InvalidPolicyTransitionError):
            from app.domain.enums import assert_transition_allowed
            assert_transition_allowed(PolicyStatus.PUBLISHED, PolicyStatus.DRAFT)

    def test_invalid_transition_archived_to_draft_raises(self):
        """ARCHIVED → DRAFT is illegal."""
        with pytest.raises(InvalidPolicyTransitionError):
            from app.domain.enums import assert_transition_allowed
            assert_transition_allowed(PolicyStatus.ARCHIVED, PolicyStatus.DRAFT)

    def test_valid_transitions_succeed(self):
        """All valid transitions should pass."""
        from app.domain.enums import assert_transition_allowed

        # These should not raise
        assert_transition_allowed(PolicyStatus.DRAFT, PolicyStatus.PUBLISHED)
        assert_transition_allowed(PolicyStatus.DRAFT, PolicyStatus.ARCHIVED)
        assert_transition_allowed(PolicyStatus.PUBLISHED, PolicyStatus.ARCHIVED)
        assert_transition_allowed(PolicyStatus.ARCHIVED, PolicyStatus.PUBLISHED)


class TestRecordTransition:
    def test_transition_record_created(self, lifecycle):
        """_record_transition should create a PolicyTransition and add to session."""
        from app.infrastructure.orm import PolicyTransition

        result = lifecycle._record_transition(
            entity_type="policy_version",
            entity_id="42",
            from_status="draft",
            to_status="published",
            triggered_by="user_activate",
            actor_id=1,
        )

        assert isinstance(result, PolicyTransition)
        assert result.entity_type == "policy_version"
        assert result.entity_id == "42"
        assert result.from_status == "draft"
        assert result.to_status == "published"
        assert result.triggered_by == "user_activate"
        lifecycle._db.add.assert_called_once_with(result)
