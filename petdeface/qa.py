import argparse
import os
import tempfile
import shutil
import sys
from glob import glob
import nilearn
from nilearn import plotting
import webbrowser
import nibabel as nib
import numpy as np
from nilearn import image
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import imageio
import multiprocessing as mp
from functools import partial
import seaborn as sns
from PIL import Image, ImageDraw
from nipype import Workflow, Node
from tempfile import TemporaryDirectory
from pathlib import Path

# Handle imports for both script and module execution (including debugger)
is_script = (
    __name__ == "__main__"
    or len(sys.argv) > 0
    and sys.argv[0].endswith("qa.py")
    or "debugpy" in sys.modules
)

if is_script:
    # Running as script - add current directory to path for local imports
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))

# Import nireports - this should work in both script and module mode
from nireports.interfaces.reporting.base import SimpleBeforeAfterRPT


def preprocess_single_subject(s, output_dir):
    """Preprocess a single subject's images (for parallel processing)."""
    temp_dir = os.path.join(output_dir, "temp_3d_images")

    # Debug: Print what files we're processing
    print(f"Preprocessing subject {s['id']}:")
    print(f"  Original: {s['orig_path']}")
    print(f"  Defaced: {s['defaced_path']}")

    # Extract BIDS suffix from original path to preserve meaningful naming
    orig_basename = os.path.basename(s["orig_path"])
    defaced_basename = os.path.basename(s["defaced_path"])

    # Extract the meaningful part (e.g., "sub-01_ses-baseline_T1w" or "sub-01_ses-baseline_pet")
    def extract_bids_name(basename):
        # Remove .nii.gz extension
        name = basename.replace(".nii.gz", "").replace(".nii", "")
        return name

    orig_bids_name = extract_bids_name(orig_basename)
    defaced_bids_name = extract_bids_name(defaced_basename)

    # Preprocess original image
    orig_result = load_and_preprocess_image(s["orig_path"])
    if isinstance(orig_result, nib.Nifti1Image):
        # Need to save the averaged image with meaningful name
        orig_3d_path = os.path.join(temp_dir, f"orig_{orig_bids_name}.nii.gz")
        nib.save(orig_result, orig_3d_path)
        orig_img = orig_result
    else:
        # Already 3D, use original path and load image
        orig_3d_path = orig_result
        orig_img = nib.load(orig_result)

    # Preprocess defaced image
    defaced_result = load_and_preprocess_image(s["defaced_path"])
    if isinstance(defaced_result, nib.Nifti1Image):
        # Need to save the averaged image with meaningful name
        defaced_3d_path = os.path.join(temp_dir, f"defaced_{defaced_bids_name}.nii.gz")
        nib.save(defaced_result, defaced_3d_path)
        defaced_img = defaced_result
    else:
        # Already 3D, use original path and load image
        defaced_3d_path = defaced_result
        defaced_img = nib.load(defaced_result)

    # Create new subject dict with preprocessed paths (update paths to 3D versions)
    preprocessed_subject = {
        "id": s["id"],
        "orig_path": orig_3d_path,  # Update to 3D path
        "defaced_path": defaced_3d_path,  # Update to 3D path
        "orig_img": orig_img,  # Keep loaded image for direct use
        "defaced_img": defaced_img,  # Keep loaded image for direct use
    }

    print(f"  Preprocessed {s['id']}")
    return preprocessed_subject


def preprocess_images(subjects: dict, output_dir, n_jobs=None):
    """Preprocess all images once: load and convert 4D to 3D if needed."""
    print("Preprocessing images (4D→3D conversion)...")

    # Create temp directory
    temp_dir = os.path.join(output_dir, "temp_3d_images")
    os.makedirs(temp_dir, exist_ok=True)

    # Set number of jobs for parallel processing
    if n_jobs is None:
        n_jobs = mp.cpu_count()
    print(f"Using {n_jobs} parallel processes for preprocessing")

    # Process subjects in parallel
    with mp.Pool(processes=n_jobs) as pool:
        # Create a partial function with the output_dir fixed
        preprocess_func = partial(preprocess_single_subject, output_dir=output_dir)

        # Process all subjects in parallel
        preprocessed_subjects = pool.map(preprocess_func, subjects)

    print(f"Preprocessed {len(preprocessed_subjects)} subjects")
    return preprocessed_subjects


def generate_simple_before_and_after(preprocessed_subjects: dict, output_dir):
    if not output_dir:
        output_dir = TemporaryDirectory()
    wf = Workflow(
        name="simple_before_after_report", base_dir=Path(output_dir) / "images/"
    )

    # Create a list to store all nodes
    nodes = []

    for s in preprocessed_subjects:
        # only run this on the T1w images for now
        if "T1w" in s["orig_path"]:
            o_path = Path(s["orig_path"])
            # Create a valid node name by replacing invalid characters but preserving session info
            # Use the full path to ensure uniqueness
            path_parts = s["orig_path"].split(os.sep)
            subject_part = next(
                (p for p in path_parts if p.startswith("sub-")), s["id"]
            )
            session_part = next((p for p in path_parts if p.startswith("ses-")), "")

            if session_part:
                valid_name = f"before_after_{subject_part}_{session_part}".replace(
                    "-", "_"
                )
            else:
                valid_name = f"before_after_{subject_part}".replace("-", "_")
            node = Node(
                SimpleBeforeAfterRPT(
                    before=s["orig_path"],
                    after=s["defaced_path"],
                    before_label="Original",
                    after_label="Defaced",
                    out_report=f"{s['id']}_simple_before_after.svg",
                ),
                name=valid_name,
            )
            nodes.append(node)

            # Add all nodes to the workflow
    wf.add_nodes(nodes)

    # Only run if we have nodes to process
    if nodes:
        wf.run(plugin="MultiProc", plugin_args={"n_procs": mp.cpu_count()})
        # Collect SVG files and move them to images folder
        collect_svg_reports(wf, output_dir)
    else:
        print("No T1w images found for SVG report generation")


