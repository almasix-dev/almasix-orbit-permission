"""Dashboard stats for users, roles, and permissions."""

from __future__ import annotations

from typing import Any, ClassVar

from almasix.orbit.widgets import Stat, StatsOverviewWidget

from almasix_orbit_permission.resources import current_plugin
from almasix_orbit_permission.store import MemoryStore


class AccessOverviewWidget(StatsOverviewWidget):
    heading = "Access"
    description = "Users, roles, and abilities on this panel."
    sort = -40
    navigation_label: ClassVar[str | None] = None

    def __init__(self, name: str | None = "access-overview") -> None:
        super().__init__(name)
        self.stats(
            [
                Stat.make("Users").icon("heroicon-o-users").color("primary"),
                Stat.make("Roles").icon("heroicon-o-shield-check").color("warning"),
                Stat.make("Permissions").icon("heroicon-o-key").color("success"),
            ]
        )

    def get_stats(self, **ctx: Any) -> list[Stat]:
        users, roles, permissions = self._counts()
        cards = super().get_stats(**ctx)
        if len(cards) >= 3:
            cards[0].value(users)
            cards[1].value(roles)
            cards[2].value(permissions)
        return cards

    def _counts(self) -> tuple[int, int, int]:
        plugin = current_plugin()
        store = getattr(plugin, "store", None) if plugin is not None else None
        if isinstance(store, MemoryStore):
            return (
                len(store.list_users()),
                len(store.list_roles()),
                len(store.list_permissions()),
            )
        try:
            from almasix.permission import Permission, Role

            from almasix_orbit_permission.runtime import run

            role_n = len(list(run(Role.query().get()) or []))
            perm_n = len(list(run(Permission.query().get()) or []))
        except Exception:
            role_n = perm_n = 0
        user_n = 0
        model = None
        if plugin is not None:
            model = plugin.resolve_user_model()
        if model is not None:
            try:
                from almasix_orbit_permission.runtime import run

                all_fn = getattr(model, "all", None)
                if callable(all_fn):
                    user_n = len(list(run(all_fn()) or []))
            except Exception:
                user_n = 0
        return user_n, role_n, perm_n
