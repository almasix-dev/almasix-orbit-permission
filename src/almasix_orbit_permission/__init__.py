"""Official Orbit plugin: Users, Roles, and Permissions on almasix-permission."""

from almasix_orbit_permission.auth import HasOrbitPermissions
from almasix_orbit_permission.plugin import PermissionPlugin
from almasix_orbit_permission.resources import PermissionResource, RoleResource, UserResource
from almasix_orbit_permission.store import MemoryStore
from almasix_orbit_permission.widgets import AccessOverviewWidget

__all__ = [
    "AccessOverviewWidget",
    "HasOrbitPermissions",
    "MemoryStore",
    "PermissionPlugin",
    "PermissionResource",
    "RoleResource",
    "UserResource",
    "__version__",
]

__version__ = "0.1.0"
