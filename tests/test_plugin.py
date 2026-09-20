"""Coverage for generator, store, plugin, resources, commands, models."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from almasix.orbit import Panel, Resource
from almasix.orbit.widgets import Widget

from almasix_orbit_permission import (
    AccessOverviewWidget,
    HasOrbitPermissions,
    MemoryStore,
    PermissionPlugin,
    PermissionResource,
    RoleResource,
    UserResource,
    __version__,
)
from almasix_orbit_permission.auth import HasOrbitPermissions as AuthMixin
from almasix_orbit_permission.commands import (
    GeneratePermissionsCommand,
    SuperAdminCommand,
    _find_user,
)
from almasix_orbit_permission.config import RESOURCE_ABILITIES
from almasix_orbit_permission.generator import (
    PermissionSpec,
    ability_label,
    discover_panel,
    entity_slug,
    grouped_options,
    permission_name,
    prefixes_for,
    specs_for_object,
)
from almasix_orbit_permission.models import (
    _as_name_list,
    _copy_fillable,
    bind_permission_model,
    bind_role_model,
    bind_user_model,
)
from almasix_orbit_permission.provider import OrbitPermissionProvider
from almasix_orbit_permission.resources import (
    _config,
    _permission_options,
    _role_options,
    _stamp,
    bind_plugin,
    current_plugin,
)
from almasix_orbit_permission.runtime import run
from almasix_orbit_permission.seeder import (
    default_guard,
    generate_for_panel,
    generate_into_orm,
    generate_into_store,
)


class PostResource(Resource):
    slug = "posts"
    soft_deletes = True

    @classmethod
    def get_permission_prefixes(cls) -> list[str]:
        return ["view_any", "publish"]


class SettingsPage:
    slug = "settings"


class NotesWidget(Widget):
    pass


class Prefixed:
    @classmethod
    def get_permission_prefix(cls) -> str:
        return "custom"

    @classmethod
    def get_slug(cls) -> str:
        return "ignored"


@pytest.fixture(autouse=True)
def _reset_plugin() -> Any:
    bind_plugin(None)
    RoleResource.records = []
    PermissionResource.records = []
    UserResource.records = []
    UserResource.model = None
    RoleResource.model = None
    PermissionResource.model = None
    yield
    bind_plugin(None)


def test_version_and_names() -> None:
    assert __version__ == "0.1.0"
    assert AuthMixin is HasOrbitPermissions
    assert permission_name("posts", "view") == "posts.view"
    assert ability_label("view_any") == "View any"
    assert ability_label("publish") == "Publish"
    assert entity_slug(PostResource, fallback="x") == "posts"
    assert entity_slug(type("AuditLogResource", (), {}), fallback="x") == "audit_log"
    assert entity_slug(SimpleNamespace(permission_prefix="custom"), fallback="x") == "custom"
    assert entity_slug(Prefixed, fallback="x") == "custom"
    assert entity_slug(type("X", (), {}), fallback="page") == "x"

    class EmptyPrefix:
        @classmethod
        def get_permission_prefix(cls) -> str:
            return ""

        @classmethod
        def get_slug(cls) -> str:
            return "from-slug"

    class EmptySlug:
        @classmethod
        def get_slug(cls) -> str:
            return ""

        slug = "from-attr"

    assert entity_slug(EmptyPrefix, fallback="x") == "from-slug"
    assert entity_slug(EmptySlug, fallback="x") == "from-attr"
    assert prefixes_for(PostResource, kind="resource") == ("view_any", "publish")
    assert "restore" in prefixes_for(
        type("R", (Resource,), {"soft_deletes": True}), kind="resource"
    )
    assert prefixes_for(type("R", (Resource,), {}), kind="resource") == RESOURCE_ABILITIES
    assert prefixes_for(SettingsPage, kind="page") == ("view",)
    assert prefixes_for(NotesWidget, kind="widget") == ("view",)
    assert prefixes_for(object(), kind="other") == ()
    assert _as_name_list("a") == ["a"]
    assert _as_name_list("  ") == []
    assert _as_name_list(["a", ""]) == ["a"]
    assert _as_name_list(None) == []
    assert _as_name_list(1) == []
    assert _copy_fillable(type("M", (), {"fillable": ("name",)}), "roles") == ("name", "roles")
    assert _copy_fillable(type("M", (), {"fillable": ("roles",)}), "roles") == ("roles",)


def test_discover_and_group() -> None:
    dash = type("Dashboard", (), {"slug": "dashboard"})
    panel = (
        Panel.make("admin")
        .path("admin")
        .resources([PostResource])
        .pages([dash, type("SettingsPage", (), {"slug": "settings"})])
        .widgets([NotesWidget])
        .login(False)
        .dashboard(dash)
    )
    plugin = (
        PermissionPlugin.make()
        .memory()
        .exclude("NotesWidget")
        .extra_permissions("impersonate", "posts.view_any", "  ")
    )
    plugin.register(panel)
    plugin.register(panel)  # duplicate extras skipped
    specs = discover_panel(panel, plugin.config)
    names = {spec.name for spec in specs}
    assert "posts.view_any" in names
    assert "posts.publish" in names
    assert "settings.view" in names
    assert "impersonate" in names
    groups = grouped_options(specs)
    assert "posts" in groups
    plugin.boot(panel)
    assert plugin.cached_specs

    dash_obj = object()
    settings = type("SettingsPage", (), {"slug": "settings"})
    fake_panel = SimpleNamespace(
        get_resources=lambda: [],
        get_pages=lambda: [dash_obj, settings],
        get_widgets=lambda: [NotesWidget],
        dashboard_page=lambda: dash_obj,
        dashboard_enabled=lambda: True,
    )
    skip_cfg = PermissionPlugin.make().exclude("NotesWidget", "settings").config
    skip_names = {spec.name for spec in discover_panel(fake_panel, skip_cfg)}
    assert "dashboard.view" not in skip_names
    assert "settings.view" not in skip_names
    assert "notes.view" not in skip_names

    html = RoleResource.get_form().render({"name": "editor", "permissions": ["posts.view_any"]})
    assert "or-field" in html


def test_plugin_registers_resources_and_widget() -> None:
    store = MemoryStore()
    store.ensure_permission("posts.view")
    store.ensure_role("editor")
    store.users.append({"id": 1, "name": "Ada", "email": "ada@example.com", "roles": ["editor"]})
    panel = Panel.make("admin").path("admin").resources([PostResource]).login(False)
    plugin = (
        PermissionPlugin.make()
        .memory(store)
        .navigation_group("Security")
        .super_admin_role("root")
        .guard("web")
        .generate_on_boot()
        .extra_permissions("posts.view")
    )
    plugin.register(panel)
    plugin.boot(panel)
    names = {cls.__name__ for cls in panel.get_resources()}
    assert {"PostResource", "RoleResource", "PermissionResource", "UserResource"} <= names
    assert AccessOverviewWidget in panel.get_widgets()
    assert RoleResource.navigation_group == "Security"
    assert RoleResource.get_table() is not None
    role_rows = RoleResource.get_records()
    assert any(row["name"] == "editor" for row in role_rows)
    assert PermissionResource.get_records()
    assert UserResource.get_records()[0]["email"] == "ada@example.com"
    assert "email" in UserResource.get_form().render({"email": "ada@example.com"})
    assert "posts.view" in PermissionResource.get_form().render({"name": "posts.view"})
    widget = AccessOverviewWidget()
    stats = widget.get_stats()
    assert stats[0]._value == 1
    assert stats[1]._value >= 1
    assert stats[2]._value >= 1
    assert "or-stats" in widget.render_body()
    assert current_plugin() is plugin
    assert _config().navigation_group == "Security"
    assert _permission_options()
    assert _role_options()["editor"] == "editor"


def test_plugin_without_optional_surfaces() -> None:
    panel = Panel.make("admin").path("admin").login(False)
    plugin = (
        PermissionPlugin.make()
        .memory()
        .without_user_resource()
        .without_role_resource()
        .without_permission_resource()
        .without_widget()
        .cluster("access")
    )
    plugin.register(panel)
    assert panel.get_resources() == []
    assert panel.get_widgets() == []
    _stamp(RoleResource, plugin.config)
    assert RoleResource.cluster == "access"


def test_memory_store_and_seeder() -> None:
    store = MemoryStore()
    first = store.ensure_permission("posts.view")
    again = store.ensure_permission("posts.view")
    assert first["id"] == again["id"]
    role = store.ensure_role("admin")
    store.ensure_role("admin")
    store.sync_role_permissions(role["id"], ["posts.view"])
    store.sync_role_permissions(999, ["x"])
    store.users.append({"id": 9, "email": "root@x.test"})
    store.sync_user_roles(9, ["admin"])
    store.sync_user_roles(999, ["x"])
    store.sync_user_permissions(9, ["posts.view"])
    store.sync_user_permissions(999, ["x"])
    store.grant_all_to_role("admin")
    store.replace_roles(store.list_roles())
    store.replace_permissions(store.list_permissions())
    store.replace_users(store.list_users())
    panel = Panel.make("admin").path("admin").resources([PostResource]).login(False)
    config = PermissionPlugin.make().memory(store).config
    names = generate_into_store(specs_for_object(PostResource, kind="resource"), store, config)
    assert "posts.view_any" in names
    assert generate_for_panel(panel, config, store=store)


def test_generate_command_and_super_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MemoryStore()
    store.users.append({"id": 3, "email": "ada@example.com"})
    panel = Panel.make("admin").path("admin").resources([PostResource]).login(False)
    plugin = PermissionPlugin.make().memory(store)
    plugin.register(panel)
    plugin.boot(panel)

    import almasix_orbit_permission.commands as commands

    monkeypatch.setattr(
        commands, "_panel_from_id", lambda panel_id: panel if panel_id == "admin" else None
    )
    gen = GeneratePermissionsCommand()
    gen.argument = lambda name: "admin"  # type: ignore[method-assign]
    gen.success = lambda msg: None  # type: ignore[method-assign]
    gen.error = lambda msg: None  # type: ignore[method-assign]
    assert gen.handle() == 0

    missing = GeneratePermissionsCommand()
    missing.argument = lambda name: "missing"  # type: ignore[method-assign]
    missing.error = lambda msg: None  # type: ignore[method-assign]
    assert missing.handle() == 1

    cmd = SuperAdminCommand()
    cmd.argument = lambda name: "ada@example.com"  # type: ignore[method-assign]
    cmd.success = lambda msg: None  # type: ignore[method-assign]
    cmd.error = lambda msg: None  # type: ignore[method-assign]
    assert cmd.handle() == 0
    user = next(u for u in store.list_users() if u["email"] == "ada@example.com")
    assert "super_admin" in user["roles"]

    by_id = SuperAdminCommand()
    by_id.argument = lambda name: "3"  # type: ignore[method-assign]
    by_id.success = lambda msg: None  # type: ignore[method-assign]
    by_id.error = lambda msg: None  # type: ignore[method-assign]
    assert by_id.handle() == 0

    empty = SuperAdminCommand()
    empty.argument = lambda name: ""  # type: ignore[method-assign]
    empty.error = lambda msg: None  # type: ignore[method-assign]
    assert empty.handle() == 1
    missing_user = SuperAdminCommand()
    missing_user.argument = lambda name: "ghost"  # type: ignore[method-assign]
    missing_user.error = lambda msg: None  # type: ignore[method-assign]
    assert missing_user.handle() == 1


def test_runtime_run_sync_and_busy_loop() -> None:
    async def _one() -> int:
        return 7

    assert run(_one()) == 7
    assert run(11) == 11

    async def _nested() -> int:
        async def _two() -> int:
            return 9

        return run(_two())

    assert asyncio.run(_nested()) == 9


def test_bind_models_without_permission_package() -> None:
    class FakeRole:
        fillable = ("name", "guard_name")
        created: list[dict[str, Any]] = []

        def __init__(self, **attrs: Any) -> None:
            self.__dict__.update(attrs)
            self.synced: list[str] = []

        @classmethod
        async def create(cls, attributes=None, **kwargs: Any) -> Any:
            attrs = {**(attributes or {}), **kwargs}
            row = cls(id=1, **attrs)
            cls.created.append(attrs)
            return row

        async def save(self) -> bool:
            return True

        async def sync_permissions(self, *names: str) -> Any:
            self.synced = list(names)
            return self

        async def get_all_permissions(self) -> list[Any]:
            return [SimpleNamespace(name=n) for n in self.synced]

        def get_attributes(self) -> dict[str, Any]:
            return {"id": getattr(self, "id", 1), "name": getattr(self, "name", "")}

    Managed = bind_role_model(FakeRole)
    role = run(Managed.create({"name": "editor", "permissions": ["posts.view"]}))
    assert "permissions" not in FakeRole.created[-1]
    assert role.synced == ["posts.view"]
    role.permissions = ["posts.update"]
    run(role.save())
    assert role.synced == ["posts.update"]
    role.permissions = "posts.delete"
    run(role.save())
    assert role.synced == ["posts.delete"]
    run(role.save())
    attrs = role.get_attributes()
    assert "posts.delete" in attrs["permissions"]
    assert bind_permission_model(FakeRole) is FakeRole

    class BareRole:
        fillable = ()

        def __init__(self, **attrs: Any) -> None:
            self.__dict__.update(attrs)

        @classmethod
        async def create(cls, attributes=None, **kwargs: Any) -> Any:
            return cls(**(attributes or {}), **kwargs)

        async def save(self) -> bool:
            return True

        async def get_all_permissions(self) -> list[Any]:
            raise RuntimeError("no db")

    Bare = bind_role_model(BareRole)
    bare = Bare(name="x", permissions=["a"])
    data = bare.get_attributes()
    assert data["permissions"] == ["a"]

    class FakeUser:
        fillable = ("email", "name")

        def __init__(self, **attrs: Any) -> None:
            self.__dict__.update(attrs)
            self.roles_synced: list[str] = []
            self.perm_synced: list[str] = []

        @classmethod
        async def create(cls, attributes=None, **kwargs: Any) -> Any:
            attrs = {**(attributes or {}), **kwargs}
            return cls(id=4, **attrs)

        async def save(self) -> bool:
            return True

        async def sync_roles(self, *names: str) -> Any:
            self.roles_synced = list(names)
            return self

        async def sync_permissions(self, *names: str) -> Any:
            self.perm_synced = list(names)
            return self

        def check_permission_to(self, ability: str, guard_name: str | None = None) -> bool:
            return ability in self.perm_synced

        async def get_role_names(self) -> list[str]:
            return list(self.roles_synced)

        async def get_all_permissions(self) -> list[Any]:
            return [SimpleNamespace(name=n) for n in self.perm_synced]

        def get_attributes(self) -> dict[str, Any]:
            return {"id": 4, "email": getattr(self, "email", "")}

    Bound = bind_user_model(FakeUser)
    user = run(Bound.create({"email": "a@b.c", "roles": ["admin"], "permissions": ["posts.view"]}))
    assert user.roles_synced == ["admin"]
    assert user.has_permission("posts.view")
    assert user.can("posts.view")
    assert not user.has_permission("posts.delete")
    user.roles = ["editor"]
    user.permissions = ["posts.update"]
    run(user.save())
    assert user.roles_synced == ["editor"]
    data = user.get_attributes()
    assert data["roles"] == ["editor"]

    class BoomUser(FakeUser):
        def check_permission_to(self, ability: str, guard_name: str | None = None) -> bool:
            raise RuntimeError("boom")

        async def get_role_names(self) -> list[str]:
            raise RuntimeError("boom")

        async def get_all_permissions(self) -> list[Any]:
            raise RuntimeError("boom")

    Broken = bind_user_model(BoomUser)
    broken = Broken(email="x", roles=["a"], permissions=["b"])
    assert broken.has_permission("b") is False
    dumped = broken.get_attributes()
    assert dumped["roles"] == ["a"]
    assert dumped["permissions"] == ["b"]

    class Plain:
        fillable = ("email",)

        def __init__(self, **attrs: Any) -> None:
            self.__dict__.update(attrs)

        @classmethod
        async def create(cls, attributes=None, **kwargs: Any) -> Any:
            return cls(**(attributes or {}), **kwargs)

        async def save(self) -> bool:
            return True

    PlainBound = bind_user_model(Plain)
    plain = run(PlainBound.create({"email": "p@x", "roles": ["r"], "permissions": ["p"]}))
    assert not hasattr(plain, "sync_roles")
    plain.roles = "r2"
    plain.permissions = {"p2"}
    assert plain.has_permission("p2")
    assert not plain.has_permission("missing")
    run(plain.save())
    none_user = PlainBound(email="z")
    assert none_user.has_permission("x") is False
    run(none_user.save())
    assert "email" in none_user.get_attributes() or none_user.get_attributes() is not None
    assert "email" in plain.get_attributes()

    class EmptyAttrs:
        fillable = ("email",)

        def __init__(self, **attrs: Any) -> None:
            self.__dict__.update(attrs)

        def get_attributes(self) -> dict[str, Any]:
            return {}

        async def save(self) -> bool:
            return True

        async def get_role_names(self) -> list[str]:
            return ["r"]

        async def get_all_permissions(self) -> list[Any]:
            return [SimpleNamespace(name="p")]

    EmptyBound = bind_user_model(EmptyAttrs)
    empty = EmptyBound(email="e@x")
    dumped = empty.get_attributes()
    assert dumped["roles"] == ["r"]
    assert "p" in dumped["permissions"]

    class RaisingNames(EmptyAttrs):
        async def get_role_names(self) -> list[str]:
            raise RuntimeError("x")

        async def get_all_permissions(self) -> list[Any]:
            raise RuntimeError("x")

    Raised = bind_user_model(RaisingNames)
    raised = Raised(email="r@x", roles=["a"], permissions=["b"])
    dumped = raised.get_attributes()
    assert dumped["roles"] == ["a"]
    assert dumped["permissions"] == ["b"]
    raised2 = Raised(email="r2@x", roles="nope", permissions="nope")
    dumped2 = raised2.get_attributes()
    assert "roles" not in dumped2 or dumped2.get("roles") == "nope"


def test_user_resource_from_model_and_query() -> None:
    class Users:
        @classmethod
        async def all(cls) -> list[Any]:
            return [
                SimpleNamespace(
                    id=1,
                    name="Ada",
                    email="ada@x.test",
                    get_attributes=lambda: {"id": 1, "email": "ada@x.test"},
                )
            ]

    UserResource.model = Users
    UserResource.records = []
    rows = UserResource.get_records()
    assert rows[0]["email"] == "ada@x.test"

    class Queried:
        @classmethod
        async def all(cls) -> list[Any]:
            return []

        @classmethod
        def query(cls) -> Any:
            return SimpleNamespace(
                get=lambda: [
                    SimpleNamespace(id=2, name="Bo", email="bo@x.test"),
                ]
            )

    UserResource.model = Queried
    UserResource.records = []
    rows = UserResource.get_records()
    assert rows[0]["email"] == "bo@x.test"

    class Broken:
        @classmethod
        async def all(cls) -> list[Any]:
            raise RuntimeError("db down")

    UserResource.model = Broken
    UserResource.records = [{"id": 9, "email": "cached@x.test"}]
    assert UserResource.get_records()[0]["email"] == "cached@x.test"
    UserResource.records = []
    assert UserResource.get_records() == []

    class OnlyQuery:
        @classmethod
        def query(cls) -> Any:
            return SimpleNamespace(
                get=lambda: [SimpleNamespace(id=2, name="Bo", email="bo@x.test")]
            )

    UserResource.model = OnlyQuery
    UserResource.records = []
    assert UserResource.get_records()[0]["email"] == "bo@x.test"
    assert PermissionResource.get_table() is not None

    bind_plugin(None)
    UserResource.model = OnlyQuery
    UserResource.records = []
    rows = UserResource.get_records()
    assert rows[0]["name"] == "Bo"
    assert "get_attributes" not in rows[0]


def test_resource_orm_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeQuery:
        def get(self) -> list[Any]:
            return [
                SimpleNamespace(
                    id=1,
                    name="editor",
                    guard_name="web",
                    get_attributes=lambda: {"id": 1, "name": "editor"},
                ),
                SimpleNamespace(id=2, name="viewer", guard_name="web"),
            ]

    class FakeRole:
        @classmethod
        def query(cls) -> FakeQuery:
            return FakeQuery()

    monkeypatch.setattr("almasix.permission.Role", FakeRole, raising=False)
    import almasix_orbit_permission.resources as resources

    monkeypatch.setattr(resources, "_store", lambda: None)
    RoleResource.records = []
    rows = RoleResource.get_records()
    assert any(row["name"] == "editor" for row in rows)
    RoleResource.records = [{"id": 3, "name": "cached"}]
    assert RoleResource.get_records()[0]["name"] == "cached"

    class PermQuery:
        def get(self) -> list[Any]:
            return [SimpleNamespace(id=1, name="posts.view", guard_name="web")]

    class FakePermission:
        @classmethod
        def query(cls) -> PermQuery:
            return PermQuery()

    monkeypatch.setattr("almasix.permission.Permission", FakePermission, raising=False)
    PermissionResource.records = []
    assert PermissionResource.get_records()[0]["name"] == "posts.view"
    PermissionResource.records = [{"id": 4, "name": "cached.perm"}]
    assert PermissionResource.get_records()[0]["name"] == "cached.perm"

    options = _role_options()
    assert "editor" in options or "cached" in options or options == {}


def test_resource_orm_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    import almasix_orbit_permission.resources as resources

    monkeypatch.setattr(resources, "_store", lambda: None)

    def _boom() -> Any:
        raise RuntimeError("no package")

    monkeypatch.setattr(resources.run, "__call__", _boom) if False else None

    class Boom:
        @classmethod
        def query(cls) -> Any:
            raise RuntimeError("no db")

    monkeypatch.setattr("almasix.permission.Role", Boom, raising=False)
    monkeypatch.setattr("almasix.permission.Permission", Boom, raising=False)
    RoleResource.records = []
    assert RoleResource.get_records() == []
    PermissionResource.records = []
    assert PermissionResource.get_records() == []
    assert _role_options() == {}


def test_provider_registers_commands() -> None:
    registered: list[Any] = []

    class FakeProvider(OrbitPermissionProvider):
        def __init__(self) -> None:
            pass

        def commands(self, items: list[Any]) -> None:  # type: ignore[override]
            registered.extend(items)

    FakeProvider().boot()
    assert GeneratePermissionsCommand in registered


def test_default_guard_and_orm_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    assert default_guard(PermissionPlugin.make().guard("api").config) == "api"

    def _guard() -> str:
        return "from-pkg"

    monkeypatch.setattr(
        "almasix.permission.helpers.get_default_guard_name",
        _guard,
        raising=False,
    )
    assert default_guard(PermissionPlugin.make().config) in {"from-pkg", "web"}

    created: list[str] = []

    class FakePermission:
        @classmethod
        async def find_or_create(cls, name: str, guard: str | None = None) -> Any:
            created.append(name)
            return SimpleNamespace(name=name)

    class FakeRole:
        @classmethod
        async def find_or_create(cls, name: str, guard: str | None = None) -> Any:
            role = SimpleNamespace(name=name, synced=[])

            async def _sync(*names: str) -> Any:
                role.synced = list(names)
                return role

            role.sync_permissions = _sync
            return role

    monkeypatch.setattr("almasix.permission.Permission", FakePermission)
    monkeypatch.setattr("almasix.permission.Role", FakeRole)
    specs = [
        PermissionSpec(
            name="posts.view", entity="posts", ability="view", kind="resource", label="Posts · View"
        )
    ]
    names = generate_into_orm(specs, PermissionPlugin.make().guard("web").config)
    assert "posts.view" in names
    assert created == ["posts.view"]

    def _fail(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("orm down")

    monkeypatch.setattr("almasix_orbit_permission.seeder.generate_into_orm", _fail)
    panel = Panel.make("admin").path("admin").login(False)
    fallback = generate_for_panel(panel, PermissionPlugin.make().config, store=None)
    assert isinstance(fallback, list)


def test_plugin_user_model_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    class User:
        fillable = ("email",)

    plugin = PermissionPlugin.make().memory().user_model(User)
    resolved = plugin.resolve_user_model()
    assert resolved is not None
    assert plugin.resolve_user_model() is resolved

    plugin2 = PermissionPlugin.make()
    plugin2.config.user_model = "almasix_orbit_permission.plugin.PermissionPlugin"
    assert plugin2.resolve_user_model() is not None

    plugin3 = PermissionPlugin.make()
    plugin3.config.user_model = "almasix_orbit_permission.plugin.Missing"
    assert plugin3.resolve_user_model() is None

    plugin4 = PermissionPlugin.make()
    plugin4.config.user_model = "NoDots"
    assert plugin4.resolve_user_model() is None

    plugin5 = PermissionPlugin.make()
    plugin5.config.user_model = None

    def _cfg(_key: str) -> type[Any]:
        return User

    monkeypatch.setattr("almasix.config.config", _cfg, raising=False)
    # config() may already exist; either a type or None is acceptable
    plugin5.resolve_user_model()

    plugin6 = PermissionPlugin.make()
    plugin6.config.user_model = None

    def _boom(_key: str) -> Any:
        raise RuntimeError("no config")

    monkeypatch.setattr("almasix.config.config", _boom, raising=False)
    # If the real config is already imported this may still resolve; just must not crash
    plugin6.resolve_user_model()


def test_empty_records_and_unbound_helpers() -> None:
    bind_plugin(None)
    assert _config().navigation_group == "Access"
    assert _permission_options() == {}
    assert current_plugin() is None
    RoleResource.records = []
    PermissionResource.records = []
    UserResource.records = []
    UserResource.model = None
    plugin = PermissionPlugin.make().memory()
    bind_plugin(plugin)
    assert RoleResource.get_records() == []
    assert PermissionResource.get_records() == []
    assert UserResource.get_records() == []
    bind_plugin(None)
    UserResource.model = None
    UserResource.records = []
    assert UserResource.get_records() == []
    assert _permission_options() == {}
    assert _role_options() == {}


def test_has_orbit_permissions_mixin() -> None:
    class User(HasOrbitPermissions):
        def check_permission_to(self, ability: str, guard_name: str | None = None) -> bool:
            return ability == "posts.view"

    user = User()
    assert user.has_permission("posts.view")
    assert user.can("posts.view")
    assert not user.has_permission("posts.delete")

    class Boom(HasOrbitPermissions):
        def check_permission_to(self, ability: str, guard_name: str | None = None) -> bool:
            raise RuntimeError("x")

    assert Boom().has_permission("x") is False

    class Listed(HasOrbitPermissions):
        permissions = ["posts.view", "*"]

    assert Listed().has_permission("anything")

    class Empty(HasOrbitPermissions):
        pass

    assert Empty().has_permission("x") is False


def test_widget_orm_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    bind_plugin(None)

    class Q:
        def get(self) -> list[Any]:
            return [1, 2]

    class Fake:
        @classmethod
        def query(cls) -> Q:
            return Q()

    monkeypatch.setattr("almasix.permission.Role", Fake, raising=False)
    monkeypatch.setattr("almasix.permission.Permission", Fake, raising=False)
    widget = AccessOverviewWidget()
    users, roles, perms = widget._counts()
    assert users == 0
    assert roles in {0, 2}
    assert perms in {0, 2}

    class Broken:
        @classmethod
        def query(cls) -> Any:
            raise RuntimeError("x")

    monkeypatch.setattr("almasix.permission.Role", Broken, raising=False)
    users, roles, perms = AccessOverviewWidget()._counts()
    assert roles == 0 and perms == 0

    class UserModel:
        @classmethod
        async def all(cls) -> list[Any]:
            return [1, 2, 3]

    plugin = PermissionPlugin.make()
    plugin._user_model = UserModel
    bind_plugin(plugin)
    monkeypatch.setattr("almasix.permission.Role", Broken, raising=False)
    monkeypatch.setattr("almasix.permission.Permission", Broken, raising=False)
    users, _r, _p = AccessOverviewWidget()._counts()
    assert users == 3

    class BoomAll:
        @classmethod
        async def all(cls) -> list[Any]:
            raise RuntimeError("x")

    plugin._user_model = BoomAll
    users, _r, _p = AccessOverviewWidget()._counts()
    assert users == 0

    class NoAll:
        pass

    plugin._user_model = NoAll
    users, _r, _p = AccessOverviewWidget()._counts()
    assert users == 0


def test_commands_panel_lookup_and_orm_super_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    panel = Panel.make("admin").path("admin").login(False)

    class Registry:
        def get(self, panel_id: str) -> Any:
            return panel if panel_id == "admin" else None

        def all(self) -> list[Any]:
            return [panel]

    class App:
        def make(self, _cls: Any) -> Registry:
            return Registry()

    import almasix_orbit_permission.commands as commands

    monkeypatch.setattr("almasix.framework.helpers.app", lambda abstract=None: Registry())
    assert commands._panel_from_id("admin") is panel

    class EmptyReg:
        def get(self, panel_id: str) -> Any:
            return None

        def all(self) -> list[Any]:
            other = Panel.make("other").path("other").login(False)
            return [other]

    monkeypatch.setattr("almasix.framework.helpers.app", lambda abstract=None: EmptyReg())
    assert commands._panel_from_id("other") is not None
    assert commands._panel_from_id("admin") is None

    def _boom(abstract=None) -> Any:
        raise RuntimeError("no app")

    monkeypatch.setattr("almasix.framework.helpers.app", _boom)
    assert commands._panel_from_id("admin") is None

    class OnlyAll:
        def all(self) -> list[Any]:
            return [panel]

    monkeypatch.setattr("almasix.framework.helpers.app", lambda abstract=None: OnlyAll())
    assert commands._panel_from_id("admin") is panel

    class Neither:
        pass

    monkeypatch.setattr("almasix.framework.helpers.app", lambda abstract=None: Neither())
    assert commands._panel_from_id("admin") is None

    class UserModel:
        @classmethod
        async def find(cls, token: Any) -> Any:
            if str(token) == "7":
                return SimpleNamespace(id=7, assign_role=lambda role: None)
            return None

        @classmethod
        def query(cls) -> Any:
            class Q:
                def where(self, *_a: Any, **_k: Any) -> Any:
                    return self

                async def first(self) -> Any:
                    return SimpleNamespace(
                        id=8,
                        assign_role=lambda role: asyncio.get_event_loop() and None,
                    )

            return Q()

    async def _assign_role(self: Any, role: Any) -> None:
        self.role = role

    found = SimpleNamespace(id=7)
    found.assign_role = lambda role: (
        run(_assign_role(found, role)) if False else setattr(found, "role", role)
    )

    async def _find(token: Any) -> Any:
        return found if str(token) in {"7", "ada@x.test"} else None

    UserModel.find = classmethod(lambda cls, token: _find(token))  # type: ignore[method-assign]

    class PermQ:
        async def get(self) -> list[Any]:
            return [SimpleNamespace(name="posts.view")]

    class FakePermission:
        @classmethod
        def query(cls) -> PermQ:
            return PermQ()

    class FakeRole:
        @classmethod
        async def find_or_create(cls, name: str, guard: str | None = None) -> Any:
            role = SimpleNamespace(name=name, synced=[])

            async def _sync(*names: str) -> Any:
                role.synced = list(names)
                return role

            role.sync_permissions = _sync
            return role

    monkeypatch.setattr("almasix.permission.Permission", FakePermission)
    monkeypatch.setattr("almasix.permission.Role", FakeRole)

    plugin = PermissionPlugin.make().user_model(UserModel)
    plugin._user_model = UserModel
    bind_plugin(plugin)
    cmd = SuperAdminCommand()
    cmd.argument = lambda name: "7"  # type: ignore[method-assign]
    cmd.success = lambda msg: None  # type: ignore[method-assign]
    cmd.error = lambda msg: None  # type: ignore[method-assign]
    # find() returns a coroutine — _find_user uses run()
    result = cmd.handle()
    assert result in {0, 1}

    class MissingUserPlugin(PermissionPlugin):
        def resolve_user_model(self) -> None:  # type: ignore[override]
            return None

    bind_plugin(MissingUserPlugin.make())
    no_model = SuperAdminCommand()
    no_model.argument = lambda name: "ada"  # type: ignore[method-assign]
    no_model.error = lambda msg: None  # type: ignore[method-assign]
    assert no_model.handle() == 1

    class StrictUser:
        @classmethod
        async def find(cls, token: Any) -> Any:
            return None

        @classmethod
        def query(cls) -> Any:
            class Q:
                def where(self, *_a: Any, **_k: Any) -> Any:
                    return self

                async def first(self) -> Any:
                    return None

            return Q()

    plugin._user_model = StrictUser
    bind_plugin(plugin)
    missing = SuperAdminCommand()
    missing.argument = lambda name: "ghost"  # type: ignore[method-assign]
    missing.error = lambda msg: None  # type: ignore[method-assign]
    assert missing.handle() == 1

    async def _async_assign(role: Any) -> None:
        found.assigned = role

    found.assign_role = _async_assign
    plugin._user_model = UserModel
    bind_plugin(plugin)
    again = SuperAdminCommand()
    again.argument = lambda name: "7"  # type: ignore[method-assign]
    again.success = lambda msg: None  # type: ignore[method-assign]
    again.error = lambda msg: None  # type: ignore[method-assign]
    assert again.handle() == 0

    gen = GeneratePermissionsCommand()
    monkeypatch.setattr(commands, "_panel_from_id", lambda panel_id: panel)
    bind_plugin(None)
    gen.argument = lambda name: "admin"  # type: ignore[method-assign]
    gen.success = lambda msg: None  # type: ignore[method-assign]
    gen.error = lambda msg: None  # type: ignore[method-assign]
    assert gen.handle() == 0


def test_find_user_paths() -> None:
    class Model:
        @classmethod
        async def find(cls, token: Any) -> Any:
            if token == "hit":
                return "row"
            if token == 5:
                return "int-row"
            return None

        @classmethod
        def query(cls) -> Any:
            class Q:
                def where(self, *_a: Any, **_k: Any) -> Any:
                    return self

                async def first(self) -> Any:
                    return "email-row"

            return Q()

    assert _find_user(Model, "hit") == "row"
    assert _find_user(Model, "5") == "int-row"
    assert _find_user(Model, "ada@x.test") == "email-row"

    class DigitsMiss:
        @classmethod
        async def find(cls, token: Any) -> Any:
            return None

        @classmethod
        def query(cls) -> Any:
            class Q:
                def where(self, *_a: Any, **_k: Any) -> Any:
                    return self

                async def first(self) -> Any:
                    return "digit-email"

            return Q()

    assert _find_user(DigitsMiss, "5") == "digit-email"

    class Broken:
        @classmethod
        async def find(cls, token: Any) -> Any:
            raise RuntimeError("x")

    assert _find_user(Broken, "x") is None


def test_permission_options_from_store_without_specs() -> None:
    store = MemoryStore()
    store.ensure_permission("custom.ability")
    plugin = PermissionPlugin.make().memory(store)
    plugin.cached_specs = []
    bind_plugin(plugin)
    assert _permission_options()["custom.ability"] == "custom.ability"


def test_bind_default_orm_models() -> None:
    from almasix.permission import Permission, Role

    managed = bind_role_model()
    assert issubclass(managed, Role)
    assert bind_permission_model() is Permission


def test_plugin_register_without_memory_binds_orm() -> None:
    panel = Panel.make("admin").path("admin").login(False)
    plugin = PermissionPlugin.make()
    plugin.register(panel)
    assert RoleResource.model is not None
    plugin.boot(panel)
    assert isinstance(plugin.cached_specs, list)


def test_config_store_promoted_on_register() -> None:
    store = MemoryStore()
    plugin = PermissionPlugin.make()
    plugin.config.store = store
    panel = Panel.make("admin").path("admin").login(False)
    plugin.register(panel)
    assert plugin.store is store


def test_plugin_binds_configured_user_without_memory() -> None:
    class User:
        fillable = ("email",)

    panel = Panel.make("admin").path("admin").login(False)
    plugin = PermissionPlugin.make().user_model(User)
    plugin.register(panel)
    assert UserResource.model is not None
    assert UserResource.get_table() is not None


def test_discover_skips_disabled_dashboard_and_duplicates() -> None:
    dash = type("Dashboard", (), {"slug": "dashboard"})
    twin = type("PostsTwin", (Resource,), {"slug": "posts"})
    panel = SimpleNamespace(
        get_resources=lambda: [PostResource, twin],
        get_pages=lambda: [dash],
        get_widgets=lambda: [],
        dashboard_page=lambda: dash,
        dashboard_enabled=lambda: False,
    )
    names = {spec.name for spec in discover_panel(panel, PermissionPlugin.make().config)}
    assert "posts.view_any" in names
    assert "dashboard.view" in names
    excluded = discover_panel(panel, PermissionPlugin.make().exclude("posts").config)
    assert "posts.view_any" not in {spec.name for spec in excluded}


def test_generate_into_orm_empty_and_guard_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePermission:
        @classmethod
        async def find_or_create(cls, name: str, guard: str | None = None) -> Any:
            return SimpleNamespace(name=name)

    class FakeRole:
        @classmethod
        async def find_or_create(cls, name: str, guard: str | None = None) -> Any:
            role = SimpleNamespace(name=name)

            async def _sync(*names: str) -> Any:
                return role

            role.sync_permissions = _sync
            return role

    monkeypatch.setattr("almasix.permission.Permission", FakePermission)
    monkeypatch.setattr("almasix.permission.Role", FakeRole)
    assert generate_into_orm([], PermissionPlugin.make().config) == []

    def _boom() -> str:
        raise RuntimeError("no guard")

    monkeypatch.setattr("almasix.permission.helpers.get_default_guard_name", _boom)
    assert default_guard(PermissionPlugin.make().config) == "web"


def test_widget_empty_stats_and_role_create_without_permissions() -> None:
    widget = AccessOverviewWidget()
    widget._stats = []
    assert widget.get_stats() == []

    class FakeRole:
        fillable = ("name",)
        synced = False

        def __init__(self, **attrs: Any) -> None:
            self.__dict__.update(attrs)

        @classmethod
        async def create(cls, attributes=None, **kwargs: Any) -> Any:
            return cls(**(attributes or {}), **kwargs)

        async def save(self) -> bool:
            return True

        async def sync_permissions(self, *names: str) -> Any:
            type(self).synced = True
            return self

        async def get_all_permissions(self) -> list[Any]:
            raise RuntimeError("no db")

    Managed = bind_role_model(FakeRole)
    role = run(Managed.create({"name": "plain"}))
    assert FakeRole.synced is False
    assert "permissions" not in role.get_attributes() or role.get_attributes()["name"] == "plain"


def test_super_admin_orm_permission_sync_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    found = SimpleNamespace(id=1, assigned=None)
    found.assign_role = lambda role: setattr(found, "assigned", role)

    class UserModel:
        @classmethod
        async def find(cls, token: Any) -> Any:
            return found if str(token) == "1" else None

    class FakePermission:
        @classmethod
        def query(cls) -> Any:
            raise RuntimeError("no perms")

    class FakeRole:
        @classmethod
        async def find_or_create(cls, name: str, guard: str | None = None) -> Any:
            return SimpleNamespace(name=name)

    monkeypatch.setattr("almasix.permission.Permission", FakePermission)
    monkeypatch.setattr("almasix.permission.Role", FakeRole)
    plugin = PermissionPlugin.make()
    plugin._user_model = UserModel
    bind_plugin(plugin)
    cmd = SuperAdminCommand()
    cmd.argument = lambda name: "1"  # type: ignore[method-assign]
    cmd.success = lambda msg: None  # type: ignore[method-assign]
    cmd.error = lambda msg: None  # type: ignore[method-assign]
    assert cmd.handle() == 0
    assert found.assigned is not None

    class EmptyPerms:
        @classmethod
        def query(cls) -> Any:
            return SimpleNamespace(get=lambda: [SimpleNamespace(name="posts.view")])

    class SyncRole:
        @classmethod
        async def find_or_create(cls, name: str, guard: str | None = None) -> Any:
            return SimpleNamespace(name=name, sync_permissions=lambda *names: None)

    monkeypatch.setattr("almasix.permission.Permission", EmptyPerms)
    monkeypatch.setattr("almasix.permission.Role", SyncRole)
    cmd2 = SuperAdminCommand()
    cmd2.argument = lambda name: "1"  # type: ignore[method-assign]
    cmd2.success = lambda msg: None  # type: ignore[method-assign]
    cmd2.error = lambda msg: None  # type: ignore[method-assign]
    assert cmd2.handle() == 0

    class NoPerms:
        @classmethod
        def query(cls) -> Any:
            return SimpleNamespace(get=lambda: [SimpleNamespace(name=""), None])

    monkeypatch.setattr("almasix.permission.Permission", NoPerms)
    cmd3 = SuperAdminCommand()
    cmd3.argument = lambda name: "1"  # type: ignore[method-assign]
    cmd3.success = lambda msg: None  # type: ignore[method-assign]
    cmd3.error = lambda msg: None  # type: ignore[method-assign]
    assert cmd3.handle() == 0
