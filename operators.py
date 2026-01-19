import bpy
from .properties import PolishItem

class ANIMAH_OT_add_track(bpy.types.Operator):
    """Add a new polish track"""
    bl_idname = "animah.add_track"
    bl_label = "Add Track"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}
        
        track = obj.animah_tracks.add()
        track.name = f"Track {len(obj.animah_tracks)}"
        obj.animah_active_track_index = len(obj.animah_tracks) - 1
        
        return {'FINISHED'}

class ANIMAH_OT_remove_track(bpy.types.Operator):
    """Remove the active polish track"""
    bl_idname = "animah.remove_track"
    bl_label = "Remove Track"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.animah_tracks:
            return {'CANCELLED'}
            
        obj.animah_tracks.remove(obj.animah_active_track_index)
        
        # Adjust index
        if obj.animah_active_track_index >= len(obj.animah_tracks):
            obj.animah_active_track_index = max(0, len(obj.animah_tracks) - 1)
            
        return {'FINISHED'}

class ANIMAH_OT_bake_ghosts(bpy.types.Operator):
    """Bake ghosts for the entire animation (allows scrubbing/playback without lag)"""
    bl_idname = "animah.bake_ghosts"
    bl_label = "Bake Ghosts"
    
    def execute(self, context):
        from . import ghosting
        ghosting.bake_ghosts_to_memory(context)
        # Enable display if not enabled
        context.scene.animah_settings.show_ghosts = True
        return {'FINISHED'}

class ANIMAH_OT_add_polish_frame(bpy.types.Operator):
    """Add a polish shape key for the current frame"""
    bl_idname = "animah.add_polish_frame"
    bl_label = "Sculpt This Frame"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a Mesh")
            return {'CANCELLED'}
            
        # Ensure we have tracks
        if not obj.animah_tracks:
            bpy.ops.animah.add_track()
            
        track = obj.animah_tracks[obj.animah_active_track_index]
        current_frame = context.scene.frame_current
        
        # Check if shape key already exists for this frame in this track? 
        # For now, let's allow multiples or just name strictly.
        shape_name = f"{track.name}_F{current_frame}"
        
        # Ensure Basis exists
        if not obj.data.shape_keys:
            obj.shape_key_add(name="Basis")
            
        # Create new Shape Key
        sk = obj.shape_key_add(name=shape_name)
        sk.value = 1.0
        
        # Keyframe it
        # 1. Keyframe 1.0 at current frame
        sk.keyframe_insert(data_path="value", frame=current_frame)
        
        # 2. Keyframe 0.0 at neighbors
        settings = context.scene.animah_settings
        if settings.auto_key_neighbors:
            range_val = settings.neighbor_range
            sk.value = 0.0
            sk.keyframe_insert(data_path="value", frame=current_frame - range_val)
            sk.keyframe_insert(data_path="value", frame=current_frame + range_val)
            
        # Reset value to 1.0 for sculpting
        sk.value = 1.0
        
        # SMOOTHING LOGIC
        # Find the fcurve and set handle types
        if obj.data.shape_keys and obj.data.shape_keys.animation_data and obj.data.shape_keys.animation_data.action:
            action = obj.data.shape_keys.animation_data.action
            # The data path for a shape key value is usually key_blocks["Name"].value
            data_path = f'key_blocks["{sk.name}"].value'
            
            fcurve = list(filter(lambda fc: fc.data_path == data_path, action.fcurves))
            if fcurve:
                fc = fcurve[0]
                for kp in fc.keyframe_points:
                    kp.interpolation = 'BEZIER'
                    # Set handles to AUTO_CLAMPED for smooth ease in/out
                    kp.handle_left_type = 'AUTO_CLAMPED'
                    kp.handle_right_type = 'AUTO_CLAMPED'
                fc.update()

        # Add to track data
        item = track.items.add()
        item.name = shape_name
        item.frame = current_frame
        item.shape_key_name = sk.name
        
        # make it active
        obj.active_shape_key_index = obj.data.shape_keys.key_blocks.find(sk.name)
        
        # Switch to Sculpt Mode
        bpy.ops.object.mode_set(mode='SCULPT')
        
        self.report({'INFO'}, f"Added Polish Frame: {shape_name}")
        return {'FINISHED'}

class ANIMAH_OT_remove_polish_item(bpy.types.Operator):
    """Remove the selected polish item and delete its shape key"""
    bl_idname = "animah.remove_polish_item"
    bl_label = "Remove Polish Item"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        if not obj.animah_tracks:
            return False
        track = obj.animah_tracks[obj.animah_active_track_index]
        return len(track.items) > 0
    
    def execute(self, context):
        obj = context.active_object
        track = obj.animah_tracks[obj.animah_active_track_index]
        
        if not track.items:
            self.report({'WARNING'}, "No items to remove")
            return {'CANCELLED'}
        
        # Get the item to remove
        item_index = track.active_item_index
        item = track.items[item_index]
        shape_key_name = item.shape_key_name
        
        # 1. Remove the shape key from the mesh
        if obj.data.shape_keys and shape_key_name in obj.data.shape_keys.key_blocks:
            sk = obj.data.shape_keys.key_blocks[shape_key_name]
            obj.shape_key_remove(sk)
            self.report({'INFO'}, f"Deleted Shape Key: {shape_key_name}")
        else:
            self.report({'WARNING'}, f"Shape Key '{shape_key_name}' not found on mesh")
        
        # 2. Remove the item from the track
        track.items.remove(item_index)
        
        # 3. Adjust the active index
        if track.active_item_index >= len(track.items):
            track.active_item_index = max(0, len(track.items) - 1)
        
        return {'FINISHED'}


class ANIMAH_OT_reset_polish_frame(bpy.types.Operator):
    """Reset the active shape key to match Basis (Clear Sculpt)"""
    bl_idname = "animah.reset_polish_frame"
    bl_label = "Reset Sculpt"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and 
                obj.active_shape_key and 
                obj.active_shape_key.name != "Basis")

    def execute(self, context):
        obj = context.active_object
        active_sk = obj.active_shape_key
        basis_sk = obj.data.shape_keys.key_blocks.get("Basis")
        
        if not basis_sk:
            self.report({'ERROR'}, "No Basis shape key found")
            return {'CANCELLED'}

        # 1. Reset all shape keys to 0
        for sk in obj.data.shape_keys.key_blocks:
            sk.value = 0.0
            
        # 2. Set current to 1
        active_sk.value = 1.0

        # 3. Reset vertices to Basis
        # Using foreach_set is much faster than iterating
        coords = [0.0] * (len(obj.data.vertices) * 3)
        basis_sk.data.foreach_get("co", coords)
        active_sk.data.foreach_set("co", coords)
        
        # Update mesh
        obj.data.update()
        
        self.report({'INFO'}, f"Reset Shape Key: {active_sk.name}")
        return {'FINISHED'}

classes = (
    ANIMAH_OT_add_track,
    ANIMAH_OT_remove_track,
    ANIMAH_OT_add_polish_frame,
    ANIMAH_OT_remove_polish_item,
    ANIMAH_OT_reset_polish_frame,
    ANIMAH_OT_bake_ghosts,
)

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
