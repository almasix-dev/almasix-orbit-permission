"""Smith commands for generating abilities and promoting a super admin."""

from __future__ import annotations

from typing import Any

from almasix.console.command import Command

from almasix_orbit_permission.config import PermissionPluginConfig
from almasix_orbit_permission.runtime import run
from almasix_orbit_permission.seeder import generate_for_panel


def _panel_from_id(panel_id: str) -> Any:
    from almasix.orbit import PanelRegistry

    try:
        from almasix.framework.helpers import app

        registry = app(PanelRegistry)
    except Exception:
        from almasix.orbit.panels.panel import PanelRegistry as RegistryCls

        registry = RegistryCls()
    getter = getattr(registry, "get", None)
    if callable(getter):
        panel = getter(panel_id)
        if panel is not None:
            return panel
    all_fn = getattr(registry, "all", None)
    if callable(all_fn):
        for panel in all_fn() or []:
            if getattr(panel, "id", None) == panel_id:
                return panel
    return None


class GeneratePermissionsCommand(Command):
    signature = "orbit-permission:generate {panel=admin}"
    description = "Create permission rows for a panel's resources, pages, and widgets"

    def handle(self) -> int:
        panel_id = str(self.argument("panel") or "admin")
        panel = _panel_from_id(panel_id)
        if panel is None:
            self.error(f"panel {panel_id!r} is not registered")
            return self.FAILURE
        from almasix_orbit_permission.resources import current_plugin

        plugin = current_plugin()
        config = plugin.config if plugin is not None else PermissionPluginConfig()
        store = getattr(plugin, "store", None) if plugin is not None else None
        names = generate_for_panel(panel, config, store=store)
        self.success(f"generated {len(names)} permissions for panel `{panel_id}`")
        return self.SUCCESS


class SuperAdminCommand(Command):
    signature = "orbit-permission:super-admin {user}"
    description = "Assign the super-admin role to a user id or email"

    def handle(self) -> int:
        token = str(self.argument("user") or "").strip()
        if not token:
            self.error("user id or email is required")
            return self.FAILURE
        from almasix_orbit_permission.resources import current_plugin

        plugin = current_plugin()
        config = plugin.config if plugin is not None else PermissionPluginConfig()
        store = getattr(plugin, "store", None) if plugin is not None else None
        if store is not None:
            for row in store.list_users():
                if str(row.get("id")) == token or str(row.get("email") or "") == token:
                    store.sync_user_roles(row["id"], [config.super_admin_role])
                    store.grant_all_to_role(config.super_admin_role)
                    self.success(f"granted `{config.super_admin_role}` to user {token}")
                    return self.SUCCESS
            self.error(f"user {token!r} not found")
            return self.FAILURE
        model = plugin.resolve_user_model() if plugin is not None else None
        if model is None:
            self.error("no user model configured")
            return self.FAILURE
        user = _find_user(model, token)
        if user is None:
            self.error(f"user {token!r} not found")
            return self.FAILURE
        from almasix.permission import Permission, Role

        async def _assign() -> None:
            import inspect

            role = await Role.find_or_create(config.super_admin_role)
            try:
                rows = list(run(Permission.query().get()) or [])
                names = [
                    str(getattr(row, "name", row)) for row in rows if getattr(row, "name", None)
                ]
                if names:
                    synced = role.sync_permissions(*names)
                    if inspect.isawaitable(synced):
                        await synced
            except Exception:
                pass
            assigned = user.assign_role(role)
            if inspect.isawaitable(assigned):
                await assigned

        run(_assign())
        self.success(f"granted `{config.super_admin_role}` to user {token}")
        return self.SUCCESS


def _find_user(model: type[Any], token: str) -> Any:
    try:
        found = run(model.find(token))
        if found is not None:
            return found
        if token.isdigit():
            found = run(model.find(int(token)))
            if found is not None:
                return found
        query = model.query().where("email", token)
        return run(query.first())
    except Exception:
        return None


ORBIT_PERMISSION_COMMANDS = [GeneratePermissionsCommand, SuperAdminCommand]
