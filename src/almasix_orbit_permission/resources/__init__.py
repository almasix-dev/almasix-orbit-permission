"""Orbit resources for users, roles, and permissions."""

from __future__ import annotations

from typing import Any, ClassVar

from almasix.orbit import Resource
from almasix.orbit.forms import CheckboxList, Form, Select, TextInput
from almasix.orbit.schemas import Section
from almasix.orbit.tables import Table, TextColumn

from almasix_orbit_permission.config import PermissionPluginConfig
from almasix_orbit_permission.generator import grouped_options
from almasix_orbit_permission.store import MemoryStore

_PLUGIN: Any = None


def bind_plugin(plugin: Any) -> None:
    global _PLUGIN
    _PLUGIN = plugin


def current_plugin() -> Any:
    return _PLUGIN


def _config() -> PermissionPluginConfig:
    plugin = current_plugin()
    if plugin is None:
        return PermissionPluginConfig()
    return plugin.config


def _store() -> MemoryStore | None:
    plugin = current_plugin()
    if plugin is None:
        return None
    store = getattr(plugin, "store", None)
    return store if isinstance(store, MemoryStore) else None


def _permission_options() -> dict[str, str]:
    plugin = current_plugin()
    if plugin is not None:
        specs = getattr(plugin, "cached_specs", None)
        if specs:
            flat: dict[str, str] = {}
            for entity, options in grouped_options(list(specs)).items():
                title = entity.replace("_", " ").title()
                for name, label in options.items():
                    flat[name] = f"{title} · {label}"
            return flat
    store = _store()
    if store is not None:
        return {str(row["name"]): str(row["name"]) for row in store.list_permissions()}
    return {}


def _role_options() -> dict[str, str]:
    store = _store()
    if store is not None:
        return {str(row["name"]): str(row["name"]) for row in store.list_roles()}
    try:
        from almasix.permission import Role

        from almasix_orbit_permission.runtime import run

        rows = list(run(Role.query().get()) or [])
        return {str(row.name): str(row.name) for row in rows}
    except Exception:
        return {}


def _stamp(resource: type[Resource], config: PermissionPluginConfig) -> None:
    resource.navigation_group = config.navigation_group
    resource.cluster = config.cluster


class RoleResource(Resource):
    """CRUD for named roles and the abilities attached to them."""

    slug = "roles"
    navigation_label = "Roles"
    navigation_icon = "heroicon-o-shield-check"
    navigation_sort = 10
    record_title_attribute = "name"
    model_label = "Role"
    records_mutable = True
    records: ClassVar[list[dict[str, Any]]] = []
    global_search_attributes = ("name", "guard_name")

    @classmethod
    def get_records(cls) -> list[dict[str, Any]]:
        store = _store()
        if store is not None:
            cls.records = store.list_roles()
            return list(cls.records)
        if cls.records:
            return list(cls.records)
        try:
            from almasix.permission import Role

            from almasix_orbit_permission.runtime import run

            rows = []
            for role in run(Role.query().get()) or []:
                getter = getattr(role, "get_attributes", None)
                if callable(getter):
                    rows.append(dict(getter()))
                else:
                    rows.append(
                        {
                            "id": getattr(role, "id", None),
                            "name": getattr(role, "name", ""),
                            "guard_name": getattr(role, "guard_name", ""),
                            "permissions": [],
                        }
                    )
            cls.records = rows
            return list(rows)
        except Exception:
            return list(cls.records)

    @classmethod
    def form(cls, form: Form) -> Form:
        options = _permission_options()
        return form.schema(
            [
                TextInput.make("name").required().max_length(255),
                TextInput.make("guard_name").default("web"),
                Section.make("Permissions").schema(
                    [
                        CheckboxList.make("permissions")
                        .options(options)
                        .bulk_toggleable()
                        .options_columns(2),
                    ]
                ),
            ]
        )

    @classmethod
    def table(cls, table: Table) -> Table:
        return table.columns(
            [
                TextColumn.make("name").searchable().sortable(),
                TextColumn.make("guard_name").badge(),
            ]
        )


