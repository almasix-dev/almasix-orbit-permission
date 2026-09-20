# Example panel

`panel.py` registers `PermissionPlugin` on a login-free admin panel with an in-memory store (no database). Use it as a wiring reference, not a runnable app by itself.

```python
from almasix_orbit_permission import PermissionPlugin

panel.plugin(
    PermissionPlugin.make()
    .navigation_group("Access")
    .memory()
    .generate_on_boot()
)
```
