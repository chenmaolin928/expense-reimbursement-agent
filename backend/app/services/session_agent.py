"""Session-level LLM instance manager.

Each chat session gets its own SessionAgent with isolated context.
Unused sessions are evicted via LRU to control memory.
"""

import time
import threading
from app.infrastructure.llm_client import get_model
from app.config import settings


class SessionAgent:
    """Per-session LLM wrapper with bounded message buffer."""

    def __init__(self, session_id: str, max_context_tokens: int = 8000):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_used = time.time()
        self._model = get_model()
        self._max_tokens = max_context_tokens
        self._lock = threading.Lock()

    def touch(self) -> None:
        self.last_used = time.time()

    def get_model(self):
        """Return the session-scoped model (with bound tools)."""
        self.touch()
        return self._model

    def estimate_tokens(self, messages: list) -> int:
        """Rough token estimate: ~4 chars per token for Chinese, ~3 for English."""
        total = 0
        for m in messages:
            content = str(getattr(m, "content", "") or "")
            total += max(len(content) // 3, 1)
        return total

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_used


class SessionAgentManager:
    """Manages per-session SessionAgent instances with LRU eviction."""

    _instances: dict[str, SessionAgent] = {}
    _lock = threading.Lock()
    _max_sessions: int = 50
    _max_idle_seconds: int = 3600  # 1 hour

    @classmethod
    def get_or_create(cls, session_id: str) -> SessionAgent:
        """Get or create a SessionAgent for this session."""
        with cls._lock:
            if session_id in cls._instances:
                sa = cls._instances[session_id]
                sa.touch()
                return sa

            # Evict if over limit
            if len(cls._instances) >= cls._max_sessions:
                cls._evict_lru()

            sa = SessionAgent(session_id)
            cls._instances[session_id] = sa
            return sa

    @classmethod
    def get(cls, session_id: str) -> SessionAgent | None:
        with cls._lock:
            return cls._instances.get(session_id)

    @classmethod
    def remove(cls, session_id: str) -> None:
        with cls._lock:
            cls._instances.pop(session_id, None)

    @classmethod
    def cleanup(cls) -> int:
        """Remove sessions idle longer than max_idle_seconds. Returns count removed."""
        removed = 0
        with cls._lock:
            stale = [
                sid for sid, sa in cls._instances.items()
                if sa.idle_seconds > cls._max_idle_seconds
            ]
            for sid in stale:
                cls._instances.pop(sid, None)
                removed += 1
        return removed

    @classmethod
    def _evict_lru(cls) -> None:
        """Evict the least-recently-used session."""
        if not cls._instances:
            return
        oldest_id = min(cls._instances, key=lambda sid: cls._instances[sid].last_used)
        cls._instances.pop(oldest_id, None)

    @classmethod
    def stats(cls) -> dict:
        with cls._lock:
            return {
                "active_sessions": len(cls._instances),
                "max_sessions": cls._max_sessions,
                "max_idle_seconds": cls._max_idle_seconds,
            }
