import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, CollectionProperty, PointerProperty, EnumProperty, FloatVectorProperty

class PolishItem(bpy.types.PropertyGroup):
    """A single polish/corrective frame"""
    name: StringProperty(name="Name", default="Polish")
    frame: IntProperty(name="Frame")
    shape_key_name: StringProperty(name="Shape Key Name")
    
class PolishTrack(bpy.types.PropertyGroup):
    """A collection of polish items (e.g. for a specific body part)"""
    name: StringProperty(name="Track Name", default="Main Track")
    items: CollectionProperty(type=PolishItem)
    active_item_index: IntProperty(name="Active Item Index", default=0)
    
from . import ghosting

class PolisherSettings(bpy.types.PropertyGroup):
    """Global settings for the polisher"""
    auto_key_neighbors: BoolProperty(
        name="Auto-Key Neighbors",
        description="Automatically set 0 influence on previous/next frames",
        default=True
    )
    neighbor_range: IntProperty(
        name="Neighbor Range",
        description="How many frames away to set the 0 key",
        default=4,
        min=1,
        update=ghosting.update_ghosts
    )
    # Ghosting settings
    show_ghosts: BoolProperty(
        name="Show Ghosts",
        description="Show onion skinning/ghosts for previous and next neighbor frames",
        default=False,
        update=ghosting.update_ghosts
    )

    ghost_prev_color: FloatVectorProperty(
        name="Prev Color",
        subtype='COLOR',
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0.0, max=1.0,
        description="Color for previous frame ghost (RGBA)",
        update=ghosting.update_ghosts
    )
    ghost_next_color: FloatVectorProperty(
        name="Next Color",
        subtype='COLOR',
        default=(0.0, 1.0, 0.0, 0.5),
        size=4,
        min=0.0, max=1.0,
        description="Color for next frame ghost (RGBA)",
        update=ghosting.update_ghosts
    )
    ghost_length: IntProperty(
        name="Ghost Length",
        description="Number of frames to show in the ghost trail",
        default=3,
        min=1,
        max=20,
        update=ghosting.update_ghosts
    )
    ghost_type: EnumProperty(
        name="Ghost Type",
        description="Method for selecting ghost frames",
        items=[
            ('STEP', "Step", "Show ghosts at regular intervals"),
            ('KEYFRAME', "Keyframe", "Show ghosts only on keyframes"),
        ],
        default='STEP',
        update=ghosting.update_ghosts
    )
    ghost_step: IntProperty(
        name="Ghost Step",
        description="Frame interval between ghosts (for Step mode)",
        default=1,
        min=1,
        max=10,
        update=ghosting.update_ghosts
    )
    show_wireframe: BoolProperty(
        name="Show Wireframe",
        description="Draw ghosts as wireframes",
        default=False,
        update=ghosting.update_ghosts
    )

classes = (
    PolishItem,
    PolishTrack,
    PolisherSettings,
)

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # If already registered, likely a reload issue; ignore or unregister first (risky if different class obj)
            pass
            
    bpy.types.Object.animah_tracks = CollectionProperty(type=PolishTrack)
    bpy.types.Object.animah_active_track_index = IntProperty()
    bpy.types.Scene.animah_settings = PointerProperty(type=PolisherSettings)

def unregister():
    if hasattr(bpy.types.Scene, "animah_settings"):
        del bpy.types.Scene.animah_settings
    if hasattr(bpy.types.Object, "animah_active_track_index"):
        del bpy.types.Object.animah_active_track_index
    if hasattr(bpy.types.Object, "animah_tracks"):
        del bpy.types.Object.animah_tracks
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
