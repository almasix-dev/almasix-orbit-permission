"""Discover panel entities and build permission names."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from almasix_orbit_permission.config import (
    ABILITY_LABELS,
    PAGE_ABILITIES,
    RESOURCE_ABILITIES,
    SOFT_DELETE_ABILITIES,
    WIDGET_ABILITIES,
    PermissionPluginConfig,
)


@dataclass(frozen=True)
class PermissionSpec:
    """One generated ability."""

    name: str
    entity: str
    ability: str
    kind: str
    label: str


def ability_label(ability: str) -> str:
    return ABILITY_LABELS.get(ability, ability.replace("_", " ").title())


def permission_name(entity: str, ability: str) -> str:
    return f"{entity}.{ability}"


def entity_slug(obj: Any, *, fallback: str) -> str:
    getter = getattr(obj, "get_permission_prefix", None)
    if callable(getter):
        prefix = getter()
        if prefix:
            return str(prefix)
    prefix = getattr(obj, "permission_prefix", None)
    if prefix:
        return str(prefix)
    getter = getattr(obj, "get_slug", None)
    if callable(getter):
        slug = getter()
        if slug:
            return str(slug)
    slug = getattr(obj, "slug", None)
    if slug:
        return str(slug)
    name = getattr(obj, "__name__", fallback)
    text = str(name)
    for suffix in ("Resource", "Page", "Widget", "Plugin"):
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
            break
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch.isupper() and i:
            out.append("_")
        out.append(ch.lower())
    return "".join(out) or fallback


def prefixes_for(obj: Any, *, kind: str) -> tuple[str, ...]:
    getter = getattr(obj, "get_permission_prefixes", None)
    if callable(getter):
        values = getter()
        return tuple(str(v) for v in values if v)
    if kind == "resource":
        abilities = RESOURCE_ABILITIES
        if getattr(obj, "soft_deletes", False):
            abilities = abilities + SOFT_DELETE_ABILITIES
        return abilities
    if kind == "page":
        return PAGE_ABILITIES
    if kind == "widget":
        return WIDGET_ABILITIES
    return ()


def _excluded(config: PermissionPluginConfig, obj: Any, slug: str) -> bool:
    names = {slug, getattr(obj, "__name__", ""), entity_slug(obj, fallback=slug)}
    skip = {str(x) for x in config.exclude}
    return bool(names & skip)


def specs_for_object(obj: Any, *, kind: str) -> list[PermissionSpec]:
    slug = entity_slug(obj, fallback=kind)
    out: list[PermissionSpec] = []
    for ability in prefixes_for(obj, kind=kind):
        name = permission_name(slug, ability)
        out.append(
            PermissionSpec(
                name=name,
                entity=slug,
                ability=ability,
                kind=kind,
                label=f"{slug.replace('_', ' ').title()} · {ability_label(ability)}",
            )
        )
    return out


def discover_panel(
    panel: Any, config: PermissionPluginConfig | None = None
) -> list[PermissionSpec]:
    """Collect resource / page / widget abilities from a live panel."""
    cfg = config or PermissionPluginConfig()
    found: list[PermissionSpec] = []
    seen: set[str] = set()

    def _add(specs: Iterable[PermissionSpec]) -> None:
        for spec in specs:
            if spec.name in seen:
                continue
            seen.add(spec.name)
            found.append(spec)

    resources = list(getattr(panel, "get_resources", lambda: [])() or [])
    for resource in resources:
        slug = entity_slug(resource, fallback="resource")
        if _excluded(cfg, resource, slug):
            continue
        _add(specs_for_object(resource, kind="resource"))

    pages = list(getattr(panel, "get_pages", lambda: [])() or [])
    dash = None
    getter = getattr(panel, "dashboard_page", None)
    if callable(getter) and getattr(panel, "dashboard_enabled", lambda: False)():
        dash = getter()
    for page in pages:
        if dash is not None and page is dash:
            continue
        slug = entity_slug(page, fallback="page")
        if _excluded(cfg, page, slug):
            continue
        _add(specs_for_object(page, kind="page"))

    widgets = list(getattr(panel, "get_widgets", lambda: [])() or [])
    for widget in widgets:
        slug = entity_slug(widget, fallback="widget")
        if _excluded(cfg, widget, slug):
            continue
        _add(specs_for_object(widget, kind="widget"))

    for extra in cfg.extra_permissions:
        name = str(extra).strip()
        if not name or name in seen:
            continue
        if "." in name:
            entity, ability = name.split(".", 1)
        else:
            entity, ability = "custom", name
        seen.add(name)
        found.append(
            PermissionSpec(
                name=name,
                entity=entity,
                ability=ability,
                kind="custom",
                label=name,
            )
        )
    return found


def grouped_options(specs: list[PermissionSpec]) -> dict[str, dict[str, str]]:
    """``{entity: {permission_name: label}}`` for checkbox lists."""
    groups: dict[str, dict[str, str]] = {}
    for spec in specs:
        bucket = groups.setdefault(spec.entity, {})
        bucket[spec.name] = ability_label(spec.ability)
    return groups
