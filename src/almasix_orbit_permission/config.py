"""Fluent options for :class:`~almasix_orbit_permission.plugin.PermissionPlugin`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RESOURCE_ABILITIES: tuple[str, ...] = (
    "view_any",
    "view",
    "create",
    "update",
    "delete",
)
SOFT_DELETE_ABILITIES: tuple[str, ...] = ("restore", "force_delete")
PAGE_ABILITIES: tuple[str, ...] = ("view",)
WIDGET_ABILITIES: tuple[str, ...] = ("view",)

ABILITY_LABELS: dict[str, str] = {
    "view_any": "View any",
    "view": "View",
    "create": "Create",
    "update": "Update",
    "delete": "Delete",
    "restore": "Restore",
    "force_delete": "Force delete",
}


@dataclass
class PermissionPluginConfig:
    """Mutable options applied in ``PermissionPlugin.register``."""

    navigation_group: str = "Access"
    super_admin_role: str = "super_admin"
    guard: str | None = None
    register_user_resource: bool = True
    register_role_resource: bool = True
    register_permission_resource: bool = True
    register_widget: bool = True
    exclude: tuple[str, ...] = ()
    extra_permissions: tuple[str, ...] = ()
    user_model: type[Any] | str | None = None
    cluster: type[Any] | str | None = None
    generate_on_boot: bool = False
    store: Any = field(default=None, repr=False)
