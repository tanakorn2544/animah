import bpy
import gpu
from gpu_extras.batch import batch_for_shader

_handle_dopesheet = None
_handle_timeline = None
_shader_2d = None

_shader_2d = None

def get_shader_2d():
    global _shader_2d
    if not _shader_2d:
        _shader_2d = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader_2d

def draw_timeline_markers():
    """Draw gradient bars in the dopesheet for polish frames using Stepped Transparency (Safe Mode)"""
    context = bpy.context
    
    if context.space_data.type != 'DOPESHEET_EDITOR':
        return

    obj = context.active_object
    if not obj or not hasattr(obj, "animah_tracks"):
        return

    active_idx = obj.animah_active_track_index
    if active_idx >= len(obj.animah_tracks):
        return

    track = obj.animah_tracks[active_idx]
    settings = context.scene.animah_settings
    
    # Check if HUD is enabled
    if not settings or not settings.show_hud:
        return
    
    neighbor_range = settings.neighbor_range if settings else 4
    
    # Custom Color
    base_color = settings.hud_color if settings else (1.0, 0.4, 0.1, 1.0)
    
    if not track.items:
        return

    # Optimization: Cache the action lookup
    action = None
    if obj.data and obj.data.shape_keys and obj.data.shape_keys.animation_data:
        action = obj.data.shape_keys.animation_data.action

    # Collect frame data as (left_edge, peak, right_edge) tuples
    frame_data = []
    
    # Resolve real-time positions from F-Curves
    for item in track.items:
        peak_frame = item.frame
        left_edge = peak_frame - neighbor_range
        right_edge = peak_frame + neighbor_range
        
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
        
        frame_data.append((left_edge, peak_frame, right_edge))
        
    if not frame_data:
        return
        
    region = context.region
    view2d = region.view2d
    
    # HUD Settings - Bar positioned on Value channel row
    # Dope Sheet row layout (from top): Header, Summary, Object, Key, Value(s)
    # Typical row height is ~20px, header area ~45px
    header_offset = 45
    row_height = 20
    
    # Value channels are typically 4 rows down (Summary=1, Object=2, Key=3, Value=4)
    # We'll draw a bar for each tracked shape key value row
    value_row_index = 4  # 0-indexed from after header
    
    # We will draw 2 simple batches:
    # 1. Outer Soft Falloff (Based on actual keyframe edges)
    # 2. Inner Hard Center (The peak frame)
    
    # Coordinates lists
    outer_verts = []
    outer_indices = []
    
    inner_verts = []
    inner_indices = []
    
    # Batch counters
    o_idx = 0
    i_idx = 0
    
    for item_index, (left_edge, peak_frame, right_edge) in enumerate(frame_data):
        # Calculate Y position for this specific value channel row
        # Each value channel is one row below the last
        row_from_top = value_row_index + item_index
        y_max = region.height - header_offset - (row_from_top * row_height)
        y_min = y_max - row_height
        
        # 1. Outer Falloff (Based on actual keyframe positions)
        xl_out, _ = view2d.view_to_region(left_edge, 0)
        xr_out, _ = view2d.view_to_region(right_edge, 0)
        
        outer_verts.extend([
            (xl_out, y_min), (xl_out, y_max),
            (xr_out, y_min), (xr_out, y_max)
        ])
        outer_indices.extend([
            (o_idx, o_idx+1, o_idx+2), (o_idx+1, o_idx+3, o_idx+2)
        ])
        o_idx += 4
        
        # 2. Inner Center (Narrow highlight at peak)
        framewidth_l, _ = view2d.view_to_region(peak_frame - 0.2, 0)
        framewidth_r, _ = view2d.view_to_region(peak_frame + 0.2, 0)
        
        inner_verts.extend([
            (framewidth_l, y_min), (framewidth_l, y_max),
            (framewidth_r, y_min), (framewidth_r, y_max)
        ])
        inner_indices.extend([
            (i_idx, i_idx+1, i_idx+2), (i_idx+1, i_idx+3, i_idx+2)
        ])
        i_idx += 4

    shader = get_shader_2d()
    gpu.state.blend_set('ALPHA')
    shader.bind()
    
    # Draw Outer (Soft Gradient Simulation)
    if outer_verts:
        # Low Alpha (0.2 * base alpha)
        c = list(base_color)
        c[3] *= 0.2
        shader.uniform_float("color", tuple(c))
        batch_out = batch_for_shader(shader, 'TRIS', {"pos": outer_verts}, indices=outer_indices)
        batch_out.draw(shader)
        
    # Draw Inner (Strong Center)
    if inner_verts:
        # High Alpha (0.8 * base alpha)
        c = list(base_color)
        c[3] *= 0.8
        shader.uniform_float("color", tuple(c))
        batch_in = batch_for_shader(shader, 'TRIS', {"pos": inner_verts}, indices=inner_indices)
        batch_in.draw(shader)

    gpu.state.blend_set('NONE')

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


@bpy.app.handlers.persistent
def force_dopesheet_redraw(scene, depsgraph=None):
    """Force dopesheet to redraw after any scene change"""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'DOPESHEET_EDITOR':
                area.tag_redraw()

def register():
    global _handle_dopesheet, _handle_timeline
    
    # Register sync handler
    if sync_list_to_timeline not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(sync_list_to_timeline)
    
    # Register depsgraph handler for forced refresh after edits
    if force_dopesheet_redraw not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(force_dopesheet_redraw)

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
    
    if force_dopesheet_redraw in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(force_dopesheet_redraw)