def collect_svg_reports(wf, output_dir):
    """Collect SVG reports from workflow and move them to images folder."""
    import glob

    # Find all SVG files in the workflow directory
    workflow_dir = wf.base_dir
    svg_files = glob.glob(os.path.join(workflow_dir, "**", "*.svg"), recursive=True)

    print(f"Found {len(svg_files)} SVG reports")

    # Move each SVG to the images folder
    for svg_file in svg_files:
        filename = os.path.basename(svg_file)
        dest_path = os.path.join(output_dir, "images", filename)
        shutil.move(svg_file, dest_path)
        print(f"  Moved: {filename}")

    # Create HTML page for SVG reports
    create_svg_index_html(svg_files, output_dir)


def create_svg_index_html(svg_files, output_dir):
    """Create HTML index page for SVG reports."""

    svg_entries = ""
    for svg_file in svg_files:
        filename = os.path.basename(svg_file)
        subject_id = filename.replace("_simple_before_after.svg", "")

        svg_entries += f"""
        <div class="svg-report">
            <h3>{subject_id}</h3>
            <object data="images/{filename}" type="image/svg+xml" style="width: 100%; height: 600px;">
                <p>Your browser does not support SVG. <a href="images/{filename}">Download SVG</a></p>
            </object>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>PET Deface SVG Reports</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #f5f5f5;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                color: #333;
            }}
            .svg-report {{
                background: white;
                margin-bottom: 40px;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .svg-report h3 {{
                color: #2c3e50;
                margin-top: 0;
                margin-bottom: 15px;
                text-align: center;
            }}
            .navigation {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: white;
                padding: 15px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                z-index: 1000;
            }}
            .nav-button {{
                display: block;
                margin: 5px 0;
                padding: 8px 12px;
                background: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 12px;
                text-decoration: none;
            }}
            .nav-button:hover {{
                background: #2980b9;
            }}
        </style>
        <script>
            function scrollToReport(direction) {{
                const reports = document.querySelectorAll('.svg-report');
                const currentScroll = window.pageYOffset;
                const windowHeight = window.innerHeight;
                let targetReport = null;
                
                if (direction === 'next') {{
                    for (let report of reports) {{
                        if (report.offsetTop > currentScroll + windowHeight * 0.3) {{
                            targetReport = report;
                            break;
                        }}
                    }}
                    if (!targetReport && reports.length > 0) {{
                        targetReport = reports[0];
                    }}
                }} else if (direction === 'prev') {{
                    for (let i = reports.length - 1; i >= 0; i--) {{
                        if (reports[i].offsetTop < currentScroll - windowHeight * 0.3) {{
                            targetReport = reports[i];
                            break;
                        }}
                    }}
                    if (!targetReport && reports.length > 0) {{
                        targetReport = reports[reports.length - 1];
                    }}
                }}
                
                if (targetReport) {{
                    targetReport.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }}
            
            // Keyboard navigation
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'ArrowDown' || e.key === ' ') {{
                    e.preventDefault();
                    scrollToReport('next');
                }} else if (e.key === 'ArrowUp') {{
                    e.preventDefault();
                    scrollToReport('prev');
                }}
            }});
        </script>
    </head>
    <body>
        <div class="navigation">
            <button class="nav-button" onclick="scrollToReport('prev')">↑ Previous</button>
            <button class="nav-button" onclick="scrollToReport('next')">↓ Next</button>
            <div style="margin-top: 10px; font-size: 10px; color: #666;">
                Use arrow keys or spacebar
            </div>
        </div>
        
        <div class="header">
            <h1>PET Deface SVG Reports</h1>
            <p>Before/After comparison reports using nireports</p>
        </div>
        
        <div class="reports-container">
            {svg_entries}
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <a href="index.html">← Back to Index</a>
        </div>
    </body>
    </html>
    """

    svg_index_file = os.path.join(output_dir, "SimpleBeforeAfterRPT.html")
    with open(svg_index_file, "w") as f:
        f.write(html_content)

    print(f"Created SVG reports index: {svg_index_file}")


def create_overlay_comparison(orig_path, defaced_path, subject_id, output_dir):
    """Create overlay comparison with original as background and defaced as overlay."""

    # Load images
    orig_img = image.load_img(orig_path)
    defaced_img = image.load_img(defaced_path)

    # Create overlay plot
    fig = plotting.plot_anat(
        orig_img,
        title=f"Overlay: Original (background) + Defaced (overlay) - {subject_id}",
        display_mode="ortho",
        cut_coords=(0, 0, 0),
        colorbar=True,
        annotate=True,
    )

    # Add defaced as overlay
    plotting.plot_roi(defaced_img, bg_img=orig_img, figure=fig, alpha=0.7, color="red")

    # Save overlay
    overlay_file = os.path.join(output_dir, f"overlay_{subject_id}.png")
    fig.savefig(overlay_file, dpi=150)
    fig.close()

    return overlay_file


