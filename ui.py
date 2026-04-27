import bpy


# ---------- UIList ----------

class ANIMAH_UL_track_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text="", icon='NLA')
            row.prop(item, "name", text="", emboss=False)
            row.label(text=f"{len(item.items)}", icon='KEYFRAME_HLT')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name)


class ANIMAH_UL_item_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            scene_frame = context.scene.frame_current
            is_current = int(item.frame) == int(scene_frame)
            row = layout.row(align=True)
            row.prop(item, "color", text="")
            sub = row.row(align=True)
            if is_current:
                sub.alert = True
            sub.label(text=f"F{item.frame}", icon='KEYFRAME_HLT' if is_current else 'KEYFRAME')
            sub.label(text=item.shape_key_name, icon='SHAPEKEY_DATA')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=str(item.frame))


# ---------- Helpers ----------

def _resolve_track(obj):
    if not obj or not obj.animah_tracks:
        return None
    idx = obj.animah_active_track_index
    if idx < 0 or idx >= len(obj.animah_tracks):
        return None
    return obj.animah_tracks[idx]


# ---------- Main Panel ----------

class ANIMAH_PT_main(bpy.types.Panel):
    bl_label = "Animah Polisher"
    bl_idname = "ANIMAH_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animah'

    def draw_header(self, context):
        layout = self.layout
        settings = context.scene.animah_settings
        if settings:
            row = layout.row(align=True)
            row.prop(settings, "show_ghosts", text="",
                     icon='GHOST_ENABLED' if settings.show_ghosts else 'GHOST_DISABLED')
            row.prop(settings, "show_hud", text="",
                     icon='HIDE_OFF' if settings.show_hud else 'HIDE_ON')

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        if not obj or obj.type != 'MESH':
            box = layout.box()
            box.label(text="Select a Mesh Object", icon='INFO')
            return

        active_track = _resolve_track(obj)

        # -- STATUS HEADER --
        status = layout.box()
        col = status.column(align=True)
        row = col.row(align=True)
        row.label(text=obj.name, icon='OUTLINER_OB_MESH')
        row.label(text=f"Frame {context.scene.frame_current}", icon='TIME')
        row = col.row(align=True)
        if active_track:
            row.label(text=f"Track: {active_track.name}", icon='NLA')
            row.label(text=f"{len(active_track.items)} polish",
                      icon='KEYFRAME_HLT')
        else:
            row.label(text="No active track", icon='ERROR')

        # -- TRACKS LIST --
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

        # -- SCULPT ACTIONS --
        layout.separator()
        layout.label(text="Sculpt", icon='SCULPTMODE_HLT')

        in_sculpt = obj.mode == 'SCULPT'

        # Big sculpt action — switches role based on current mode
        col = layout.column(align=True)
        if in_sculpt:
            row = col.row(align=True)
            row.scale_y = 1.8
            row.alert = True
            row.operator("animah.toggle_sculpt_mode",
                         text="Exit Sculpt Mode",
                         icon='OBJECT_DATAMODE')
        else:
            row = col.row(align=True)
            row.scale_y = 1.8
            row.operator("animah.add_polish_frame",
                         text="Sculpt This Frame",
                         icon='SCULPTMODE_HLT')

        # Navigation + reset row
        nav = col.row(align=True)
        nav.scale_y = 1.1
        nav.operator("animah.jump_prev_polish", text="", icon='TRIA_LEFT')
        sub = nav.row(align=True)
        sub.alert = True
        sub.operator("animah.reset_polish_frame", text="Reset", icon='X')
        nav.operator("animah.jump_next_polish", text="", icon='TRIA_RIGHT')

        # -- POLISH ITEMS LIST --
        layout.separator()
        if active_track:
            row = layout.row(align=True)
            row.label(text=f"Keys in '{active_track.name}'", icon='KEYINGSET')
            row = layout.row()
            row.template_list(
                "ANIMAH_UL_item_list", "items",
                active_track, "items",
                active_track, "active_item_index",
                rows=6
            )
            col = row.column(align=True)
            col.operator("animah.remove_polish_item", icon='REMOVE', text="")


# ---------- Sub-panels ----------

class ANIMAH_PT_settings(bpy.types.Panel):
    bl_label = "Auto-Key Settings"
    bl_idname = "ANIMAH_PT_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animah'
    bl_parent_id = "ANIMAH_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        settings = context.scene.animah_settings
        if settings:
            self.layout.prop(settings, "auto_key_neighbors", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.animah_settings
        if not settings:
            layout.label(text="Animah settings not available", icon='ERROR')
            return
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        col.enabled = settings.auto_key_neighbors
        col.prop(settings, "neighbor_range")


class ANIMAH_PT_ghosts(bpy.types.Panel):
    bl_label = "Ghosting"
    bl_idname = "ANIMAH_PT_ghosts"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animah'
    bl_parent_id = "ANIMAH_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        settings = context.scene.animah_settings
        if settings:
            self.layout.prop(settings, "show_ghosts", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.animah_settings
        if not settings:
            layout.label(text="Animah settings not available", icon='ERROR')
            return
        layout.use_property_split = True
        layout.use_property_decorate = False

        body = layout.column()
        body.enabled = settings.show_ghosts

        # Bake button — most prominent action in this panel
        row = body.row()
        row.scale_y = 1.3
        row.operator("animah.bake_ghosts", icon='RENDER_STILL', text="Bake Ghosts to GPU")

        col = body.column(align=True)
        col.prop(settings, "ghost_type")
        col.prop(settings, "ghost_display_type")

        col = body.column(align=True)
        if settings.ghost_type == 'STEP':
            col.prop(settings, "ghost_step")
            col.prop(settings, "ghost_length", text="Length")
        else:
            col.prop(settings, "ghost_length", text="Keyframes")

        col = body.column(align=True)
        col.prop(settings, "ghost_prev_color", text="Prev")
        col.prop(settings, "ghost_next_color", text="Next")


class ANIMAH_PT_hud(bpy.types.Panel):
    bl_label = "Timeline HUD"
    bl_idname = "ANIMAH_PT_hud"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animah'
    bl_parent_id = "ANIMAH_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        settings = context.scene.animah_settings
        if settings:
            self.layout.prop(settings, "show_hud", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.animah_settings
        if not settings:
            layout.label(text="Animah settings not available", icon='ERROR')
            return
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        col.enabled = settings.show_hud
        col.prop(settings, "hud_color", text="Default Color")
        col.label(text="Per-item color editable in the keys list", icon='INFO')


classes = (
    ANIMAH_UL_track_list,
    ANIMAH_UL_item_list,
    ANIMAH_PT_main,
    ANIMAH_PT_settings,
    ANIMAH_PT_ghosts,
    ANIMAH_PT_hud,
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
