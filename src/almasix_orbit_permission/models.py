"""ORM wrappers so form extras (permissions / roles) survive Orbit create/save."""

from __future__ import annotations

from typing import Any

from almasix_orbit_permission.runtime import run

_MISSING = object()


def _as_name_list(value: Any) -> list[str]:
    if value in (None, _MISSING):
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _copy_fillable(model: type[Any], *extra: str) -> tuple[str, ...]:
    current = tuple(getattr(model, "fillable", ()) or ())
    added = tuple(name for name in extra if name not in current)
    return current + added


def _pop_virtual(attrs: dict[str, Any], key: str) -> list[str] | None:
    if key not in attrs:
        return None
    return _as_name_list(attrs.pop(key))


def bind_role_model(role_cls: type[Any] | None = None) -> type[Any]:
    """Subclass ``Role`` so ``permissions`` on the form is synced after write."""
    if role_cls is None:
        from almasix.permission import Role

        role_cls = Role

    class ManagedRole(role_cls):  # type: ignore[misc,valid-type]
        fillable = _copy_fillable(role_cls, "permissions")

        @classmethod
        async def create(cls, attributes: dict[str, Any] | None = None, **kwargs: Any) -> Any:
            attrs = {**(attributes or {}), **kwargs}
            names = _pop_virtual(attrs, "permissions")
            role = await super().create(attrs)
            if names is not None:
                await role.sync_permissions(*names)
            return role

        async def save(self) -> Any:
            names = _MISSING
            raw = self.__dict__.get("permissions", _MISSING)
            if isinstance(raw, (list, tuple, set, str)):
                names = _as_name_list(raw)
                self.__dict__.pop("permissions", None)
            result = await super().save()
            if names is not _MISSING:
                await self.sync_permissions(*names)
            return result

        def get_attributes(self) -> dict[str, Any]:
            getter = getattr(super(), "get_attributes", None)
            attrs = dict(getter() if callable(getter) else {})
            if not attrs:
                attrs = {
                    key: value
                    for key, value in self.__dict__.items()
                    if not str(key).startswith("_")
                }
            try:
                perms = run(self.get_all_permissions())
                attrs["permissions"] = sorted(
                    {str(getattr(item, "name", item)) for item in (perms or [])}
                )
            except Exception:
                raw = self.__dict__.get("permissions")
                if isinstance(raw, (list, tuple)):
                    attrs["permissions"] = list(raw)
            return attrs

    ManagedRole.__name__ = "ManagedRole"
    ManagedRole.__qualname__ = "ManagedRole"
    return ManagedRole


def bind_permission_model(permission_cls: type[Any] | None = None) -> type[Any]:
    if permission_cls is None:
        from almasix.permission import Permission

        permission_cls = Permission
    return permission_cls


def bind_user_model(user_cls: type[Any]) -> type[Any]:
    """Subclass the app user so ``roles`` / ``permissions`` lists persist."""

    class ManagedUser(user_cls):  # type: ignore[misc,valid-type]
        fillable = _copy_fillable(user_cls, "roles", "permissions")

        @classmethod
        async def create(cls, attributes: dict[str, Any] | None = None, **kwargs: Any) -> Any:
            attrs = {**(attributes or {}), **kwargs}
            roles = _pop_virtual(attrs, "roles")
            perms = _pop_virtual(attrs, "permissions")
            user = await super().create(attrs)
            if roles is not None and hasattr(user, "sync_roles"):
                await user.sync_roles(*roles)
            if perms is not None and hasattr(user, "sync_permissions"):
                await user.sync_permissions(*perms)
            return user

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

        async def save(self) -> Any:
            roles = _MISSING
            perms = _MISSING
            raw_roles = self.__dict__.get("roles", _MISSING)
            raw_perms = self.__dict__.get("permissions", _MISSING)
            if isinstance(raw_roles, (list, tuple, set, str)):
                roles = _as_name_list(raw_roles)
                self.__dict__.pop("roles", None)
            if isinstance(raw_perms, (list, tuple, set, str)):
                perms = _as_name_list(raw_perms)
                self.__dict__.pop("permissions", None)
            result = await super().save()
            if roles is not _MISSING and hasattr(self, "sync_roles"):
                await self.sync_roles(*roles)
            if perms is not _MISSING and hasattr(self, "sync_permissions"):
                await self.sync_permissions(*perms)
            return result

        def get_attributes(self) -> dict[str, Any]:
            getter = getattr(super(), "get_attributes", None)
            attrs = dict(getter() if callable(getter) else {})
            if not attrs:
                attrs = {
                    key: value
                    for key, value in self.__dict__.items()
                    if not str(key).startswith("_")
                }
            try:
                if hasattr(self, "get_role_names"):
                    attrs["roles"] = list(run(self.get_role_names()) or [])
            except Exception:
                raw = self.__dict__.get("roles")
                if isinstance(raw, (list, tuple)):
                    attrs["roles"] = list(raw)
            try:
                if hasattr(self, "get_all_permissions"):
                    owned = run(self.get_all_permissions())
                    attrs["permissions"] = sorted(
                        {str(getattr(item, "name", item)) for item in (owned or [])}
                    )
            except Exception:
                raw = self.__dict__.get("permissions")
                if isinstance(raw, (list, tuple)):
                    attrs["permissions"] = list(raw)
            return attrs

    ManagedUser.__name__ = getattr(user_cls, "__name__", "ManagedUser")
    ManagedUser.__qualname__ = f"Managed{ManagedUser.__name__}"
    return ManagedUser
