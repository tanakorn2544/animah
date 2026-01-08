import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import bgl

# Global Cache: { frame_number: {'batch': batch, 'matrix': matrix} }
GHOST_CACHE = {}
_handler = None
_shader = None

def get_shader():
    global _shader
    if not _shader:
        try:
            _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        except:
            # Fallback for older Blender versions if needed, but 4.0+ uses UNIFORM_COLOR
            _shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    return _shader

def clear_cache():
    global GHOST_CACHE
    GHOST_CACHE.clear()
    # Force redraw
    if bpy.context.area:
        bpy.context.area.tag_redraw()

def bake_ghosts_to_memory(context):
    """Bake evaluated meshes to GPU batches for the entire range"""
    clear_cache()
    
    scene = context.scene
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return
        
    start = scene.frame_start
    end = scene.frame_end
    
    print(f"Baking Ghosts to GPU Memory from {start} to {end}...")
    
    # Store state
    original_frame = scene.frame_current
    original_mode = obj.mode
    
    # Needs to be in Object mode for clean eval usually, but let's try to respect
    
    try:
        for f in range(start, end + 1):
            scene.frame_set(f)
            depsgraph = context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            
            if mesh:
                # Extract coords and indices
                # We need loop triangles for drawing
                mesh.calc_loop_triangles()
                
                vertices = [v.co for v in mesh.vertices]
                indices = [tri.vertices for tri in mesh.loop_triangles]
                
                # Create Batch
                # UNIFORM_COLOR requires {"pos": ...}
                batch = batch_for_shader(get_shader(), 'TRIS', {"pos": vertices}, indices=indices)
                
                # Store
                GHOST_CACHE[f] = {
                    'batch': batch,
                    'matrix': eval_obj.matrix_world.copy()
                }
                
                eval_obj.to_mesh_clear()
                
    finally:
        scene.frame_set(original_frame)
        context.area.tag_redraw()
        print("GPU Bake Complete.")

def find_nearest_keyframes(obj, current_frame, count, direction):
    # Same helper as before
    if not obj.animation_data or not obj.animation_data.action:
        return []
    keyframes = set()
    for fcurve in obj.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            keyframes.add(int(kp.co[0]))
    sorted_keys = sorted(list(keyframes))
    if direction == 'PREV':
        candidates = [f for f in sorted_keys if f < current_frame]
        candidates.sort(reverse=True)
        return candidates[:count]
    else:
        candidates = [f for f in sorted_keys if f > current_frame]
        candidates.sort()
        return candidates[:count]

def draw_ghosts():
    context = bpy.context
    if not context.scene.animah_settings.show_ghosts:
        return
    
    # Only draw for active object
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return
        
    settings = context.scene.animah_settings
    current_frame = context.scene.frame_current
    
    shader = get_shader()
    shader.bind()
    
    # Setup Blending
    gpu.state.blend_set('ALPHA')
    
    # Calculate frames to draw
    frames_to_draw = [] # list of (frame, color, fade)
    
    length = settings.ghost_length
    step = settings.ghost_step
    
    # PREV
    frames = []
    if settings.ghost_type == 'KEYFRAME':
        frames = find_nearest_keyframes(obj, current_frame, length, 'PREV')
    else:
        for i in range(1, length + 1):
            frames.append(current_frame - (i * step))
            
    for i, f in enumerate(frames):
        if f in GHOST_CACHE:
            fade = 1.0 - (i / max(length, 1)) * 0.8
            col = list(settings.ghost_prev_color)
            col[3] *= fade
            frames_to_draw.append((f, col))
            
    # NEXT
    frames = []
    if settings.ghost_type == 'KEYFRAME':
        frames = find_nearest_keyframes(obj, current_frame, length, 'NEXT')
    else:
        for i in range(1, length + 1):
            frames.append(current_frame + (i * step))
            
    for i, f in enumerate(frames):
        if f in GHOST_CACHE:
            fade = 1.0 - (i / max(length, 1)) * 0.8
            col = list(settings.ghost_next_color)
            col[3] *= fade
            frames_to_draw.append((f, col))
            
    # DRAW
    for frame_idx, color in frames_to_draw:
        data = GHOST_CACHE.get(frame_idx)
        if not data:
            continue
            
        batch = data['batch']
        matrix = data['matrix']
        
        # Set Uniforms
        shader.uniform_float("color", color)
        
        gpu.matrix.push()
        gpu.matrix.multiply_matrix(matrix)
        
        if settings.show_wireframe:
            # Wireframe todo (needs edge batch)
            batch.draw(shader)
        else:
             batch.draw(shader)
             
        gpu.matrix.pop()
        
    gpu.state.blend_set('NONE')

def update_ghosts(self, context):
    # Just trigger redraw
    if context.area:
        context.area.tag_redraw()

def register():
    global _handler
    if _handler is None:
        _handler = bpy.types.SpaceView3D.draw_handler_add(draw_ghosts, (), 'WINDOW', 'POST_VIEW')

def unregister():
    global _handler
    if _handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handler, 'WINDOW')
        _handler = None
    clear_cache()
