"""Minimal panel wiring for almasix-orbit-permission (memory store, no database)."""

from almasix.orbit import Panel, PanelRegistry, Resource
from almasix_orbit_permission import PermissionPlugin


class PostResource(Resource):
    slug = "posts"

    @classmethod
    def get_permission_prefixes(cls) -> list[str]:
        return ["view_any", "view", "create", "update", "delete", "publish"]


def register_admin_panel(registry: PanelRegistry) -> Panel:
    panel = (
        Panel.make("admin")
        .path("admin")
        .login(False)
        .resources([PostResource])
        .plugin(
            PermissionPlugin.make()
            .navigation_group("Access")
            .memory()
            .generate_on_boot()
        )
    )
    registry.register(panel)
    return panel
