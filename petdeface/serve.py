import argparse
import os
import tempfile
import shutil
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
    orig_png_path = os.path.join(output_dir, image_files[0][2])  # original image
    defaced_png_path = os.path.join(output_dir, image_files[1][2])  # defaced image

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
    gif_path = os.path.join(output_dir, gif_filename)
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=1500,  # 1.5 seconds per frame
        loop=0,
    )

    return gif_filename


def load_and_preprocess_image(img_path):
    """Load image and take mean if it has more than 3 dimensions."""
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

    return img


def create_comparison_html(
    orig_path,
    defaced_path,
    subject_id,
    output_dir,
    display_mode="side-by-side",
    size="compact",
):
    """Create HTML comparison page for a subject using nilearn ortho views."""

    # Get basenames for display
    orig_basename = os.path.basename(orig_path)
    defaced_basename = os.path.basename(defaced_path)

    # Generate images and get their filenames
    image_files = []
    for label, img_path, cmap in [
        ("original", orig_path, "hot"),  # Colored for original
        ("defaced", defaced_path, "gray"),  # Grey for defaced
    ]:
        # Get the basename for display
        basename = os.path.basename(img_path)

        # Load and preprocess image (handle 4D if needed)
        img = load_and_preprocess_image(img_path)

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
        png_path = os.path.join(output_dir, png_filename)
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
                        if (comp.offsetTop > currentScroll + 100) {{
                            targetComparison = comp;
                            break;
                        }}
                    }}
                }} else if (direction === 'prev') {{
                    for (let i = comparisons.length - 1; i >= 0; i--) {{
                        if (comparisons[i].offsetTop < currentScroll - 100) {{
                            targetComparison = comparisons[i];
                            break;
                        }}
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
            subject["orig_path"],
            subject["defaced_path"],
            subject["id"],
            output_dir,
            "side-by-side",  # Always generate side-by-side for individual pages
            size,
        )
        print(f"  Completed: {subject['id']}")
        return comparison_file
    except Exception as e:
        print(f"  Error processing {subject['id']}: {e}")
        return None


def build_subjects_from_datasets(orig_dir, defaced_dir):
    """Build subject list with file paths."""
    orig_files = glob(os.path.join(orig_dir, "**", "*.nii*"), recursive=True)
    defaced_files = glob(os.path.join(defaced_dir, "**", "*.nii*"), recursive=True)

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

        subjects.append(
            {
                "id": subject_id,
                "orig_path": orig_path,
                "defaced_path": defaced_path,
            }
        )

    if not subjects:
        print("No matching NIfTI files found in both datasets.")
        exit(1)

    return subjects


def create_side_by_side_index_html(subjects, output_dir, size="compact"):
    """Create index page for side-by-side comparisons."""

    comparisons_html = ""
    for subject in subjects:
        subject_id = subject["id"]
        orig_basename = os.path.basename(subject["orig_path"])
        defaced_basename = os.path.basename(subject["defaced_path"])

        # Check if the PNG files exist
        orig_png = f"original_{subject_id}.png"
        defaced_png = f"defaced_{subject_id}.png"

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
                
                let targetComparison = null;
                
                if (direction === 'next') {{
                    for (let comp of comparisons) {{
                        if (comp.offsetTop > currentScroll + 100) {{
                            targetComparison = comp;
                            break;
                        }}
                    }}
                }} else if (direction === 'prev') {{
                    for (let i = comparisons.length - 1; i >= 0; i--) {{
                        if (comparisons[i].offsetTop < currentScroll - 100) {{
                            targetComparison = comparisons[i];
                            break;
                        }}
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
        overlay_gif = f"overlay_{subject_id}.gif"

        comparisons_html += f"""
        <div class="subject-comparison">
            <h2>{subject_id}</h2>
            <div style="text-align: center;">
                <h3>Animated Comparison</h3>
                <p>Switching between Original and Defaced images</p>
                <img src="{overlay_gif}" alt="Animated comparison" style="max-width: 90%; border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);">
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
                
                let targetComparison = null;
                
                if (direction === 'next') {{
                    for (let comp of comparisons) {{
                        if (comp.offsetTop > currentScroll + 100) {{
                            targetComparison = comp;
                            break;
                        }}
                    }}
                }} else if (direction === 'prev') {{
                    for (let i = comparisons.length - 1; i >= 0; i--) {{
                        if (comparisons[i].offsetTop < currentScroll - 100) {{
                            targetComparison = comparisons[i];
                            break;
                        }}
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
        default="petdeface_comparisons",
        help="Output directory for HTML files",
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

    faced_dir = os.path.abspath(args.faced_dir)
    defaced_dir = os.path.abspath(args.defaced_dir)
    output_dir = os.path.abspath(args.output_dir)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Build subjects list
    subjects = build_subjects_from_datasets(faced_dir, defaced_dir)
    print(f"Found {len(subjects)} subjects with matching files")

    # Filter to specific subject if requested
    if args.subject:
        original_count = len(subjects)
        subjects = [s for s in subjects if args.subject in s["id"]]
        print(
            f"Filtered to {len(subjects)} subjects matching '{args.subject}' (from {original_count} total)"
        )

        if not subjects:
            print(f"No subjects found matching '{args.subject}'")
            print("Available subjects:")
            all_subjects = build_subjects_from_datasets(faced_dir, defaced_dir)
            for s in all_subjects:
                print(f"  - {s['id']}")
            exit(1)

    # Set number of jobs for parallel processing
    n_jobs = args.n_jobs if args.n_jobs else mp.cpu_count()
    print(f"Using {n_jobs} parallel processes")

    # Process subjects in parallel
    print("Generating comparisons...")
    with mp.Pool(processes=n_jobs) as pool:
        # Create a partial function with the output_dir and size fixed
        process_func = partial(
            process_subject,
            output_dir=output_dir,
            size=args.size,
        )

        # Process all subjects in parallel
        results = pool.map(process_func, subjects)

    # Count successful results
    successful = [r for r in results if r is not None]
    print(f"Successfully processed {len(successful)} out of {len(subjects)} subjects")

    # Create both HTML files
    side_by_side_file = create_side_by_side_index_html(subjects, output_dir, args.size)
    animated_file = create_gif_index_html(subjects, output_dir, args.size)

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
            
            <p style="margin-top: 30px; color: #999; font-size: 14px;">
                Generated with {len(subjects)} subjects
            </p>
        </div>
    </body>
    </html>
    """

    index_file = os.path.join(output_dir, "index.html")
    with open(index_file, "w") as f:
        f.write(index_html)

    print(f"Created side-by-side view: {side_by_side_file}")
    print(f"Created animated view: {animated_file}")
    print(f"Created main index: {index_file}")

    # Open browser if requested
    if args.open_browser:
        webbrowser.open(f"file://{index_file}")
        print(f"Opened browser to: {index_file}")

    print(f"\nAll files generated in: {output_dir}")
    print(f"Open index.html in your browser to view comparisons")


if __name__ == "__main__":
    main()
