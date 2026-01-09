import bpy
import gpu
from gpu_extras.batch import batch_for_shader

_handle_dopesheet = None
_handle_timeline = None
_shader_2d = None

def get_shader_2d():
    global _shader_2d
    if not _shader_2d:
        _shader_2d = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader_2d

@bpy.app.handlers.persistent
def sync_list_to_timeline(scene, depsgraph=None):
    """Auto-highlight the item in the list that is closest to current frame"""
    # Safety checks
    obj = bpy.context.active_object
    if not obj or not getattr(obj, "animah_tracks", None):
        return
        
    if obj.animah_active_track_index >= len(obj.animah_tracks):
        return
        
    track = obj.animah_tracks[obj.animah_active_track_index]
    if not track.items:
        return
        
    current_frame = scene.frame_current
    
    # 1. Update item frames from actual F-Curves (in case user moved keys in Dope Sheet)
    # This ensures consistency
    if obj.data and obj.data.shape_keys and obj.data.shape_keys.animation_data and obj.data.shape_keys.animation_data.action:
        action = obj.data.shape_keys.animation_data.action
        # Cache fcurves lookup? action.fcurves.find is decent.
        
        for t in obj.animah_tracks:
            for item in t.items:
                sk_name = item.shape_key_name
                if not sk_name: 
                    continue
                    
                data_path = f'key_blocks["{sk_name}"].value'
                fcurve = action.fcurves.find(data_path)
                
                if fcurve:
                    # Find the "Peak" keyframe (value close to 1.0)
                    # Optimization: Likely checking just the keypoints is fast enough for typical counts
                    peak_frame = None
                    for kp in fcurve.keyframe_points:
                        if kp.co[1] > 0.5: # Assuming peak is significant
                            peak_frame = int(kp.co[0])
                            break
                    
                    if peak_frame is not None and peak_frame != item.frame:
                        item.frame = peak_frame
    
    # Find closest item
    closest_idx = -1

    min_dist = float('inf')
    
    for i, item in enumerate(track.items):
        dist = abs(item.frame - current_frame)
        if dist < min_dist:
            min_dist = dist
            closest_idx = i
            
    # Update UI if needed
    if closest_idx != -1 and closest_idx != track.active_item_index:
        # Lock preventing the update callback from jumping the timeline back
        if hasattr(scene, "animah_settings") and scene.animah_settings:
            scene.animah_settings.is_scrubbing = True
            track.active_item_index = closest_idx
            scene.animah_settings.is_scrubbing = False


def draw_timeline_markers():
    """Draw markers in the timeline/dopesheet for polish frames"""
    context = bpy.context
    obj = context.active_object
    if not obj or not obj.animah_tracks:
        return
    
    # Check if we are in a valid region?
    # Actually, we rely on the draw_handler space type.
    
    # Collect frames
    # We want to draw markers for ALL items in ALL tracks? Or just active track?
    # Maybe different colors?
    # Let's draw Active Track items in Bright Color, others in Dim Color.
    
    active_idx = obj.animah_active_track_index
    
    active_frames = set()
    other_frames = set()
    
    for i, track in enumerate(obj.animah_tracks):
        is_active = (i == active_idx)
        for item in track.items:
            if is_active:
                active_frames.add(item.frame)
            else:
                other_frames.add(item.frame)
                
    # If a frame is in both, active takes precedence
    other_frames = other_frames - active_frames
    
    if not active_frames and not other_frames:
        return
        
    # Prepare Batches
    shader = get_shader_2d()
    shader.bind()
    gpu.state.blend_set('ALPHA')
    
    # Region View coordinates
    # We need to map Frame to X pixel.
    # bpy.types.View2D can act as converter?
    # context.region.view2d.view_to_region(x, y)
    
    # But wait, in Dopesheet, the view is (Frame, ChannelIndex).
    # In Timeline, it's (Frame, 0).
    # We want to draw a vertical line or a marker at top?
    # Usually overlays draw strips.
    
    region = context.region
    view2d = region.view2d
    
    # We Draw vertical lines spanning the view?
    # y min/max
    y_min = 0
    y_max = region.height
    
    # Helper to draw set of frames
    def draw_set(frames, color_rgba):
        coords = []
        for f in frames:
            # Map frame to region X
            x_r, _ = view2d.view_to_region(f, 0)
            
            # Simple line width 2px
            coords.append((x_r, y_min))
            coords.append((x_r, y_max))
            
        if not coords:
            return
            
        shader.uniform_float("color", color_rgba)
        batch = batch_for_shader(shader, 'LINES', {"pos": coords})
        batch.draw(shader)
        
    # Draw Others (Dim)
    draw_set(other_frames, (0.5, 0.5, 0.5, 0.3))
    
    # Draw Active (Bright Orange)
    draw_set(active_frames, (1.0, 0.5, 0.0, 0.6))
    
    gpu.state.blend_set('NONE')


def register():
    global _handle_dopesheet, _handle_timeline
    
    # Register sync handler
    if sync_list_to_timeline not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(sync_list_to_timeline)

    
    if _handle_dopesheet is None:
        _handle_dopesheet = bpy.types.SpaceDopeSheetEditor.draw_handler_add(draw_timeline_markers, (), 'WINDOW', 'POST_PIXEL')
        
    if _handle_timeline is None:
        # Timeline is technically SpaceGraphEditor? No SpaceTimeline?
        # Actually SpaceDopeSheetEditor covers Action Editor, Dope Sheet.
        # Logic Editor -> Timeline is separate?
        # Blender 4.0: Timeline is just a Dopesheet mode usually? No handle separate?
        # Actually `SpaceTimeline` exists but often we use DopeSheet for seeing keys.
        # Let's add to SpaceGraphEditor (F-Curves) too?
        # Let's stick to Dopesheet for now.
        pass

def unregister():
    global _handle_dopesheet
    if _handle_dopesheet is not None:
        bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_handle_dopesheet, 'WINDOW')
        _handle_dopesheet = None
        
    if sync_list_to_timeline in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(sync_list_to_timeline)
