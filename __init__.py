bl_info = {
    "name": "Animah Polisher",
    "author": "Korn Sensei",
    "version": (0, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Animah",
    "description": "Shot sculpting and polish tool similar to Maya's Animatrix",
    "category": "Animation",
}

import bpy
from . import properties
from . import operators
from . import ui
from . import ghosting
from . import timeline

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
