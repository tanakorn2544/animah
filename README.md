# Animah Polisher

**Animah Polisher** is a Blender addon designed to bring Maya-style "Animatrix" polishing workflows to Blender. It allows animators to quickly sculpt corrective shapes on a per-frame basis without managing complex shape key drivers manually.

It also features a high-performance **GPU Ghosting (Onion Skinning)** system that draws ghosts directly to the 3D Viewport HUD, keeping your scene clean and your Outliner empty.

## Features

### 1. Shape Key Polishing
- **Sculpt This Frame**: Instantly creates a temporary Shape Key for the current frame and switches to Sculpt Mode.
- **Auto-Keying**: Automatically keys the shape influence to 1.0 on the current frame and 0.0 on neighbor frames (defined by `Neighbor Range`).
- **Smooth Interpolation**: Automatically sets keyframe handles to `Auto Clamped` to prevent overshoots.
- **Reset Sculpt**: Quickly reset the current frame's sculpt to the base mesh state.
- **Track Management**: Organize your polish frames into named "Tracks" (e.g., "Arm_Fixes", "Face_Tweaks").

### 2. Smart Navigation & Timeline Integration
- **Bidirectional Sync**: 
    - **Auto-Highlight**: As you scrub the timeline, the relevant Shape Key in the UI list is automatically highlighted.
    - **Dynamic Tracking**: If you move a keyframe in the Dope Sheet, the list updates automatically to reflect the new position.
    - **Click-to-Jump**: Clicking a Shape Key in the list instantly jumps the timeline to that frame.
- **Timeline Markers**: Visual markers are drawn directly in the Dope Sheet/Timeline to show where your polish frames are located (Orange for active track, Grey for others).

### 3. GPU Ghosting (Onion Skins)
- **Zero Clutter**: Ghosts are drawn using the GPU directly to the viewport. No real objects are created, keeping your Outliner clean.
- **High Performance**: Optimized for speed using GPU batches.
- **Bake-to-Memory**: Ghosts are "baked" into memory, allowing you to scrub the timeline smoothly without re-evaluating meshes every frame.
- **Customizable**:
    - **Step Mode**: Show ghosts every N frames.
    - **Keyframe Mode**: Show ghosts only on actual keyframes (great for pose checks).
    - **Wireframe / Solid**: Toggle between semi-transparent solid, wireframe, or silhouette display.
    - **Colors**: Fully customizable Previous/Next colors with alpha fading.

## Installation

1. Download the `animah` folder.
2. Place it in your Blender Addons directory (or zip it and install via `Edit > Preferences > Add-ons`).
3. Enable **Animah Polisher** in the Add-ons list.
4. The panel will appear in the **3D View > Sidebar (N) > Animah**.

## Usage Guide

### Sculpting a Correction
1. Select a Mesh object with an animation.
2. In the **Animah** panel, click **"Sculpt This Frame"**.
3. Use Blender's sculpting tools to fix the deformation.
4. Scrub away; the fix will blend out over the `Neighbor Range` (default 4 frames).

### Using Ghosting
1. Expand the **Settings** box in the Animah panel.
2. Enable **Show Ghosts**.
3. Click the **"Bake Ghosts to GPU"** button. 
    - *Note: This is required to see ghosts. If you change your animation, click Bake again.*
4. Adjust **Ghost Length** and **Step** to control the trail.
5. Switch **Ghost Type** to **Keyframe** to only see ghosts at keyframe positions.

## Requirements
- Blender 4.0 or higher (requires `gpu` module updates).
