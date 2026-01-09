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
    if bpy.context.area:
        bpy.context.area.tag_redraw()

_lit_shader = None
def get_lit_shader():
    global _lit_shader
    if not _lit_shader:
        vertex_shader = '''
            in vec3 pos;
            in vec3 normal;
            uniform mat4 viewProjectionMatrix;
            uniform mat4 modelMatrix;
            uniform vec4 color;
            out vec4 f_color;
            
            void main() {
                vec3 world_normal = normalize(mat3(modelMatrix) * normal);
                vec3 light_dir = normalize(vec3(0.5, 0.5, 1.0)); // Fixed light from camera-ish
                float diff = max(dot(world_normal, light_dir), 0.0);
                float ambient = 0.3;
                
                vec3 lit_col = color.rgb * (diff + ambient);
                
                gl_Position = viewProjectionMatrix * modelMatrix * vec4(pos, 1.0);
                f_color = vec4(lit_col, color.a);
            }
        '''
        fragment_shader = '''
            in vec4 f_color;
            out vec4 fragColor;
            void main() {
                fragColor = f_color;
            }
        '''
        _lit_shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
    return _lit_shader


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
                # Ensure normals are calculated for 'SOLID' mode
                pass

                
                vertices = [v.co for v in mesh.vertices]
                indices = [tri.vertices for tri in mesh.loop_triangles]
                
                # To draw with normals, we need to pass them.
                # 'TRIS' expects specific format depending on shader.
                # For `3D_UNIFORM_COLOR` (flat), we only need pos.
                # For a Lit look, we might need a custom shader or `3D_SMOOTH_COLOR` with fake light color?
                # Actually, `3D_SMOOTH_COLOR` requires specific vertex colors.
                # Simplest "Lit" look in GPU module without custom shader complexity:
                # Use a custom shader that takes Normal and LightDir.
                
                # Let's bake Normals anyway.
                # Note: mesh.vertices[i].normal is the vertex normal.
                normals = [v.normal for v in mesh.vertices]
                
                # We create Two Batches? Or one batch with all info?
                # UNIFORM_COLOR only uses 'pos'.
                # A custom shader will use 'pos' and 'normal'.
                
                # Let's create a batch with both.
                # batch_for_shader can take extra args but builtins might ignore them.
                
                batch_data = {"pos": vertices, "normal": normals}
                
                # We need a shader that uses normals.
                # If we use built-in, we are limited.
                # Let's stick to flat UNIFORM_COLOR for Silhouette/Wireframe.
                # For Solid, we can try to use a simple custom shader.
                
                # We need a shader that uses normals.
                # Use the Lit shader to define the batch layout so it accepts normals.
                
                batch = batch_for_shader(get_lit_shader(), 'TRIS', batch_data, indices=indices)
                
                # Wireframe needs edges ideally.
                # calc_loop_triangles doesn't give edges directly in a way beneficial for wireframe overlay on tris?
                # Actually `mesh.edges` exists.
                edge_indices = [e.vertices for e in mesh.edges]
                batch_wire = batch_for_shader(gpu.shader.from_builtin('UNIFORM_COLOR'), 'LINES', {"pos": vertices}, indices=edge_indices)
                
                # Store
                GHOST_CACHE[f] = {
                    'batch': batch,
                    'batch_wire': batch_wire,
                    'matrix': eval_obj.matrix_world.copy()
                }
                
                eval_obj.to_mesh_clear()
                
    finally:
        scene.frame_set(original_frame)
        context.area.tag_redraw()
        print("GPU Bake Complete.")



def draw_ghosts():
    context = bpy.context
    if not context.scene.animah_settings.show_ghosts:
        return
    
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return
        
    settings = context.scene.animah_settings
    current_frame = context.scene.frame_current
    
    display_type = settings.ghost_display_type
    
    # Select Shader
    shader = None
    if display_type == 'SOLID':
        shader = get_lit_shader()
    else:
        shader = get_shader() # UNIFORM_COLOR
        
    shader.bind()
    
    # Setup Blending
    gpu.state.blend_set('ALPHA')
    
    # Calculate frames...
    # (Reuse same logic for finding frames)
    frames_to_draw = []
    
    length = settings.ghost_length
    step = settings.ghost_step
    
    # Helper to clean logic
    def get_fade_col(base_col, i, length):
        fade = 1.0 - (i / max(length, 1)) * 0.8
        c = list(base_col)
        c[3] *= fade
        return c

    # PREV
    frames = []
    if settings.ghost_type == 'KEYFRAME':
        frames = find_nearest_keyframes(obj, current_frame, length, 'PREV')
    else:
        for i in range(1, length + 1):
            frames.append(current_frame - (i * step))
            
    for i, f in enumerate(frames):
        if f in GHOST_CACHE:
            frames_to_draw.append((f, get_fade_col(settings.ghost_prev_color, i, length)))

    # NEXT
    frames = []
    if settings.ghost_type == 'KEYFRAME':
        frames = find_nearest_keyframes(obj, current_frame, length, 'NEXT')
    else:
        for i in range(1, length + 1):
            frames.append(current_frame + (i * step))
            
    for i, f in enumerate(frames):
        if f in GHOST_CACHE:
             frames_to_draw.append((f, get_fade_col(settings.ghost_next_color, i, length)))
            
    # DRAW
    for frame_idx, color in frames_to_draw:
        data = GHOST_CACHE.get(frame_idx)
        if not data:
            continue
            
        matrix = data['matrix']
        
        gpu.matrix.push()
        gpu.matrix.multiply_matrix(matrix)
        
        shader.uniform_float("color", color)
        
        if display_type == 'SOLID':
            # Needs viewProjectionMatrix?
            # Custom shaders usually need explicit update of builtin uniforms
            # Or uses `gpu.matrix.get_model_view_matrix()` etc?
            # Actually gpu.types.GPUShader creates a shader that might NOT automatically bind the builtins the way `from_builtin` does.
            # However, recent Blender wrapper handles `viewProjectionMatrix` if named correctly.
            # We need `modelMatrix` too.
            # In new GPU API, we often pass `gpu.matrix.get_model_view_matrix()` to uniform.
            # But let's check standard practice.
            # Simpler: use built-in for simplicity if possible. 
            pass # Shader will use uniforms
            
        if display_type == 'WIRE':
            # Use Wire Batch
            if 'batch_wire' in data:
                data['batch_wire'].draw(shader)
        else:
             # SOLID or SILHOUETTE
             # Both use 'batch' (TRIS)
             # SOLID uses custom shader which reads pos/normal. 'batch' has them.
             # SILHOUETTE uses UNIFORM_COLOR which reads pos. 'batch' has them.
             data['batch'].draw(shader)
             
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
