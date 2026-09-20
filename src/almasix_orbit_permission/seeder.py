"""Seed generated permission names into almasix-permission."""

from __future__ import annotations

from typing import Any

from almasix_orbit_permission.config import PermissionPluginConfig
from almasix_orbit_permission.generator import PermissionSpec, discover_panel
from almasix_orbit_permission.runtime import run
from almasix_orbit_permission.store import MemoryStore


def default_guard(config: PermissionPluginConfig) -> str:
    if config.guard:
        return str(config.guard)
    try:
        from almasix.permission.helpers import get_default_guard_name

        return str(get_default_guard_name())
    except Exception:
        return "web"


def generate_into_store(
    specs: list[PermissionSpec],
    store: MemoryStore,
    config: PermissionPluginConfig,
) -> list[str]:
    guard = default_guard(config)
    names: list[str] = []
    for spec in specs:
        store.ensure_permission(spec.name, guard=guard)
        names.append(spec.name)
    store.grant_all_to_role(config.super_admin_role, guard=guard)
    return names


def generate_into_orm(
    specs: list[PermissionSpec],
    config: PermissionPluginConfig,
) -> list[str]:
    from almasix.permission import Permission, Role

    guard = default_guard(config)
    names: list[str] = []

    async def _seed() -> list[str]:
        created: list[str] = []
        for spec in specs:
            await Permission.find_or_create(spec.name, guard)
            created.append(spec.name)
        role = await Role.find_or_create(config.super_admin_role, guard)
        if created:
            await role.sync_permissions(*created)
        return created

    names = run(_seed())
    return names


def generate_for_panel(
    panel: Any,
    config: PermissionPluginConfig,
    *,
    store: MemoryStore | None = None,
) -> list[str]:
    specs = discover_panel(panel, config)
    if store is not None:
        return generate_into_store(specs, store, config)
    try:
        return generate_into_orm(specs, config)
    except Exception:
        fallback = config.store if isinstance(config.store, MemoryStore) else MemoryStore()
        config.store = fallback
        return generate_into_store(specs, fallback, config)
