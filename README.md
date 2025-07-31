# Alcove DoF Visualizer

A Blender addon that provides real-time depth of field visualization in the 3D viewport. Helps cinematographers and photographers visualize focus zones, hyperfocal distances, and DoF limits directly in their scene.

![Experimental](https://img.shields.io/badge/status-experimental-yellow)


## Features

- Real-time DoF gradient overlays
- Focus plane laser indicator
- Near/far DoF limit visualization
- Hyperfocal distance calculations
- Live text info display
- Works with focus objects and manual focus distance


## Installation

### 1. Download the addon

In the [Releases](/alcove-design/alcove-dof-visualizer/releases) section of this repository, download the latest **zip file**.

The releases are named using the format: `vX.Y.Z`.


### 2. Install the addon in blender

1. **Do not extract** the ZIP file - install it as-is.
2. Open **Blender**.
3. Go to **Edit > Preferences > Add-ons**.
4. Click the **Install...** button at the top right.
5. In the file browser, select the ZIP file you downloaded and click **Install Add-on**.
6. After installation, search for the addon in the list and enable it by checking the box next to its name.

N.B. This addon relies on `numpy` python module, which should already be included in blender's python environment, so no extra install is needed.
