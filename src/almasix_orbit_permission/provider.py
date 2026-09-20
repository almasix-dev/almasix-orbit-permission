"""Register smith commands. The plugin itself stays passive (``.plugin(...)``)."""

from __future__ import annotations

from almasix.providers import ServiceProvider


class OrbitPermissionProvider(ServiceProvider):
    def boot(self) -> None:
        from almasix_orbit_permission.commands import ORBIT_PERMISSION_COMMANDS

        self.commands(ORBIT_PERMISSION_COMMANDS)
