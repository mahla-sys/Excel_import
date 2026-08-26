"""Service helpers for recording audit entries.

Importing from this module must not import models at module-load time in a
way that causes circular imports; all model access is lazy.
"""
from __future__ import annotations

from typing import Any


def _client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_audit(
    *,
    actor,
    action,
    entity_type: str = "",
    entity_id: Any = "",
    school=None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    request=None,
    ip_address: str | None = None,
) -> None:
    """Create an AuditLog row without ever failing the caller's request."""
    try:
        from .models import AuditLog

        if school is None and actor is not None:
            school = getattr(actor, "school_tenant", None)

        ip = ip_address
        if ip is None and request is not None:
            ip = _client_ip(request)

        user_agent = ""
        if request is not None:
            user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:300]

        AuditLog.objects.create(
            actor=actor if actor and getattr(actor, "pk", None) else None,
            actor_username=getattr(actor, "username", "") or "",
            school=school,
            action=action,
            entity_type=entity_type,
            entity_id="" if entity_id is None else str(entity_id),
            before_state=before_state,
            after_state=after_state,
            ip_address=ip,
            user_agent=user_agent,
        )
    except Exception:  # pragma: no cover - audit must never break the request
        import logging

        logging.getLogger("apps.audit").exception("Failed to record audit log.")


__all__ = ["AuditAction" if False else "record_audit"]  # type: ignore[unused-ignore]


# Re-export AuditAction so callers can ``from apps.audit.services import AuditAction``
def __getattr__(name):  # pragma: no cover - trivial
    if name == "AuditAction":
        from .models import AuditAction

        return AuditAction
    raise AttributeError(name)