def create_animated_gif(orig_path, defaced_path, subject_id, output_dir, n_slices=20):
    """Create animated GIF showing different slices through the volume."""

    # Load images
    orig_img = image.load_img(orig_path)
    defaced_img = image.load_img(defaced_path)

    # Get data
    orig_data = orig_img.get_fdata()
    defaced_data = defaced_img.get_fdata()

    # Create figure for animation
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle(f"Animated Comparison - {subject_id}", fontsize=16)

    # Initialize plots
    slice_idx = orig_data.shape[2] // 2
    im1 = ax1.imshow(orig_data[:, :, slice_idx], cmap="gray")
    im2 = ax2.imshow(defaced_data[:, :, slice_idx], cmap="hot")

    ax1.set_title("Original")
    ax2.set_title("Defaced")
    ax1.axis("off")
    ax2.axis("off")

    def animate(frame):
        slice_idx = int(frame * orig_data.shape[2] / n_slices)
        im1.set_array(orig_data[:, :, slice_idx])
        im2.set_array(defaced_data[:, :, slice_idx])
        return [im1, im2]

    # Create animation
    anim = FuncAnimation(fig, animate, frames=n_slices, interval=200, blit=True)

    # Save as GIF
    gif_file = os.path.join(output_dir, f"animation_{subject_id}.gif")
    anim.save(gif_file, writer="pillow", fps=5)
    plt.close()

    return gif_file


def create_overlay_gif(image_files, subject_id, output_dir):
    """Create an animated GIF switching between original and defaced."""

    # Load the PNG images
    orig_png_path = os.path.join(
        output_dir, "images", image_files[0][2]
    )  # original image
    defaced_png_path = os.path.join(
        output_dir, "images", image_files[1][2]
    )  # defaced image

    # Open images
    orig_img = Image.open(orig_png_path)
    defaced_img = Image.open(defaced_png_path)

    # Ensure same size
    if orig_img.size != defaced_img.size:
        defaced_img = defaced_img.resize(orig_img.size, Image.Resampling.LANCZOS)

    # Create frames for the GIF
    frames = []

    # Frame 1: Original
    frames.append(orig_img.copy())

    # Frame 2: Defaced
    frames.append(defaced_img.copy())

    # Save as GIF
    gif_filename = f"overlay_{subject_id}.gif"
    gif_path = os.path.join(output_dir, "images", gif_filename)
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=1500,  # 1.5 seconds per frame
        loop=0,
    )

    return gif_filename


def load_and_preprocess_image(img_path):
    """Load image and take mean if it has more than 3 dimensions.
    Returns nibabel image if averaging was needed, otherwise returns original path."""
    img = nib.load(img_path)

    # Check if image has more than 3 dimensions
    if len(img.shape) > 3:
        print(
            f"  Converting 4D image to 3D by taking mean: {os.path.basename(img_path)}"
        )
        # Take mean across the 4th dimension
        data = img.get_fdata()
        mean_data = np.mean(data, axis=3)
        # Create new 3D image
        img = nib.Nifti1Image(mean_data, img.affine, img.header)
        return img  # Return nibabel image object
    else:
        return img_path  # Return original path if already 3D


