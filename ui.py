import bpy

class ANIMAH_UL_track_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name)

class ANIMAH_UL_item_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # Data is PolishTrack, item is PolishItem
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "color", text="")
            row.label(text=f"F{item.frame}: {item.shape_key_name}", icon='SHAPEKEY_DATA')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=str(item.frame))

class ANIMAH_PT_main(bpy.types.Panel):
    bl_label = "Animah Polisher"
    bl_idname = "ANIMAH_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animah'
    
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        if not obj or obj.type != 'MESH':
            layout.label(text="Select a Mesh Object", icon='INFO')
            return
            
        # -- TRACKS SECTION --
        layout.label(text="Tracks", icon='NLA')
        row = layout.row()
        row.template_list(
            "ANIMAH_UL_track_list", "tracks", 
            obj, "animah_tracks", 
            obj, "animah_active_track_index",
            rows=3
        )
        
        col = row.column(align=True)
        col.operator("animah.add_track", icon='ADD', text="")
        col.operator("animah.remove_track", icon='REMOVE', text="")
        
        layout.separator()
        
        # -- ACTIONS SECTION --
        # Use a box for the main actions to group them
        box = layout.box()
        box.label(text="Sculpting", icon='SCULPTMODE_HLT')
        
        # Big Sculpt Button
        row = box.row()
        row.scale_y = 2.0
        row.operator("animah.add_polish_frame", text="Sculpt This Frame", icon='SCULPTMODE_HLT')
        
        # Reset Button (Danger zone style)
        row = box.row()
        row.scale_y = 1.2
        row.alert = True  # Make it red/alert color
        row.operator("animah.reset_polish_frame", text="Reset Current Sculpt", icon='X')

        layout.separator()

        # -- SETTINGS SECTION --
        settings = context.scene.animah_settings
        box = layout.box()
        box.label(text="Settings", icon='PREFERENCES')
        box.prop(settings, "auto_key_neighbors")
        if settings.auto_key_neighbors:
            row = box.row()
            row.prop(settings, "neighbor_range")
        box.prop(settings, "show_ghosts", toggle=True, icon='GHOST_ENABLED' if settings.show_ghosts else 'GHOST_DISABLED')
        if settings.show_ghosts:
            row = box.row()
            row.scale_y = 1.2
            row.operator("animah.bake_ghosts", icon='RENDER_STILL', text="Bake Ghosts to GPU")
            
            row = box.row()
            row.prop(settings, "ghost_type")
            row.prop(settings, "ghost_display_type", text="")
            
            row = box.row()
            if settings.ghost_type == 'STEP':
                row.prop(settings, "ghost_step")
            row.prop(settings, "ghost_length", text="Length" if settings.ghost_type == 'STEP' else "Keyframes")
            
            row = box.row()
            row.prop(settings, "ghost_prev_color", text="")
            row.prop(settings, "ghost_next_color", text="")
            
        box.prop(settings, "show_hud", toggle=True, icon='HIDE_OFF' if settings.show_hud else 'HIDE_ON')
            
        layout.separator()

        # -- ITEMS LIST SECTION --
        # Properly display items in the active track
        if obj.animah_tracks:
            active_track = obj.animah_tracks[obj.animah_active_track_index]
            
            layout.label(text=f"Keys in '{active_track.name}'", icon='KEYINGSET')
            row = layout.row()
            row.template_list(
                "ANIMAH_UL_item_list", "items",
                active_track, "items",
                active_track, "active_item_index",
                rows=5
            )

classes = (
    ANIMAH_UL_track_list,
    ANIMAH_UL_item_list,
    ANIMAH_PT_main,
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
