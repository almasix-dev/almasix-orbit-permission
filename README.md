# almasix-orbit-permission

[![PyPI](https://img.shields.io/pypi/v/almasix-orbit-permission?label=pypi&v=0.1.0)](https://pypi.org/project/almasix-orbit-permission/)
[![CI](https://github.com/almasix-dev/almasix-orbit-permission/actions/workflows/ci.yml/badge.svg)](https://github.com/almasix-dev/almasix-orbit-permission/actions/workflows/ci.yml)

Opinionated **Users, Roles, and Permissions** UI for [Orbit](https://orbit.almasix.com/) panels, built on [`almasix-permission`](https://permission.almasix.com/).

Register the plugin on a panel. Orbit never auto-discovers plugins.

## Install

```bash
pip install almasix-orbit-permission
```

Your user model must mix in `HasRoles` from `almasix-permission`, and the permission tables must be migrated.

```python
from almasix.auth import AuthenticatableMixin
from almasix.orm import Model
from almasix.permission import HasRoles

from almasix_orbit_permission import HasOrbitPermissions

class User(HasOrbitPermissions, HasRoles, AuthenticatableMixin, Model):
    fillable = ("email", "name", "password")
```

```python title="app/orbit/admin/panel.py"
from almasix.orbit import Panel, PanelRegistry
from almasix_orbit_permission import PermissionPlugin

def register_admin_panel(registry: PanelRegistry) -> Panel:
    panel = (
        Panel.make("admin")
        .path("admin")
        .plugin(
            PermissionPlugin.make()
            .navigation_group("Access")
            .generate_on_boot()
        )
    )
    registry.register(panel)
    return panel
```

That adds three resources — **Users**, **Roles**, **Permissions** — plus an Access stats widget on the dashboard.

## What you get

- **Roles** with a checkbox list of abilities (`posts.view_any`, `posts.create`, …)
- **Permissions** as first-class rows (create extras, or let the generator fill them)
- **Users** with role assignment and optional direct permissions
- **Generator** that walks the panel’s resources, pages, and widgets and creates matching abilities
- **Super-admin role** (`super_admin` by default) that receives every generated ability
- **Dashboard widget** with user / role / permission counts

Abilities follow Orbit’s existing names: `{prefix}.view_any`, `.view`, `.create`, `.update`, `.delete`, plus `.restore` / `.force_delete` when the resource uses soft deletes. A resource can declare its own list:

```python
class PostResource(Resource):
    @classmethod
    def get_permission_prefixes(cls) -> list[str]:
        return ["view_any", "view", "create", "update", "delete", "publish"]
```

## Commands

```bash
smith orbit-permission:generate admin
smith orbit-permission:super-admin ada@example.com
```

`generate` is also available as `python -m` once the provider is discovered (`OrbitPermissionProvider` is registered via the `almasix.providers` entry point).

## Options

```python
PermissionPlugin.make()
    .navigation_group("Access")
    .super_admin_role("super_admin")
    .guard("web")
    .exclude("RoleResource", "PermissionResource")  # skip generating for these
    .extra_permissions("impersonate")
    .user_model("app.models.user.User")
    .generate_on_boot()
    .without_widget()
```

`.memory()` swaps the ORM for an in-memory store (tests and demos without a database).

## Marketplace

Listing: [orbit.almasix.com/plugins/orbit-permission](https://orbit.almasix.com/plugins/orbit-permission/).
