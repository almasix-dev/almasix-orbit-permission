"""Orbit plugin: users, roles, and permissions UI on top of almasix-permission."""

from __future__ import annotations

from typing import Any, Self

from almasix.orbit.panels.hooks import Plugin

from almasix_orbit_permission.config import PermissionPluginConfig
from almasix_orbit_permission.generator import discover_panel
from almasix_orbit_permission.models import bind_permission_model, bind_role_model, bind_user_model
from almasix_orbit_permission.resources import (
    PermissionResource,
    RoleResource,
    UserResource,
    _stamp,
    bind_plugin,
)
from almasix_orbit_permission.seeder import generate_for_panel
from almasix_orbit_permission.store import MemoryStore
from almasix_orbit_permission.widgets import AccessOverviewWidget


class PermissionPlugin(Plugin):
    """Register Access resources and optionally seed abilities from the panel."""

    def __init__(self) -> None:
        super().__init__("orbit-permission")
        self.config = PermissionPluginConfig()
        self.store: MemoryStore | None = None
        self.cached_specs: list[Any] = []
        self._role_model: type[Any] | None = None
        self._permission_model: type[Any] | None = None
        self._user_model: type[Any] | None = None

    @classmethod
    def make(cls) -> PermissionPlugin:
        return cls()

    def navigation_group(self, name: str) -> Self:
        self.config.navigation_group = str(name)
        return self

    def super_admin_role(self, name: str) -> Self:
        self.config.super_admin_role = str(name)
        return self

    def guard(self, name: str) -> Self:
        self.config.guard = str(name)
        return self

    def exclude(self, *names: str) -> Self:
        self.config.exclude = tuple(str(n) for n in names)
        return self

    def extra_permissions(self, *names: str) -> Self:
        self.config.extra_permissions = tuple(str(n) for n in names)
        return self

    def user_model(self, model: type[Any] | str) -> Self:
        self.config.user_model = model
        return self

    def cluster(self, cluster: type[Any] | str | None) -> Self:
        self.config.cluster = cluster
        return self

    def without_user_resource(self) -> Self:
        self.config.register_user_resource = False
        return self

    def without_role_resource(self) -> Self:
        self.config.register_role_resource = False
        return self

    def without_permission_resource(self) -> Self:
        self.config.register_permission_resource = False
        return self

    def without_widget(self) -> Self:
        self.config.register_widget = False
        return self

    def generate_on_boot(self, condition: bool = True) -> Self:
        self.config.generate_on_boot = bool(condition)
        return self

    def memory(self, store: MemoryStore | None = None) -> Self:
        """Use an in-memory store (tests / demos without a database)."""
        self.store = store or MemoryStore()
        self.config.store = self.store
        return self

    def resolve_user_model(self) -> type[Any] | None:
        if self._user_model is not None:
            return self._user_model
        configured = self.config.user_model
        if isinstance(configured, type):
            self._user_model = bind_user_model(configured)
            return self._user_model
        path = configured
        if not path:
            try:
                from almasix.config import config

                path = config("auth.providers.users.model")
            except Exception:
                path = None
        if not path:
            return None
        if isinstance(path, type):
            self._user_model = bind_user_model(path)
            return self._user_model
        module_name, _, class_name = str(path).rpartition(".")
        if not module_name:
            return None
        import importlib

        module = importlib.import_module(module_name)
        model = getattr(module, class_name, None)
        if model is None:
            return None
        self._user_model = bind_user_model(model)
        return self._user_model

    def register(self, panel: Any) -> None:
        bind_plugin(self)
        if self.store is None and isinstance(self.config.store, MemoryStore):
            self.store = self.config.store
        _stamp(RoleResource, self.config)
        _stamp(PermissionResource, self.config)
        _stamp(UserResource, self.config)
        if self.store is None:
            self._role_model = bind_role_model()
            self._permission_model = bind_permission_model()
            RoleResource.model = self._role_model
            PermissionResource.model = self._permission_model
            user_cls = self.resolve_user_model()
            if user_cls is not None:
                UserResource.model = user_cls
        else:
            RoleResource.model = None
            PermissionResource.model = None
            UserResource.model = None

        extras: list[type[Any]] = []
        if self.config.register_user_resource:
            extras.append(UserResource)
        if self.config.register_role_resource:
            extras.append(RoleResource)
        if self.config.register_permission_resource:
            extras.append(PermissionResource)
        existing = list(panel.get_resources())
        seen = {id(item) for item in existing}
        merged = existing + [item for item in extras if id(item) not in seen]
        panel.resources(merged)

        if self.config.register_widget:
            widgets = list(panel.get_widgets())
            if AccessOverviewWidget not in widgets:
                panel.widgets([*widgets, AccessOverviewWidget])

    def boot(self, panel: Any) -> None:
        bind_plugin(self)
        self.cached_specs = discover_panel(panel, self.config)
        if self.config.generate_on_boot:
            generate_for_panel(panel, self.config, store=self.store)
