"""Mixin so Orbit ``_can`` resolves against almasix-permission."""

from __future__ import annotations

from typing import Any


class HasOrbitPermissions:
    """Expose the method names Orbit resources call on the authenticated user.

    Mix this in next to ``HasRoles`` on your user model::

        class User(HasOrbitPermissions, HasRoles, AuthenticatableMixin, Model):
            fillable = ("email", "name", "password")
    """

    def has_permission(self, ability: str, record: Any = None) -> bool:
        checker = getattr(self, "check_permission_to", None)
        if callable(checker):
            try:
                return bool(checker(ability))
            except Exception:
                return False
        owned = getattr(self, "permissions", None)
        if isinstance(owned, (set, list, tuple)):
            return ability in owned or "*" in owned
        return False

    def can(self, ability: str, record: Any = None) -> bool:
        return self.has_permission(ability, record)
