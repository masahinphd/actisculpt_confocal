"""
ActiSculpt Confocal Viewer

Author: Mehmet Akif Sahin (akif.sahin@tum.de)
"""

import streamlit as st
import tifffile as tiff
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap
import imageio
from PIL import Image
from skimage import measure, filters
import os
import tempfile

# Set page configuration
st.set_page_config(
    page_title="ActiSculpt Confocal Viewer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* Ensure all text is readable */
    .stMarkdown, .stText, h1, h2, h3, h4, h5, h6, p, label, .stDataFrame {
        color: #FAFAFA !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #262730;
    }
    
    /* Inputs contrast */
    .stTextInput > div > div > input, .stNumberInput > div > div > input {
        color: #FAFAFA;
        background-color: #1E1E1E;
    }
    
    /* Slider highlight */
    .stSlider > div > div > div > div {
        background-color: #FF4B4B;
    }
    
    /* Metrics container */
    div.metric-container {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)

# --- Functions ---

@st.cache_data
def load_tiff_stack(input_path):
    try:
        stack = tiff.imread(input_path)
        return stack
    except Exception as e:
        st.error(f"Error loading TIFF: {e}")
        return None

def process_slice_2d(img, threshold_rel=0.0, keep_largest=False, sigma=0.0, suppress_mode="None"):
    """
    Applies Gaussian blur, thresholding, filtering, and optional artifact suppression.
    """
    # 1. Apply Gaussian Blur first
    if sigma > 0:
        # gaussian returns float 0-1 if preserve_range=False. 
        # log1p images are floats. 
        img = filters.gaussian(img, sigma=sigma, preserve_range=True).astype(img.dtype)

    # 2. Suppress Artifacts
    if suppress_mode in ["Horizontal", "Vertical", "Both"]:
        
        def remove_streaks(image, axis):
            # Calculate mean along the given axis (if axis=1, we get means of rows)
            # To fix rows (horizontal lines), we look at axis=1 returns (rows,)
            # To fix cols (vertical lines), we look at axis=0 returns (cols,)
            means = np.mean(image, axis=axis)
            med = np.median(means)
            mad = np.median(np.abs(means - med))
            
            if mad > 1e-6:
                z_scores = 0.6745 * (means - med) / mad
                # > 3.5 deviations
                artifact_idx = np.where(z_scores > 3.5)[0]
                
                # Replace with neighbors
                limit = image.shape[0] if axis == 1 else image.shape[1]
                
                for idx in artifact_idx:
                    # Logic depends on axis. if axis=1 (rows), we replace image[idx, :]
                    if axis == 1:
                        if idx > 0 and (idx-1 not in artifact_idx):
                            image[idx, :] = image[idx-1, :]
                        elif idx < limit - 1 and (idx+1 not in artifact_idx):
                            image[idx, :] = image[idx+1, :]
                        else:
                            image[idx, :] = med
                    else: # axis=0 (cols)
                        if idx > 0 and (idx-1 not in artifact_idx):
                            image[:, idx] = image[:, idx-1]
                        elif idx < limit - 1 and (idx+1 not in artifact_idx):
                            image[:, idx] = image[:, idx+1]
                        else:
                            image[:, idx] = med
            return image

        if suppress_mode == "Horizontal" or suppress_mode == "Both":
            img = remove_streaks(img, 1) # axis 1 -> Row means -> Fix Rows
        
        if suppress_mode == "Vertical" or suppress_mode == "Both":
            img = remove_streaks(img, 0) # axis 0 -> Col means -> Fix Cols

    if threshold_rel <= 0.0 and not keep_largest:
        return img
        
    # Thresholding
    # Calculate mask
    max_val = np.max(img)
    if max_val == 0: return img
    
    thresh_val = threshold_rel * max_val
    mask = img > thresh_val
    
    # Filter connected components
    if keep_largest and np.any(mask):
        labels = measure.label(mask)
        if labels.max() > 0:
            # unique labels and their counts (ignore 0 background)
            unique, counts = np.unique(labels[labels > 0], return_counts=True)
            if len(unique) > 0:
                largest_label = unique[np.argmax(counts)]
                mask = (labels == largest_label)
            else:
                mask[:] = False
    
    # Apply mask to original image (keep intensities)
    # We return the original intensities where mask is True, 0 otherwise
    return np.where(mask, img, 0).astype(img.dtype)

def find_best_rect_on_image(image, h_mm, w_mm, pix_h, pix_w):
    """
    Finds the best cropping rectangle on any 2D image array given physical dimensions.
    Returns (row_start, col_start, h_px, w_px).
    """
    h_px = int(h_mm / pix_h)
    w_px = int(w_mm / pix_w)
    
    rows, cols = image.shape
    
    # Boundary check
    if h_px >= rows: h_px = rows - 1
    if w_px >= cols: w_px = cols - 1
    if h_px < 1 or w_px < 1: return 0, 0, 1, 1

    # Sliding window search (step 2 for performance)
    # Note: image is already processed (e.g. log scale) so we just sum values
    
    # Optimization: Use Uniform Filter if available or simple loop
    # For Slice 512x512, loop is okay.
    
    best_val = -np.inf
    best_loc = (0, 0)
    
    # Limit search area for speed if image is huge, but usually fine
    step = 2 
    
    # Naive loop - robust to rotation since we operate on the array directly
    # We loop through top-left corners
    for r in range(0, rows - h_px + 1, step):
        for c in range(0, cols - w_px + 1, step):
            # Calculate mean of window
            val = np.mean(image[r:r+h_px, c:c+w_px])
            if val > best_val:
                best_val = val
                best_loc = (r, c)
                
    return best_loc[0], best_loc[1], h_px, w_px

# --- Main App ---

st.sidebar.title("⚙️ Controls")

default_dir = os.getcwd()
current_dir = st.sidebar.text_input("Image Directory", value=default_dir)

tif_files = []
if os.path.isdir(current_dir):
    try:
        tif_files = [f for f in os.listdir(current_dir) if f.endswith('.tif') or f.endswith('.tiff')]
        tif_files.sort()
    except Exception as e:
        st.error(f"Error reading directory: {e}")
else:
    st.error(f"Directory not found: {current_dir}")

if not tif_files:
    st.error("No .tif files found in the current directory.")
else:
    selected_file = st.sidebar.selectbox("Select Confocal Image", tif_files)
    file_path = os.path.join(current_dir, selected_file)
    
    with st.spinner(f"Loading {selected_file}..."):
        stack = load_tiff_stack(file_path)

    if stack is not None and stack.ndim == 3:
        z_size, y_size, x_size = stack.shape
        
        # Sidebar Parameters
        st.sidebar.markdown("### 📏 Image Parameters")
        col1, col2 = st.sidebar.columns(2)
        pixel_size_xy = col1.number_input("Pixel Size XY (mm)", value=0.0122, format="%.4f")
        z_step_size = col2.number_input("Z Step Size (mm)", value=0.025, format="%.4f")
        
        # Moved from analysis tab to global settings
        box_size = st.sidebar.number_input("Analysis Box Size (mm)", min_value=0.1, value=1.0)
        show_crop = st.sidebar.checkbox("Show Best Region (Box)", value=True)
        
        st.sidebar.markdown("### 🎨 Display Options")
        apply_log = st.sidebar.checkbox("Apply Log Scale", value=True)
        
        # Define Custom Black-Red Colormap
        colors = [(0, 0, 0), (1, 0, 0)] # Black -> Red
        cmap_name = 'BlackRed'
        cm = LinearSegmentedColormap.from_list(cmap_name, colors, N=256)
        # We can just pass the object to imshow, but for streamlit selectbox we need string handling or a dict
        
        colormap_name = st.sidebar.selectbox("Colormap", ["inferno", "magma", "plasma", "viridis", "gray", "hot", "BlackRed"], index=0)
        
        # Resolve colormap
        if colormap_name == "BlackRed":
            colormap = cm
        else:
            colormap = colormap_name
        
        st.sidebar.markdown("### 📐 Orientation (XZ View)")
        col_yz1, col_yz2 = st.sidebar.columns(2)
        rotate_yz = col_yz1.selectbox("Rotate XZ", [0, 90, 180, 270], index=3, format_func=lambda x: f"{x}°")
        mirror_yz = col_yz2.checkbox("Mirror XZ", value=False)
        
        st.sidebar.markdown("### 📐 Orientation (XY View)")
        col_xy1, col_xy2 = st.sidebar.columns(2)
        rotate_xy = col_xy1.selectbox("Rotate XY", [0, 90, 180, 270], index=0, format_func=lambda x: f"{x}°")
        mirror_xy = col_xy2.checkbox("Mirror XY", value=False)
        
        with st.sidebar.expander("🛠️ Preprocessing & Filtering", expanded=False):
            st.markdown("Remove noise or background.")
            sigma_blur = st.slider("Gaussian Blur (Sigma)", 0.0, 5.0, 0.0, 0.5)
            threshold_rel = st.slider("Intensity Threshold (%)", 0.0, 100.0, 0.0, 1.0) / 100.0
            keep_largest = st.checkbox("Keep Only Main Bulk (Largest Object)", value=False)
            suppress_mode = st.selectbox("Suppress Linear Artifacts", ["None", "Horizontal", "Vertical", "Both"], index=0, help="Remove high-intensity streaks in specified direction.")

        # Rotation Keys
        rot_k_yz = {0: 0, 90: 1, 180: 2, 270: 3}[rotate_yz]
        rot_k_xy = {0: 0, 90: 1, 180: 2, 270: 3}[rotate_xy]

        # Calculate Pixel Dimensions for the transformed YZ image
        if rot_k_yz % 2 != 0:
            pix_height_disp_yz = pixel_size_xy
            pix_width_disp_yz = z_step_size
        else:
            pix_height_disp_yz = z_step_size
            pix_width_disp_yz = pixel_size_xy

        # Calculate Pixel Dimensions for the transformed XY image
        # Standard XY: Rows=Y, Cols=X
        if rot_k_xy % 2 != 0:
            pix_height_disp_xy = pixel_size_xy # Now X is height
            pix_width_disp_xy = pixel_size_xy  # Now Y is width
        else:
            pix_height_disp_xy = pixel_size_xy
            pix_width_disp_xy = pixel_size_xy

        # Tabs - Merged View
        tab1, tab3, tab4 = st.tabs(["🖼️ Interactive View (XY & XZ)", "📊 Intensity Analysis", "🎬 Video Generation"])
        
        # --- TAB 1: Merged Interactive View ---
        with tab1:
            st.header("Interactive Visualization")
            
            # Top Controls for Slices
            # Initialize Session State if not valid
            if 'z_pos' not in st.session_state or st.session_state.z_pos >= z_size:
                st.session_state.z_pos = z_size // 2
            if 'x_pos' not in st.session_state or st.session_state.x_pos >= x_size:
                st.session_state.x_pos = x_size // 2

            # Callbacks
            def increment_z(): st.session_state.z_pos = min(st.session_state.z_pos + 1, z_size - 1)
            def decrement_z(): st.session_state.z_pos = max(st.session_state.z_pos - 1, 0)
            def increment_x(): st.session_state.x_pos = min(st.session_state.x_pos + 10, x_size - 1)
            def decrement_x(): st.session_state.x_pos = max(st.session_state.x_pos - 10, 0)
            
            # Controls - Full Width, Stacked
            c1_1, c1_2, c1_3 = st.columns([10, 1, 1])
            c1_1.slider("Z Slice (Top View)", 0, z_size - 1, key='z_pos')
            c1_2.button("➖", key='z_min', on_click=decrement_z)
            c1_3.button("➕", key='z_plus', on_click=increment_z)

            c2_1, c2_2, c2_3 = st.columns([10, 1, 1])
            c2_1.slider("X Slice (Cross-Section)", 0, x_size - 1, key='x_pos')
            c2_2.button("➖", key='x_min', on_click=decrement_x)
            c2_3.button("➕", key='x_plus', on_click=increment_x)
            
            # Read Values
            z_pos = st.session_state.z_pos
            x_pos = st.session_state.x_pos

            # Layout: Top to Bottom
            
            # --- XY View (Top) ---
            st.subheader("XY Top View")
            xy_slice = stack[z_pos, :, :]
            if apply_log: xy_slice = np.log1p(xy_slice)
            
            # Process
            xy_slice = process_slice_2d(xy_slice, threshold_rel, keep_largest, sigma_blur, suppress_mode)
            
            # Transform XY
            if rot_k_xy > 0:
                xy_slice = np.rot90(xy_slice, k=rot_k_xy)
            if mirror_xy:
                xy_slice = np.fliplr(xy_slice)
            
            # Calculate Line Position for X-Slice Indicator
            # We need to map 'x_pos' (original column index) to the transformed image coordinates
            line_type = 'v'
            line_pos = x_pos
            
            # Rotation Logic (Standard Cartesian Rotation CCW)
            # Original: (Rows=Y, Cols=X)
            if rot_k_xy == 1: # 90 deg
                # (r, c) -> (H-1-c, r) => Cols become Rows (reversed)
                line_type = 'h' 
                line_pos = y_size - 1 - x_pos
            elif rot_k_xy == 2: # 180 deg
                # (r, c) -> (H-1-r, W-1-c) => Cols reversed
                line_type = 'v'
                line_pos = x_size - 1 - x_pos
            elif rot_k_xy == 3: # 270 deg
                # (r, c) -> (c, W-1-r) => Cols become Rows
                line_type = 'h'
                line_pos = x_pos
            
            # Mirror Logic (Left-Right Flip of the *Result*)
            if mirror_xy:
                if line_type == 'v':
                    # Width of the image *after* rotation
                    curr_width = xy_slice.shape[1]
                    line_pos = curr_width - 1 - line_pos
                    
            ar_xy = pix_height_disp_xy / pix_width_disp_xy
            fig_xy, ax_xy = plt.subplots(figsize=(6, 6))
            ax_xy.imshow(xy_slice, cmap=colormap, aspect=ar_xy)
            
            # Draw Indicator Line
            if line_type == 'v':
                ax_xy.axvline(x=line_pos, color='cyan', linestyle='--', linewidth=1.5, alpha=0.8)
            else:
                ax_xy.axhline(y=line_pos, color='cyan', linestyle='--', linewidth=1.5, alpha=0.8)
                
            ax_xy.axis('off')
            st.pyplot(fig_xy, use_container_width=True)


            # --- XZ View (Bottom/Cross Section) ---
            st.markdown("---") # Separator
            st.subheader("XZ Cross-Section")
            
            # Prepare Data
            yz_slice = stack[:, :, x_pos]
            if apply_log:
                yz_slice = np.log1p(yz_slice)
            
            # Process (Threshold/Clean)
            yz_slice = process_slice_2d(yz_slice, threshold_rel, keep_largest, sigma_blur, suppress_mode)
            
            # Transform
            if rot_k_yz > 0:
                yz_slice = np.rot90(yz_slice, k=rot_k_yz)
            if mirror_yz:
                yz_slice = np.fliplr(yz_slice)
                
            # Crop Detection & Plotting
            # We always calculate the best rect because the user likely wants to see that specific region
            # logic changed to ONLY show the cropped region
            r, c, h, w = find_best_rect_on_image(yz_slice, box_size, box_size, pix_height_disp_yz, pix_width_disp_yz)
            
            # If show_crop is True, we crop the view. 
            # If False, we could show full, but user asked to "only plot the best region".
            # We'll treat the checkbox as a toggle for "Zoom to Best Region" vs "Show Full with Box" maybe?
            # Or simplified: The user request "only plot the best region" implies this is the desired view.
            # Let's crop it.
            
            yz_cropped = yz_slice[r:r+h, c:c+w]
            
            fig, ax = plt.subplots(figsize=(4.8, 4.8))
            # Aspect ratio is now based on physical dimensions of the crop box (which is square box_size x box_size)
            # So aspect is 1:1 if we look at physical mm.
            # But pixels might be non-square.
            # h_px = box/pix_h, w_px = box/pix_w
            # aspect = pix_h/pix_w
            
            ar_yz = pix_height_disp_yz / pix_width_disp_yz 
            
            ax.imshow(yz_cropped, cmap=colormap, aspect=ar_yz)
            ax.axis('off')

            # Crop Box Overlay is no longer needed if we are zooming into it.
            
            st.pyplot(fig, use_container_width=True)

        # --- TAB 3: Analysis ---
        with tab3:
            st.header("Intensity Profile Analysis")
            
            # --- Analysis Controls ---
            col_an1, col_an3, col_an4 = st.columns(3)
            step_val = col_an1.number_input("Step (Slice)", min_value=1, value=10)
            # Box Size is now global (sidebar)
            grid_rows = col_an3.number_input("Grid Rows", min_value=1, value=1)
            grid_cols = col_an4.number_input("Grid Cols", min_value=1, value=1)
            
            # --- Preview Section ---
            st.markdown("#### 👁️ Region Preview")
            
            # Use XZ middle slice or current slider X
            # Let's use the current X position from Tab 1 (x_pos) if available in memory, but that is in Tab 1 scope.
            # We better just use the middle slice or add a small slider here.
            
            cols_prev = st.columns([1, 2])
            with cols_prev[0]:
                preview_x = st.slider("Preview Slice (X)", 0, x_size - 1, x_size // 2, key='prev_x')
            
            # Compute Preview
            sl_prev = stack[:, :, preview_x]
            if apply_log: sl_prev = np.log1p(sl_prev)
            
            sl_prev = process_slice_2d(sl_prev, threshold_rel, keep_largest, sigma_blur, suppress_mode)
            
            if rot_k_yz > 0: sl_prev = np.rot90(sl_prev, k=rot_k_yz)
            if mirror_yz: sl_prev = np.fliplr(sl_prev)
            
            # Find Rect
            r, c, h, w = find_best_rect_on_image(sl_prev, box_size, box_size, pix_height_disp_yz, pix_width_disp_yz)
            
            fig_prev, ax_prev = plt.subplots(figsize=(6, 6))
            ar_yz = pix_height_disp_yz / pix_width_disp_yz 
            ax_prev.imshow(sl_prev, cmap=colormap, aspect=ar_yz)
            
            # Draw Main Rect
            rect_main = patches.Rectangle((c, r), w, h, linewidth=2, edgecolor='cyan', facecolor='none')
            ax_prev.add_patch(rect_main)
            
            # Draw Grid
            sub_h = h / grid_rows
            sub_w = w / grid_cols
            
            # Draw internal lines
            for i in range(1, grid_rows):
                ax_prev.axhline(y=r + i * sub_h, xmin=(c)/sl_prev.shape[1], xmax=(c+w)/sl_prev.shape[1], color='cyan', linestyle='--', linewidth=0.5)
                
            for j in range(1, grid_cols):
                ax_prev.axvline(x=c + j * sub_w, ymin=1 - (r+h)/sl_prev.shape[0], ymax=1 - r/sl_prev.shape[0], color='cyan', linestyle='--', linewidth=0.5)
            
            # Label Regions (Center of each sub-box)
            for row_i in range(grid_rows):
                for col_j in range(grid_cols):
                    cy = r + (row_i + 0.5) * sub_h
                    cx = c + (col_j + 0.5) * sub_w
                    ax_prev.text(cx, cy, f"R{row_i+1}C{col_j+1}", color='white', fontsize=8, ha='center', va='center', bbox=dict(facecolor='black', alpha=0.5, edgecolor='none'))

            ax_prev.set_title(f"Preview X={preview_x} (Processed)")
            ax_prev.axis('off')
            
            with cols_prev[1]:
                st.pyplot(fig_prev, use_container_width=False)

            if st.button("Run Profile Analysis"):
                progress = st.progress(0)
                
                # Setup
                x_vals = []
                data_store = {f"R{r+1}C{c+1}": [] for r in range(grid_rows) for c in range(grid_cols)}
                
                slices = range(0, x_size, step_val)
                total_steps = len(slices)
                
                for i, x in enumerate(slices):
                    sl = stack[:, :, x]
                    if apply_log: sl = np.log1p(sl)
                    
                    # 1. Process & Transform (Consistency with XZ View)
                    # We apply the same processing and rotation as the user sees in Tab 1
                    sl = process_slice_2d(sl, threshold_rel, keep_largest, sigma_blur, suppress_mode)
                    
                    if rot_k_yz > 0:
                        sl = np.rot90(sl, k=rot_k_yz)
                    if mirror_yz:
                        sl = np.fliplr(sl)
                    
                    # 2. Find Best Rect on transformed image
                    # Use displayed pixel dimensions
                    r, c, h, w = find_best_rect_on_image(sl, box_size, box_size, pix_height_disp_yz, pix_width_disp_yz)
                    
                    # 3. Grid Subdivision
                    sub_h = h / grid_rows
                    sub_w = w / grid_cols
                    
                    for row in range(grid_rows):
                        for col in range(grid_cols):
                            r_s = int(r + row * sub_h)
                            r_e = int(r + (row + 1) * sub_h)
                            c_s = int(c + col * sub_w)
                            c_e = int(c + (col + 1) * sub_w)
                            
                            if r_e <= r_s: r_e = r_s + 1
                            if c_e <= c_s: c_e = c_s + 1
                            
                            sub_region = sl[r_s:r_e, c_s:c_e]
                            val = np.mean(sub_region) if sub_region.size > 0 else 0
                            data_store[f"R{row+1}C{col+1}"].append(val)
                            
                    x_vals.append(x * pixel_size_xy)
                    progress.progress((i + 1) / total_steps)
                
                st.session_state['analysis_res'] = {
                    'x': x_vals,
                    'data': data_store,
                    'box_size': box_size
                }
            
            # Plotting
            if 'analysis_res' in st.session_state:
                res = st.session_state['analysis_res']
                all_keys = list(res['data'].keys())
                
                st.markdown("### 📈 Results")
                selected_keys = st.multiselect("Select Regions to Plot", all_keys, default=all_keys)
                
                if selected_keys:
                    fig_res, ax_res = plt.subplots(figsize=(10, 5))
                    for k in selected_keys:
                        if k in res['data']:
                            ax_res.plot(res['x'], res['data'][k], label=k, marker='o', markersize=3, alpha=0.7)
                    
                    ax_res.set_xlabel("X (mm)")
                    ax_res.set_ylabel(f"Avg Intensity (Box: {res['box_size']}mm)")
                    ax_res.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
                    ax_res.grid(True, linestyle='--', alpha=0.3)
                    st.pyplot(fig_res)
                else:
                    st.warning("Please select at least one region to plot.")

        # --- TAB 4: Video Generator ---
        with tab4:
            st.header("🎬 Video Export")
            st.markdown("Generate a video with **XY (Top)** and **XZ (Bottom)** views.")
            st.info(f"Top view uses XY slice at **Z={z_pos}** (set in 'XY Z-Stack' tab).")

            
            col_v1, col_v2 = st.columns(2)
            video_start = col_v1.number_input("Start X Slice", 0, x_size-1, 0)
            video_end = col_v2.number_input("End X Slice", 0, x_size-1, x_size-1)
            video_step = st.slider("Step (Stride)", 1, 20, 5)
            frame_rate = st.slider("Frame Rate (fps)", 1, 60, 10)
            
            col_v3, col_v4 = st.columns(2)
            sweep_reverse = col_v3.checkbox("Sweep Reverse (Right to Left)", value=False)
            crop_video = col_v4.checkbox("Crop XZ to Best Region", value=False)
            
            if crop_video:
                vid_sqedge = st.number_input("Video Crop Size (mm)", value=1.0)
            
            if st.button("Generate Video"):
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                progress_vid = st.progress(0)
                
                # Prepare Reference Image (XY Slice from selected Z)
                # This depends on z_pos from Tab 2
                xy_ref = stack[z_pos, :, :]
                if apply_log:
                    xy_ref = np.log1p(xy_ref)
                
                # Process
                xy_ref = process_slice_2d(xy_ref, threshold_rel, keep_largest, sigma_blur, suppress_mode)

                # Apply XY Transformations
                if rot_k_xy > 0:
                    xy_ref = np.rot90(xy_ref, k=rot_k_xy)
                if mirror_xy:
                    xy_ref = np.fliplr(xy_ref)
                    
                # Setup writer
                frames = []
                x_range = list(range(video_start, video_end + 1, video_step))
                if sweep_reverse:
                    x_range = x_range[::-1]
                    
                total_frames = len(x_range)

                # Aspect ratios
                ar_top = pix_height_disp_xy / pix_width_disp_xy
                
                # If cropping, the aspect ratio of the bottom plot changes
                if crop_video:
                    # Crop is sqedge x sqedge (mm). So aspect is 1:1 visually.
                    # but in pixels: h_px = sqedge/pix_h, w_px = sqedge/pix_w
                    # We display with imshow. We want it square. 
                    # If we let imshow auto-scale, we need aspect=pix_h/pix_w.
                    ar_bot = pix_height_disp_yz / pix_width_disp_yz
                else:
                    ar_bot = pix_height_disp_yz / pix_width_disp_yz
                
                # For the moving line on Top View (XY):
                # We need to know where "X" is maped after rotation/mirroring.
                # Original Image: (Y, X) -> Rows=Y, Cols=X.
                # X coordinate is column index.
                # Line should be vertical at `x_curr`. (x=constant)
                
                # If Rotated:
                # 0 deg: (Y, X). X is Cols. Vertical Line at col=x.
                # 90 deg (CCW): (X, Y_inv). X is Rows. Horizontal Line at row=x.
                # 180 deg: (Y_inv, X_inv). X is Cols (reversed). Vertical Line at col=(W-1-x).
                # 270 deg: (X_inv, Y). X is Rows (reversed). Horizontal Line at row=(H-1-x).
                
                # If Mirrored (Left-Right flip AFTER rotation):
                # Flip aligns with logic for last dim (Cols).
                
                # Let's map x_curr to plot coordinates (col_marker, row_marker, or None)
                # Original dims of slice: (H_orig, W_orig) = (y_size, x_size)
                
                for idx, x_curr in enumerate(x_range):
                    # --- Determine Line Position ---
                    # Logic needs to track the coordinate transform of (y, x_curr)
                    # Coordinates in original: col = x_curr.
                    
                    # 1. Rotation logic on indices
                    # 90 deg:  (r, c) -> (H-1-c, r).  New dims (W, H).
                    # 180 deg: (r, c) -> (H-1-r, W-1-c). New dims (H, W).
                    # 270 deg: (r, c) -> (c, W-1-r). New dims (W, H).
                    
                    # Target pixel is (any_y, x_curr). "c" is x_curr.
                    
                    if rot_k_xy == 0:
                        # (r, x) -> (r, x).
                        # Line is vertical at col = x_curr
                        line_type = 'v'
                        line_pos = x_curr
                        
                    elif rot_k_xy == 1: # 90 deg
                        # (r, x) -> (y_size-1-x, r). 
                        # Rows are derived from x. 
                        # Line is horizontal at row = y_size - 1 - x_curr
                        line_type = 'h'
                        line_pos = y_size - 1 - x_curr
                        
                    elif rot_k_xy == 2: # 180 deg
                        # (r, x) -> (..., x_size-1-x).
                        # Line is vertical at col = x_size - 1 - x_curr
                        line_type = 'v'
                        line_pos = x_size - 1 - x_curr
                        
                    elif rot_k_xy == 3: # 270 deg
                        # (r, x) -> (x, ...).
                        # Line is horizontal at row = x_curr
                        line_type = 'h'
                        line_pos = x_curr
                        
                    # Mirroring (fliplr) - affects Columns (last dim)
                    # If we flip LR, column c becomes W_current - 1 - c
                    # If line_type is 'h' (horizontal line), it spans all cols, so Mirror doesn't move the line's row index.
                    # If line_type is 'v' (vertical line at col C), Mirror moves it to W_curr - 1 - C.
                    
                    if mirror_xy:
                        if line_type == 'v':
                            # Get width of *transformed* image
                            # If rot 0/180: width is x_size
                            # If rot 90/270: width is y_size
                            curr_width = xy_ref.shape[1]
                            line_pos = curr_width - 1 - line_pos
                        # Horizontal line position stays same (row index unaffected by LR flip)

                    
                    # --- Create Frame ---
                    # Manually adjust spacing to bring them closer
                    fig_vid, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(5, 5), 
                                                             gridspec_kw={'height_ratios': [1, 1]})
                    
                    # Reduce hspace to make them close
                    fig_vid.subplots_adjust(hspace=0.05, top=0.95, bottom=0.05, left=0.05, right=0.95)
                    
                    # Style the figure background
                    fig_vid.patch.set_facecolor('#0E1117')
                    
                    # Top: XY
                    ax_top.imshow(xy_ref, cmap=colormap, aspect=ar_top)
                    if line_type == 'v':
                        ax_top.axvline(x=line_pos, color='white', linewidth=2, linestyle='-')
                    else:
                        ax_top.axhline(y=line_pos, color='white', linewidth=2, linestyle='-')
                        
                    ax_top.set_title(f"Top View (XY)", color='white', fontsize=16)
                    ax_top.axis('off')
                    
                    # Bottom: YZ
                    yz = stack[:, :, x_curr]
                    if apply_log: yz = np.log1p(yz)
                    
                    # Process
                    yz = process_slice_2d(yz, threshold_rel, keep_largest, sigma_blur, suppress_mode)

                    if rot_k_yz > 0: yz = np.rot90(yz, k=rot_k_yz)
                    if mirror_yz: yz = np.fliplr(yz)
                    
                    # Crop Logic
                    if crop_video:
                        # Find coords on the *processed* image 
                        # (since yz is already processed/rotated, we find rect on what we see)
                        # We use the display pixel sizes
                        r, c, h, w = find_best_rect_on_image(yz, vid_sqedge, vid_sqedge, pix_height_disp_yz, pix_width_disp_yz)
                        yz = yz[r:r+h, c:c+w]
                    
                    ax_bot.imshow(yz, cmap=colormap, aspect=ar_bot)
                    ax_bot.set_title(f"Cross Section (XZ)", color='white', fontsize=16)
                    ax_bot.axis('off')
                    
                    # Convert to image array
                    fig_vid.canvas.draw()
                    
                    buf = fig_vid.canvas.buffer_rgba()
                    image_array = np.asarray(buf)
                    
                    # Drop Alpha
                    if image_array.shape[2] == 4:
                         image_array = image_array[:, :, :3]
                         
                    frames.append(image_array)
                    
                    plt.close(fig_vid)
                    progress_vid.progress((idx + 1) / total_frames)
                
                # Save Video
                imageio.mimwrite(tfile.name, frames, fps=frame_rate, codec='libx264')
                
                st.success("Video Generated!")
                st.video(tfile.name)
                
                # Download Button
                vid_name = f"{os.path.splitext(selected_file)[0]}_video.mp4"
                with open(tfile.name, "rb") as f:
                    st.download_button("Download Video", f, file_name=vid_name)

