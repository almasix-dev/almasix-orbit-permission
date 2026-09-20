"""In-memory access records used by tests and as a fallback without ORM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryStore:
    """Dict-backed users, roles, and permissions."""

    roles: list[dict[str, Any]] = field(default_factory=list)
    permissions: list[dict[str, Any]] = field(default_factory=list)
    users: list[dict[str, Any]] = field(default_factory=list)
    _next_id: int = 1

    def _id(self) -> int:
        value = self._next_id
        self._next_id += 1
        return value

    def list_roles(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.roles]

    def list_permissions(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.permissions]

    def list_users(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.users]

    def ensure_permission(self, name: str, *, guard: str = "web") -> dict[str, Any]:
        for row in self.permissions:
            if row.get("name") == name and row.get("guard_name") == guard:
                return dict(row)
        row = {"id": self._id(), "name": name, "guard_name": guard}
        self.permissions.append(row)
        return dict(row)

    def ensure_role(self, name: str, *, guard: str = "web") -> dict[str, Any]:
        for row in self.roles:
            if row.get("name") == name and row.get("guard_name") == guard:
                return dict(row)
        row = {
            "id": self._id(),
            "name": name,
            "guard_name": guard,
            "permissions": [],
        }
        self.roles.append(row)
        return dict(row)

    def replace_roles(self, rows: list[dict[str, Any]]) -> None:
        self.roles = [dict(row) for row in rows]

    def replace_permissions(self, rows: list[dict[str, Any]]) -> None:
        self.permissions = [dict(row) for row in rows]

    def replace_users(self, rows: list[dict[str, Any]]) -> None:
        self.users = [dict(row) for row in rows]

    def sync_role_permissions(self, role_id: Any, names: list[str]) -> None:
        wanted = [str(n) for n in names if n]
        for row in self.roles:
            if str(row.get("id")) == str(role_id):
                row["permissions"] = list(wanted)
                return

    def sync_user_roles(self, user_id: Any, names: list[str]) -> None:
        wanted = [str(n) for n in names if n]
        for row in self.users:
            if str(row.get("id")) == str(user_id):
                row["roles"] = list(wanted)
                return

    def sync_user_permissions(self, user_id: Any, names: list[str]) -> None:
        wanted = [str(n) for n in names if n]
        for row in self.users:
            if str(row.get("id")) == str(user_id):
                row["permissions"] = list(wanted)
                return

    def grant_all_to_role(self, role_name: str, *, guard: str = "web") -> dict[str, Any]:
        role = self.ensure_role(role_name, guard=guard)
        names = [str(row["name"]) for row in self.permissions if row.get("guard_name") == guard]
        self.sync_role_permissions(role["id"], names)
        role["permissions"] = names
        return dict(role)
