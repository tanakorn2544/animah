import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, CollectionProperty, PointerProperty, EnumProperty, FloatVectorProperty
from . import ghosting

class PolishItem(bpy.types.PropertyGroup):
    """A single polish/corrective frame"""
    name: StringProperty(name="Name", default="Polish")
    frame: IntProperty(name="Frame")
    shape_key_name: StringProperty(name="Shape Key Name")
    
class PolishTrack(bpy.types.PropertyGroup):
    """A collection of polish items (e.g. for a specific body part)"""
    name: StringProperty(name="Track Name", default="Main Track")
    items: CollectionProperty(type=PolishItem)
    
    def update_active_item_index(self, context):
        """Callback for when the list selection changes"""
        # If the change comes from our own auto-hightlight algorithm, ignore valid jumps
        settings = context.scene.animah_settings
        if settings.is_scrubbing:
            return
            
        # User clicked manually -> Jump to frame
        if self.items and 0 <= self.active_item_index < len(self.items):
            item = self.items[self.active_item_index]
            context.scene.frame_set(item.frame)
            
            # Also select the shape key for editing
            obj = context.active_object
            if obj and obj.type == 'MESH' and obj.data.shape_keys:
                sk_name = item.shape_key_name
                if sk_name in obj.data.shape_keys.key_blocks:
                    idx = obj.data.shape_keys.key_blocks.find(sk_name)
                    obj.active_shape_key_index = idx

    active_item_index: IntProperty(
        name="Active Item Index", 
        default=0,
        update=update_active_item_index
    )
    
def update_hud(self, context):
    """Force dopesheet redraw when HUD settings change"""
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'DOPESHEET_EDITOR':
                area.tag_redraw()

class PolisherSettings(bpy.types.PropertyGroup):
    """Global settings for the polisher"""
    auto_key_neighbors: BoolProperty(
        name="Auto-Key Neighbors",
        description="Automatically set 0 influence on previous/next frames",
        default=True
    )
    
    # Internal flag to prevent loop: FrameChange -> ListUpdate -> FrameSet -> FrameChange...
    is_scrubbing: BoolProperty(
        name="Is Scrubbing",
        default=False,
        options={'SKIP_SAVE', 'HIDDEN'}
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
    ghost_display_type: EnumProperty(
        name="Display Type",
        description="How to draw the ghosts",
        items=[
            ('SOLID', "Solid (Lit)", "Draw as 3D shaded solid"),
            ('SILHOUETTE', "Silhouette (Flat)", "Draw as flat silhouette"),
            ('WIRE', "Wireframe", "Draw as wireframe"),
        ],
        default='SILHOUETTE',
        update=ghosting.update_ghosts
    )
    
    show_hud: BoolProperty(
        name="Show HUD",
        description="Show timeline keyframe indicators in the Dope Sheet",
        default=True,
        update=update_hud
    )
    
    hud_color: FloatVectorProperty(
        name="HUD Color",
        subtype='COLOR',
        default=(1.0, 0.4, 0.1, 1.0),
        size=4,
        min=0.0, max=1.0,
        description="Color of the Timeline HUD indicators",
        update=update_hud
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
            # Class already registered
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
