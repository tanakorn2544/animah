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

def draw_timeline_markers():
    """Draw a colored strip at the TOP of the Dope Sheet for polish frames.
    Each keyframe marker uses its own custom color."""
    context = bpy.context

    if context.space_data is None or context.space_data.type not in {'DOPESHEET_EDITOR', 'TIMELINE'}:
        return

    obj = context.active_object
    if not obj or not hasattr(obj, "animah_tracks"):
        return

    active_idx = obj.animah_active_track_index
    if active_idx < 0 or active_idx >= len(obj.animah_tracks):
        return

    track = obj.animah_tracks[active_idx]
    settings = context.scene.animah_settings
    
    # Check if HUD is enabled
    if not settings or not settings.show_hud:
        return
    
    neighbor_range = settings.neighbor_range if settings else 4
    
    if not track.items:
        return

    # Optimization: Cache the action lookup
    action = None
    if obj.data and obj.data.shape_keys and obj.data.shape_keys.animation_data:
        action = obj.data.shape_keys.animation_data.action

    # Collect frame data as (left_edge, peak, right_edge, color) tuples
    frame_data = []
    
    # Resolve real-time positions from F-Curves
    for item in track.items:
        peak_frame = item.frame
        left_edge = peak_frame - neighbor_range
        right_edge = peak_frame + neighbor_range
        item_color = tuple(item.color)  # per-item color
        
        if action and item.shape_key_name:
            target_path = f'key_blocks["{item.shape_key_name}"].value'
            
            for fc in action.fcurves:
                if fc.data_path == target_path:
                    # Collect all keyframes with their values
                    kp_list = [(int(kp.co[0]), kp.co[1]) for kp in fc.keyframe_points]
                    kp_list.sort(key=lambda x: x[0])  # Sort by frame
                    
                    # Find the peak (highest value)
                    peak_idx = -1
                    peak_val = -1.0
                    for i, (frame, val) in enumerate(kp_list):
                        if val > peak_val:
                            peak_val = val
                            peak_idx = i
                            peak_frame = frame
                    
                    # Find left edge (keyframe before peak with lower value)
                    if peak_idx > 0:
                        left_edge = kp_list[peak_idx - 1][0]
                    else:
                        left_edge = peak_frame - neighbor_range
                    
                    # Find right edge (keyframe after peak with lower value)
                    if peak_idx < len(kp_list) - 1:
                        right_edge = kp_list[peak_idx + 1][0]
                    else:
                        right_edge = peak_frame + neighbor_range
                    
                    break
        
        frame_data.append((left_edge, peak_frame, right_edge, item_color))
        
    if not frame_data:
        return
        
    region = context.region
    view2d = region.view2d
    
    # HUD Settings - Fixed strip at the TOP of the editor
    strip_height = 8   # Height in pixels
    strip_margin = 2   # Margin from top edge
    
    y_max = region.height - strip_margin
    y_min = y_max - strip_height
    
    shader = get_shader_2d()
    gpu.state.blend_set('ALPHA')
    shader.bind()
    
    # Draw each item with its own color
    for left_edge, peak_frame, right_edge, item_color in frame_data:
        # Use clip=False so off-screen frames return real (extrapolated) pixel x,
        # not the 12345 sentinel that view_to_region returns with clip=True.
        xl_out, _ = view2d.view_to_region(left_edge, 0, clip=False)
        xr_out, _ = view2d.view_to_region(right_edge, 0, clip=False)
        peak_px_f, _ = view2d.view_to_region(peak_frame, 0, clip=False)
        peak_px = int(round(peak_px_f))

        # 1. Outer Falloff strip — only if at least partially on-screen.
        if xr_out >= 0 and xl_out <= region.width:
            outer_verts = [
                (xl_out, y_min), (xl_out, y_max),
                (xr_out, y_min), (xr_out, y_max)
            ]
            outer_indices = [(0, 1, 2), (1, 3, 2)]
            c = list(item_color)
            c[3] *= 0.25  # soft falloff alpha
            shader.uniform_float("color", tuple(c))
            batch_out = batch_for_shader(shader, 'TRIS', {"pos": outer_verts}, indices=outer_indices)
            batch_out.draw(shader)

        # 2. Pixel-aligned narrow bar AT the exact peak keyframe — confined to
        #    the strip height (same vertical extent as the falloff strip).
        if -1 <= peak_px <= region.width + 1:
            line_x0 = peak_px - 1
            line_x1 = peak_px + 2  # 3-px crisp bar centered on the keyframe pixel
            line_verts = [
                (line_x0, y_min), (line_x0, y_max),
                (line_x1, y_min), (line_x1, y_max)
            ]
            line_indices = [(0, 1, 2), (1, 3, 2)]
            c = list(item_color)
            c[3] *= 0.95  # strong alpha so the pin is clearly readable
            shader.uniform_float("color", tuple(c))
            batch_line = batch_for_shader(shader, 'TRIS', {"pos": line_verts}, indices=line_indices)
            batch_line.draw(shader)

    gpu.state.blend_set('NONE')

@bpy.app.handlers.persistent
def sync_list_to_timeline(scene, depsgraph=None):
    """Auto-highlight the item in the list that is closest to current frame"""
    # Safety checks
    obj = bpy.context.active_object
    if not obj or not getattr(obj, "animah_tracks", None):
        return
        
    if obj.animah_active_track_index < 0 or obj.animah_active_track_index >= len(obj.animah_tracks):
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
                    # Find the actual peak (highest value keyframe), matching the draw logic.
                    peak_frame = None
                    peak_val = -1.0
                    for kp in fcurve.keyframe_points:
                        if kp.co[1] > peak_val:
                            peak_val = kp.co[1]
                            peak_frame = int(kp.co[0])

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


@bpy.app.handlers.persistent
def force_animah_redraw(scene, depsgraph=None):
    """Force Dope Sheet and Timeline editors to redraw after any scene change"""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {'DOPESHEET_EDITOR', 'TIMELINE'}:
                area.tag_redraw()

def register():
    global _handle_dopesheet, _handle_timeline

    # Register sync handler
    if sync_list_to_timeline not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(sync_list_to_timeline)

    # Register depsgraph handler for forced refresh after edits
    if force_animah_redraw not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(force_animah_redraw)

    if _handle_dopesheet is None:
        _handle_dopesheet = bpy.types.SpaceDopeSheetEditor.draw_handler_add(draw_timeline_markers, (), 'WINDOW', 'POST_PIXEL')

    if _handle_timeline is None:
        _handle_timeline = bpy.types.SpaceTimeline.draw_handler_add(draw_timeline_markers, (), 'WINDOW', 'POST_PIXEL')

def unregister():
    global _handle_dopesheet, _handle_timeline
    if _handle_dopesheet is not None:
        bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_handle_dopesheet, 'WINDOW')
        _handle_dopesheet = None

    if _handle_timeline is not None:
        bpy.types.SpaceTimeline.draw_handler_remove(_handle_timeline, 'WINDOW')
        _handle_timeline = None

    if sync_list_to_timeline in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(sync_list_to_timeline)

    if force_animah_redraw in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(force_animah_redraw)
