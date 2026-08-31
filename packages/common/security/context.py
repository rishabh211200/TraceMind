"""Tenant execution context and contextvars propagation across async tasks."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

from packages.domain.security import Permission, Role, TenantContext

# Thread-safe and asyncio-safe context variable holding the active execution context
_tenant_context_var: ContextVar[TenantContext | None] = ContextVar("tenant_context", default=None)


def get_current_tenant_context() -> TenantContext:
    """Retrieve the active TenantContext for the current execution thread or task.

    If no context is active, returns a default fallback context for unauthenticated or system operations.
    """
    ctx = _tenant_context_var.get()
    if ctx is None:
        return TenantContext(
            tenant_id="tenant_system",
            user_id="usr_system",
            email="system@tracemind.internal",
            roles=[Role.PLATFORM_ADMIN],
            permissions=set(Permission),
            is_authenticated=False,
            is_platform_admin=False,
        )
    return ctx



def set_current_tenant_context(ctx: TenantContext) -> Token[TenantContext | None]:
    """Set the active TenantContext and return a token for resetting."""
    return _tenant_context_var.set(ctx)


def reset_current_tenant_context(token: Token[TenantContext | None]) -> None:
    """Reset the TenantContext to its previous state."""
    _tenant_context_var.reset(token)


class with_tenant_context:
    """Context manager for scoping an asynchronous block to a specific TenantContext."""

    def __init__(self, context: TenantContext) -> None:
        self.context = context
        self._token: Token[TenantContext | None] | None = None

    def __enter__(self) -> TenantContext:
        self._token = set_current_tenant_context(self.context)
        return self.context

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token is not None:
            reset_current_tenant_context(self._token)

    async def __aenter__(self) -> TenantContext:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)