def create_comparison_html(
    orig_img,
    defaced_img,
    subject_id,
    output_dir,
    display_mode="side-by-side",
    size="compact",
    orig_path=None,
    defaced_path=None,
):
    """Create HTML comparison page for a subject using nilearn ortho views."""

    # Get basenames for display - use actual filenames with BIDS suffixes if available
    if orig_path and defaced_path:
        orig_basename = os.path.basename(orig_path)
        defaced_basename = os.path.basename(defaced_path)
    else:
        # Fallback to generic names if paths not provided
        orig_basename = f"orig_{subject_id}.nii.gz"
        defaced_basename = f"defaced_{subject_id}.nii.gz"

    # Generate images and get their filenames
    image_files = []
    for label, img, basename, cmap in [
        ("original", orig_img, orig_basename, "hot"),  # Colored for original
        ("defaced", defaced_img, defaced_basename, "gray"),  # Grey for defaced
    ]:
        # Debug: Print what we're processing
        print(f"Processing {label} image: {basename}")
        print(f"  Image shape: {img.shape}")
        print(f"  Image data type: {img.get_data_dtype()}")
        print(
            f"  Image min/max: {img.get_fdata().min():.3f}/{img.get_fdata().max():.3f}"
        )

        # Create single sagittal slice using matplotlib directly
        img_data = img.get_fdata()
        x_midpoint = img_data.shape[0] // 2  # Get middle slice index

        # Extract the sagittal slice and rotate it properly using matrix multiplication
        sagittal_slice = img_data[x_midpoint, :, :]

        # Create 270-degree rotation matrix (to face left and right-side up)
        angle_rad = np.radians(270)
        cos_theta = np.cos(angle_rad)
        sin_theta = np.sin(angle_rad)
        rotation_matrix = np.array([[cos_theta, -sin_theta], [sin_theta, cos_theta]])

        # Get image dimensions
        h, w = sagittal_slice.shape

        # Create coordinate grid
        y, x = np.mgrid[0:h, 0:w]
        coords = np.vstack([x.ravel(), y.ravel()])

        # Center the coordinates
        center = np.array([w / 2, h / 2]).reshape(2, 1)
        coords_centered = coords - center

        # Apply rotation
        rotated_coords = rotation_matrix @ coords_centered

        # Move back to original coordinate system
        rotated_coords = rotated_coords + center

        # Interpolate the rotated image
        from scipy.interpolate import griddata

        rotated_slice = griddata(
            (rotated_coords[0], rotated_coords[1]),
            sagittal_slice.ravel(),
            (x, y),
            method="linear",
            fill_value=0,
        )

        # Crop the image to remove empty black space
        # Find non-zero regions
        non_zero_mask = rotated_slice > 0
        if np.any(non_zero_mask):
            # Get bounding box of non-zero pixels
            rows = np.any(non_zero_mask, axis=1)
            cols = np.any(non_zero_mask, axis=0)
            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]

            # Add some padding
            padding = 10
            rmin = max(0, rmin - padding)
            rmax = min(rotated_slice.shape[0], rmax + padding)
            cmin = max(0, cmin - padding)
            cmax = min(rotated_slice.shape[1], cmax + padding)

            # Crop the image
            cropped_slice = rotated_slice[rmin:rmax, cmin:cmax]
        else:
            cropped_slice = rotated_slice

        # Create figure with matplotlib
        fig, ax = plt.subplots(figsize=(8, 8))
        im = ax.imshow(cropped_slice, cmap=cmap, aspect="equal")
        ax.set_title(f"{label.title()}: {basename} ({cmap} colormap)")
        ax.axis("off")

        # Save as PNG
        png_filename = f"{label}_{subject_id}.png"
        png_path = os.path.join(output_dir, "images", png_filename)
        fig.savefig(png_path, dpi=150)
        plt.close(fig)

        image_files.append((label, basename, png_filename))

    # Create overlay GIF if we have both images
    if len(image_files) == 2:
        overlay_gif = create_overlay_gif(image_files, subject_id, output_dir)
        image_files.append(("overlay", "comparison", overlay_gif))

    # Create the comparison HTML with embedded images
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>PET Deface Comparison - {subject_id}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #f5f5f5;
                scroll-behavior: smooth;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                color: #333;
            }}
            .comparison {{
                display: flex;
                justify-content: center;
                gap: {20 if size == "compact" else 40}px;
                margin-bottom: 20px;
            }}
            .viewer {{
                background: white;
                padding: {20 if size == "compact" else 30}px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                text-align: center;
                flex: 1;
                max-width: {45 if size == "compact" else 48}%;
            }}
            .viewer h3 {{
                margin-top: 0;
                color: #2c3e50;
                font-size: {14 if size == "compact" else 18}px;
            }}
            .viewer img {{
                width: 100%;
                height: auto;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .navigation {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: white;
                padding: 15px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                z-index: 1000;
            }}
            .nav-button {{
                display: block;
                margin: 5px 0;
                padding: 8px 12px;
                background: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 12px;
                text-decoration: none;
            }}
            .nav-button:hover {{
                background: #2980b9;
            }}
            .nav-button:disabled {{
                background: #bdc3c7;
                cursor: not-allowed;
            }}
        </style>
        <script>
            function scrollToComparison(direction) {{
                const comparisons = document.querySelectorAll('.comparison');
                const currentScroll = window.pageYOffset;
                const windowHeight = window.innerHeight;
                
                let targetComparison = null;
                
                if (direction === 'next') {{
                    for (let comp of comparisons) {{
                        if (comp.offsetTop > currentScroll + windowHeight * 0.3) {{
                            targetComparison = comp;
                            break;
                        }}
                    }}
                    if (!targetComparison && comparisons.length > 0) {{
                        targetComparison = comparisons[0];
                    }}
                }} else if (direction === 'prev') {{
                    for (let i = comparisons.length - 1; i >= 0; i--) {{
                        if (comparisons[i].offsetTop < currentScroll - windowHeight * 0.3) {{
                            targetComparison = comparisons[i];
                            break;
                        }}
                    }}
                    if (!targetComparison && comparisons.length > 0) {{
                        targetComparison = comparisons[comparisons.length - 1];
                    }}
                }}
                
                if (targetComparison) {{
                    targetComparison.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }}
            
            // Keyboard navigation
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'ArrowDown' || e.key === ' ') {{
                    e.preventDefault();
                    scrollToComparison('next');
                }} else if (e.key === 'ArrowUp') {{
                    e.preventDefault();
                    scrollToComparison('prev');
                }}
            }});
        </script>
    </head>
    <body>
        <div class="navigation">
            <button class="nav-button" onclick="scrollToComparison('prev')">↑ Previous</button>
            <button class="nav-button" onclick="scrollToComparison('next')">↓ Next</button>
            <div style="margin-top: 10px; font-size: 10px; color: #666;">
                Use arrow keys or spacebar
            </div>
        </div>
        
        <div class="header">
            <h1>PET Deface Comparison - {subject_id}</h1>
            <p>Side-by-side comparison of original vs defaced neuroimaging data</p>
        </div>
        
        <div class="comparison">
    """

    # Add content based on display mode
    if display_mode == "side-by-side":
        # Add images side by side only
        html_content += f"""
            <div class="viewer">
                <h3>{image_files[0][0].title()}: {image_files[0][1]}</h3>
                <img src="{image_files[0][2]}" alt="{image_files[0][0].title()}: {image_files[0][1]}">
            </div>
            <div class="viewer">
                <h3>{image_files[1][0].title()}: {image_files[1][1]}</h3>
                <img src="{image_files[1][2]}" alt="{image_files[1][0].title()}: {image_files[1][1]}">
            </div>
        </div>
        """
    elif display_mode == "gif":
        # Show only the GIF
        if len(image_files) > 2:
            html_content += f"""
            <div style="text-align: center;">
                <h3>Animated Comparison</h3>
                <p>Switching between Original and Defaced images</p>
                <img src="{image_files[2][2]}" alt="Animated comparison" style="max-width: 90%; border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);">
            </div>
        </div>
        """
        else:
            html_content += """
        </div>
        """

    html_content += """
        <div style="text-align: center; margin-top: 30px;">
            <a href="index.html">← Back to Index</a>
        </div>
    </body>
    </html>
    """

    # Save the comparison HTML
    comparison_file = os.path.join(output_dir, f"comparison_{subject_id}.html")
    with open(comparison_file, "w") as f:
        f.write(html_content)

    return comparison_file


def process_subject(subject, output_dir, size="compact"):
    """Process a single subject (for parallel processing)."""
    print(f"Processing {subject['id']}...")
    try:
        comparison_file = create_comparison_html(
            subject["orig_img"],
            subject["defaced_img"],
            subject["id"],
            output_dir,
            "side-by-side",  # Always generate side-by-side for individual pages
            size,
            subject["orig_path"],
            subject["defaced_path"],
        )
        print(f"  Completed: {subject['id']}")
        return comparison_file
    except Exception as e:
        print(f"  Error processing {subject['id']}: {e}")
        return None


def build_subjects_from_datasets(orig_dir, defaced_dir):
    """Build subject list with file paths."""

    # Get all NIfTI files but exclude derivatives and workflow folders
    def get_nifti_files(directory):
        all_files = glob(os.path.join(directory, "**", "*.nii*"), recursive=True)
        # Filter out files in derivatives, workflow, or other processing folders
        filtered_files = []
        for file_path in all_files:
            # Skip files in derivatives, workflow, or processing-related directories
            path_parts = file_path.split(os.sep)
            skip_dirs = ["derivatives", "work", "wf", "tmp", "temp", "scratch", "cache"]
            if not any(skip_dir in path_parts for skip_dir in skip_dirs):
                filtered_files.append(file_path)
        return filtered_files

    orig_files = get_nifti_files(orig_dir)
    defaced_files = get_nifti_files(defaced_dir)

    def strip_ext(path):
        base = os.path.basename(path)
        if base.endswith(".gz"):
            base = os.path.splitext(os.path.splitext(base)[0])[0]
        else:
            base = os.path.splitext(base)[0]
        return base

    def get_unique_key(file_path):
        """Create a unique key that includes session information."""
        parts = file_path.split(os.sep)
        sub_id = next((p for p in parts if p.startswith("sub-")), "")
        session = next((p for p in parts if p.startswith("ses-")), "")
        basename = strip_ext(file_path)

        # Create unique key that includes session if present
        if session:
            return f"{sub_id}_{session}_{basename}"
        else:
            return f"{sub_id}_{basename}"

    # Create maps with unique keys
    orig_map = {get_unique_key(f): f for f in orig_files}
    defaced_map = {get_unique_key(f): f for f in defaced_files}
    common_keys = sorted(set(orig_map.keys()) & set(defaced_map.keys()))

    # Debug: Print what files are being found
    print(f"Found {len(orig_files)} files in original directory")
    print(f"Found {len(defaced_files)} files in defaced directory")
    print(f"Found {len(common_keys)} common files")
    for key in common_keys:
        print(f"  {key}: {orig_map[key]} -> {defaced_map[key]}")

    subjects = []
    for key in common_keys:
        orig_path = orig_map[key]
        defaced_path = defaced_map[key]
        parts = orig_path.split(os.sep)
        sub_id = next((p for p in parts if p.startswith("sub-")), key)
        session = next((p for p in parts if p.startswith("ses-")), "")

        # Create a unique subject ID that includes session if present
        if session:
            subject_id = f"{sub_id}_{session}"
        else:
            subject_id = sub_id

        # Check if this is a T1w file (prioritize T1w over PET)
        is_t1w = "T1w" in orig_path or "T1w" in defaced_path

        subjects.append(
            {
                "id": subject_id,
                "orig_path": orig_path,
                "defaced_path": defaced_path,
                "is_t1w": is_t1w,
            }
        )

    # Sort subjects to prioritize T1w files over PET files
    subjects.sort(key=lambda x: (not x["is_t1w"], x["id"]))

    # For each subject, only keep the T1w file if available, otherwise keep the first file
    filtered_subjects = []
    seen_subjects = set()

    for subject in subjects:
        subject_id = subject["id"]
        if subject_id not in seen_subjects:
            filtered_subjects.append(subject)
            seen_subjects.add(subject_id)
        elif subject["is_t1w"]:
            # Replace the existing entry with the T1w version
            filtered_subjects = [s for s in filtered_subjects if s["id"] != subject_id]
            filtered_subjects.append(subject)

    if not filtered_subjects:
        print("No matching NIfTI files found in both datasets.")
        exit(1)

    return filtered_subjects


def create_side_by_side_index_html(subjects, output_dir, size="compact"):
    """Create index page for side-by-side comparisons."""

    comparisons_html = ""
    for subject in subjects:
        subject_id = subject["id"]

        # Use actual filenames with BIDS suffixes instead of generic names
        orig_basename = os.path.basename(subject["orig_path"])
        defaced_basename = os.path.basename(subject["defaced_path"])

        # Check if the PNG files exist
        orig_png = f"images/original_{subject_id}.png"
        defaced_png = f"images/defaced_{subject_id}.png"

        comparisons_html += f"""
        <div class="subject-comparison">
            <h2>{subject_id}</h2>
            <div class="comparison-grid">
                <div class="viewer">
                    <h3>Original: {orig_basename}</h3>
                    <img src="{orig_png}" alt="Original: {orig_basename}">
                </div>
                <div class="viewer">
                    <h3>Defaced: {defaced_basename}</h3>
                    <img src="{defaced_png}" alt="Defaced: {defaced_basename}">
                </div>
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>PET Deface Comparisons - Side by Side</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #f5f5f5;
                scroll-behavior: smooth;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                color: #333;
            }}
            .subject-comparison {{
                background: white;
                margin-bottom: 40px;
                padding: {30 if size == "compact" else 40}px;
                border-radius: 15px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .subject-comparison h2 {{
                color: #2c3e50;
                margin-top: 0;
                margin-bottom: 20px;
                text-align: center;
                font-size: {1.5 if size == "compact" else 2}em;
            }}
            .comparison-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: {30 if size == "compact" else 40}px;
                align-items: start;
            }}
            .viewer {{
                text-align: center;
            }}
            .viewer h3 {{
                color: #34495e;
                margin-bottom: 15px;
                font-size: {1.1 if size == "compact" else 1.3}em;
            }}
            .viewer img {{
                width: 100%;
                height: auto;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .navigation {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: white;
                padding: 15px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                z-index: 1000;
            }}
            .nav-button {{
                display: block;
                margin: 5px 0;
                padding: 8px 12px;
                background: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 12px;
                text-decoration: none;
            }}
            .nav-button:hover {{
                background: #2980b9;
            }}
            .nav-button:disabled {{
                background: #bdc3c7;
                cursor: not-allowed;
            }}
        </style>
        <script>
            function scrollToComparison(direction) {{
                const comparisons = document.querySelectorAll('.subject-comparison');
                const currentScroll = window.pageYOffset;
                const windowHeight = window.innerHeight;
                let targetComparison = null;
                if (direction === 'next') {{
                    for (let comp of comparisons) {{
                        if (comp.offsetTop > currentScroll + windowHeight * 0.3) {{
                            targetComparison = comp;
                            break;
                        }}
                    }}
                    if (!targetComparison && comparisons.length > 0) {{
                        targetComparison = comparisons[0];
                    }}
                }} else if (direction === 'prev') {{
                    for (let i = comparisons.length - 1; i >= 0; i--) {{
                        if (comparisons[i].offsetTop < currentScroll - windowHeight * 0.3) {{
                            targetComparison = comparisons[i];
                            break;
                        }}
                    }}
                    if (!targetComparison && comparisons.length > 0) {{
                        targetComparison = comparisons[comparisons.length - 1];
                    }}
                }}
                
                if (targetComparison) {{
                    targetComparison.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }}
            
            // Keyboard navigation
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'ArrowDown' || e.key === ' ') {{
                    e.preventDefault();
                    scrollToComparison('next');
                }} else if (e.key === 'ArrowUp') {{
                    e.preventDefault();
                    scrollToComparison('prev');
                }}
            }});
        </script>
    </head>
    <body>
        <div class="navigation">
            <button class="nav-button" onclick="scrollToComparison('prev')">↑ Previous</button>
            <button class="nav-button" onclick="scrollToComparison('next')">↓ Next</button>
            <div style="margin-top: 10px; font-size: 10px; color: #666;">
                Use arrow keys or spacebar
            </div>
        </div>
        
        <div class="header">
            <h1>PET Deface Comparisons - Side by Side</h1>
            <p>Static side-by-side comparison of original vs defaced neuroimaging data</p>
        </div>
        
        <div class="comparisons-container">
            {comparisons_html}
        </div>
    </body>
    </html>
    """

    index_file = os.path.join(output_dir, "side_by_side.html")
    with open(index_file, "w") as f:
        f.write(html_content)

    return index_file


def create_gif_index_html(subjects, output_dir, size="compact"):
    """Create index page for GIF comparisons."""

    comparisons_html = ""
    for subject in subjects:
        subject_id = subject["id"]
        overlay_gif = f"images/overlay_{subject_id}.gif"

        comparisons_html += f"""
        <div class="subject-comparison">
            <h2>{subject_id}</h2>
            <div style="text-align: center;">
                <h3>Animated Comparison</h3>
                <p>Switching between Original and Defaced images</p>
                <img src="{overlay_gif}" alt="Animated comparison" style="max-width: 63%; border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);">
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>PET Deface Comparisons - Animated</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #f5f5f5;
                scroll-behavior: smooth;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                color: #333;
            }}
            .subject-comparison {{
                background: white;
                margin-bottom: 40px;
                padding: {30 if size == "compact" else 40}px;
                border-radius: 15px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .subject-comparison h2 {{
                color: #2c3e50;
                margin-top: 0;
                margin-bottom: 20px;
                text-align: center;
                font-size: {1.5 if size == "compact" else 2}em;
            }}
            .navigation {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: white;
                padding: 15px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                z-index: 1000;
            }}
            .nav-button {{
                display: block;
                margin: 5px 0;
                padding: 8px 12px;
                background: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 12px;
                text-decoration: none;
            }}
            .nav-button:hover {{
                background: #2980b9;
            }}
            .nav-button:disabled {{
                background: #bdc3c7;
                cursor: not-allowed;
            }}
        </style>
        <script>
            function scrollToComparison(direction) {{
                const comparisons = document.querySelectorAll('.subject-comparison');
                const currentScroll = window.pageYOffset;
                const windowHeight = window.innerHeight;
                let targetComparison = null;
                if (direction === 'next') {{
                    for (let comp of comparisons) {{
                        if (comp.offsetTop > currentScroll + windowHeight * 0.3) {{
                            targetComparison = comp;
                            break;
                        }}
                    }}
                    if (!targetComparison && comparisons.length > 0) {{
                        targetComparison = comparisons[0];
                    }}
                }} else if (direction === 'prev') {{
                    for (let i = comparisons.length - 1; i >= 0; i--) {{
                        if (comparisons[i].offsetTop < currentScroll - windowHeight * 0.3) {{
                            targetComparison = comparisons[i];
                            break;
                        }}
                    }}
                    if (!targetComparison && comparisons.length > 0) {{
                        targetComparison = comparisons[comparisons.length - 1];
                    }}
                }}
                
                if (targetComparison) {{
                    targetComparison.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }}
            
            // Keyboard navigation
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'ArrowDown' || e.key === ' ') {{
                    e.preventDefault();
                    scrollToComparison('next');
                }} else if (e.key === 'ArrowUp') {{
                    e.preventDefault();
                    scrollToComparison('prev');
                }}
            }});
        </script>
    </head>
    <body>
        <div class="navigation">
            <button class="nav-button" onclick="scrollToComparison('prev')">↑ Previous</button>
            <button class="nav-button" onclick="scrollToComparison('next')">↓ Next</button>
            <div style="margin-top: 10px; font-size: 10px; color: #666;">
                Use arrow keys or spacebar
            </div>
        </div>
        
        <div class="header">
            <h1>PET Deface Comparisons - Animated</h1>
            <p>Animated GIF comparison of original vs defaced neuroimaging data</p>
        </div>
        
        <div class="comparisons-container">
            {comparisons_html}
        </div>
    </body>
    </html>
    """

    index_file = os.path.join(output_dir, "animated.html")
    with open(index_file, "w") as f:
        f.write(html_content)

    return index_file


def run_qa(
    faced_dir,
    defaced_dir,
    output_dir=None,
    subject=None,
    n_jobs=None,
    size="compact",
    open_browser=False,
):
    """
    Run QA report generation programmatically.

    Args:
        faced_dir (str): Path to original (faced) dataset directory
        defaced_dir (str): Path to defaced dataset directory
        output_dir (str, optional): Output directory for HTML files
        subject (str, optional): Filter to specific subject
        n_jobs (int, optional): Number of parallel jobs
        size (str): Image size - 'compact' or 'full'
        open_browser (bool): Whether to open browser automatically

    Returns:
        dict: Information about generated files
    """
    faced_dir = os.path.abspath(faced_dir)
    defaced_dir = os.path.abspath(defaced_dir)

    # Create output directory name based on input directories
    if output_dir:
        output_dir = os.path.abspath(output_dir)
    else:
        orig_folder = os.path.basename(faced_dir)
        defaced_folder = os.path.basename(defaced_dir)
        output_dir = os.path.abspath(f"{orig_folder}_{defaced_folder}_qa")

    # Create output directory and images subdirectory
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Build subjects list
    subjects = build_subjects_from_datasets(faced_dir, defaced_dir)
    print(f"Found {len(subjects)} subjects with matching files")

    # Filter to specific subject if requested
    if subject:
        original_count = len(subjects)
        subjects = [s for s in subjects if subject in s["id"]]
        print(
            f"Filtered to {len(subjects)} subjects matching '{subject}' (from {original_count} total)"
        )

        if not subjects:
            print(f"No subjects found matching '{subject}'")
            print("Available subjects:")
            all_subjects = build_subjects_from_datasets(faced_dir, defaced_dir)
            for s in all_subjects:
                print(f"  - {s['id']}")
            raise ValueError(f"No subjects found matching '{subject}'")

    # Set number of jobs for parallel processing
    if n_jobs is None:
        n_jobs = mp.cpu_count()
    print(f"Using {n_jobs} parallel processes")

    # Preprocess all images once (4D→3D conversion)
    preprocessed_subjects = preprocess_images(subjects, output_dir, n_jobs)

    # create nireports svg's for comparison
    generate_simple_before_and_after(
        preprocessed_subjects=preprocessed_subjects, output_dir=output_dir
    )

    # Process subjects in parallel
    print("Generating comparisons...")
    with mp.Pool(processes=n_jobs) as pool:
        # Create a partial function with the output_dir and size fixed
        process_func = partial(
            process_subject,
            output_dir=output_dir,
            size=size,
        )

        # Process all subjects in parallel
        results = pool.map(process_func, preprocessed_subjects)

    # Count successful results
    successful = [r for r in results if r is not None]
    print(
        f"Successfully processed {len(successful)} out of {len(preprocessed_subjects)} subjects"
    )

    # Create both HTML files
    side_by_side_file = create_side_by_side_index_html(
        preprocessed_subjects, output_dir, size
    )
    animated_file = create_gif_index_html(preprocessed_subjects, output_dir, size)

    # Create a simple index that links to both
    index_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>PET Deface Comparisons</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 50px;
                background: #f5f5f5;
                text-align: center;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            h1 {{
                color: #2c3e50;
                margin-bottom: 30px;
            }}
            .link-button {{
                display: inline-block;
                margin: 15px;
                padding: 15px 30px;
                background: #3498db;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-size: 16px;
                transition: background 0.3s;
            }}
            .link-button:hover {{
                background: #2980b9;
            }}
            .description {{
                color: #666;
                margin-bottom: 30px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>PET Deface Comparisons</h1>
            <p class="description">Choose your preferred viewing mode:</p>
            
            <a href="side_by_side.html" class="link-button">Side by Side View</a>
            <a href="animated.html" class="link-button">Animated GIF View</a>
            <a href="SimpleBeforeAfterRPT.html" class="link-button">SVG Reports View</a>
            
            <p style="margin-top: 30px; color: #999; font-size: 14px;">
                Generated with {len(preprocessed_subjects)} subjects
            </p>
        </div>
    </body>
    </html>
    """

    index_file = os.path.join(output_dir, "index.html")
    with open(index_file, "w") as f:
        f.write(index_html)

    # Save the command with full expanded paths
    import sys

    command_parts = [
        sys.executable,
        os.path.abspath(__file__),
        "--faced-dir",
        faced_dir,
        "--defaced-dir",
        defaced_dir,
        "--output-dir",
        output_dir,
        "--size",
        size,
    ]
    if n_jobs:
        command_parts.extend(["--n-jobs", str(n_jobs)])
    if subject:
        command_parts.extend(["--subject", subject])
    if open_browser:
        command_parts.append("--open-browser")

    command_str = " ".join(command_parts)

    command_file = os.path.join(output_dir, "command.txt")
    with open(command_file, "w") as f:
        f.write(f"# Command used to generate this comparison\n")
        f.write(
            f"# Generated on: {__import__('datetime').datetime.now().isoformat()}\n\n"
        )
        f.write(command_str + "\n")

    print(f"Created side-by-side view: {side_by_side_file}")
    print(f"Created animated view: {animated_file}")
    print(f"Created main index: {index_file}")
    print(f"Saved command to: {command_file}")

    # Open browser if requested
    if open_browser:
        webbrowser.open(f"file://{index_file}")
        print(f"Opened browser to: {index_file}")

    print(f"\nAll files generated in: {output_dir}")
    print(f"Open index.html in your browser to view comparisons")

    return {
        "output_dir": output_dir,
        "side_by_side_file": side_by_side_file,
        "animated_file": animated_file,
        "index_file": index_file,
        "command_file": command_file,
        "subjects_processed": len(successful),
        "total_subjects": len(preprocessed_subjects),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate static HTML comparisons of PET deface results using nilearn."
    )
    parser.add_argument(
        "--faced-dir", required=True, help="Directory for original (faced) dataset"
    )
    parser.add_argument(
        "--defaced-dir", required=True, help="Directory for defaced dataset"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for HTML files (default: {orig_folder}_{defaced_folder}_qa)",
    )
    parser.add_argument(
        "--open-browser", action="store_true", help="Open browser automatically"
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=None,
        help="Number of parallel jobs (default: all cores)",
    )
    parser.add_argument(
        "--subject",
        type=str,
        help="Filter to specific subject (e.g., 'sub-01' or 'sub-01_ses-baseline')",
    )

    parser.add_argument(
        "--size",
        type=str,
        choices=["compact", "full"],
        default="compact",
        help="Image size: 'compact' for closer together or 'full' for entire page width",
    )
    args = parser.parse_args()

    return run_qa(
        faced_dir=args.faced_dir,
        defaced_dir=args.defaced_dir,
        output_dir=args.output_dir,
        subject=args.subject,
        n_jobs=args.n_jobs,
        size=args.size,
        open_browser=args.open_browser,
    )


if __name__ == "__main__":
    main()