class PermissionResource(Resource):
    """Named abilities (usually generated from the panel)."""

    slug = "permissions"
    navigation_label = "Permissions"
    navigation_icon = "heroicon-o-key"
    navigation_sort = 20
    record_title_attribute = "name"
    model_label = "Permission"
    records_mutable = True
    records: ClassVar[list[dict[str, Any]]] = []
    global_search_attributes = ("name", "guard_name")

    @classmethod
    def get_records(cls) -> list[dict[str, Any]]:
        store = _store()
        if store is not None:
            cls.records = store.list_permissions()
            return list(cls.records)
        if cls.records:
            return list(cls.records)
        try:
            from almasix.permission import Permission

            from almasix_orbit_permission.runtime import run

            rows = [
                {
                    "id": getattr(row, "id", None),
                    "name": getattr(row, "name", ""),
                    "guard_name": getattr(row, "guard_name", ""),
                }
                for row in (run(Permission.query().get()) or [])
            ]
            cls.records = rows
            return list(rows)
        except Exception:
            return list(cls.records)

    @classmethod
    def form(cls, form: Form) -> Form:
        return form.schema(
            [
                TextInput.make("name")
                .required()
                .helper_text("Use entity.ability, e.g. posts.view"),
                TextInput.make("guard_name").default("web"),
            ]
        )

    @classmethod
    def table(cls, table: Table) -> Table:
        return table.columns(
            [
                TextColumn.make("name").searchable().sortable(),
                TextColumn.make("guard_name").badge(),
            ]
        )


class UserResource(Resource):
    """App users with roles (and optional direct permissions)."""

    slug = "users"
    navigation_label = "Users"
    navigation_icon = "heroicon-o-users"
    navigation_sort = 5
    record_title_attribute = "email"
    model_label = "User"
    records_mutable = True
    records: ClassVar[list[dict[str, Any]]] = []
    global_search_attributes = ("email", "name")

    @classmethod
    def get_records(cls) -> list[dict[str, Any]]:
        store = _store()
        if store is not None:
            cls.records = store.list_users()
            return list(cls.records)
        if cls.records:
            return list(cls.records)
        model = getattr(cls, "model", None)
        if model is None:
            return list(cls.records)
        try:
            from almasix_orbit_permission.runtime import run

            rows_raw: list[Any] = []
            all_fn = getattr(model, "all", None)
            if callable(all_fn):
                rows_raw = list(run(all_fn()) or [])
            query = getattr(model, "query", None)
            if not rows_raw and callable(query):
                rows_raw = list(run(query().get()) or [])
            rows = []
            for user in rows_raw or []:
                getter = getattr(user, "get_attributes", None)
                if callable(getter):
                    rows.append(dict(getter()))
                    continue
                rows.append(
                    {
                        "id": getattr(user, "id", None),
                        "name": getattr(user, "name", ""),
                        "email": getattr(user, "email", ""),
                        "roles": [],
                        "permissions": [],
                    }
                )
            cls.records = rows
            return list(rows)
        except Exception:
            return list(cls.records)

    @classmethod
    def form(cls, form: Form) -> Form:
        return form.schema(
            [
                TextInput.make("name").required(),
                TextInput.make("email").email().required(),
                Select.make("roles")
                .multiple()
                .options(_role_options())
                .helper_text("Roles grant the abilities below."),
                CheckboxList.make("permissions")
                .options(_permission_options())
                .bulk_toggleable()
                .helper_text("Direct permissions in addition to roles."),
            ]
        )

    @classmethod
    def table(cls, table: Table) -> Table:
        return table.columns(
            [
                TextColumn.make("name").searchable().sortable(),
                TextColumn.make("email").searchable().copyable(),
            ]
        )
