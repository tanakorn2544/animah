bl_info = {
    "name": "Animah Polisher",
    "author": "Korn Sensei",
    "version": (2, 1, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Animah",
    "description": "Shot sculpting and polish tool similar to Maya's Animatrix",
    "category": "Animation",
}

import bpy

# F3 → Reload Scripts only re-runs __init__.py; Python caches sub-modules in
# sys.modules so edits to those files never reach Blender. Detect the reload
# case and force-reload sub-modules so live development works without a restart.
_g = globals()
if "_animah_modules_loaded" in _g:
    import importlib
    for _mod_name in ("properties", "operators", "ui", "ghosting", "timeline"):
        _mod = _g.get(_mod_name)
        try:
            if _mod is not None:
                _g[_mod_name] = importlib.reload(_mod)
            else:
                _g[_mod_name] = importlib.import_module(f".{_mod_name}", package=__package__)
        except Exception:
            # sys.modules entry was purged or stale — re-import fresh
            _g[_mod_name] = importlib.import_module(f".{_mod_name}", package=__package__)
else:
    from . import properties, operators, ui, ghosting, timeline

_animah_modules_loaded = True

def register():
    properties.register()
    operators.register()
    ui.register()
    ghosting.register()
    timeline.register()

def unregister():
    timeline.unregister()
    ghosting.unregister()
    ui.unregister()
    operators.unregister()
    properties.unregister()

if __name__ == "__main__":
    register()
