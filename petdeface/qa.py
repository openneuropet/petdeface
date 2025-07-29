#!/usr/bin/env python3
"""
Simple QA system for PET deface SVG reports.
"""

import os
import glob
import argparse
import webbrowser
import json
import http.server
import socketserver
import time
import subprocess
import signal
import sys
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


def collect_svg_reports(defaced_dir, output_dir):
    """Collect SVG files from derivatives/petdeface directory."""
    derivatives_dir = os.path.join(defaced_dir, "derivatives", "petdeface")
    if not os.path.exists(derivatives_dir):
        print(
            f"Warning: derivatives/petdeface directory not found at {derivatives_dir}"
        )
        print("Looking for SVG files in the main defaced directory...")
        derivatives_dir = defaced_dir

    # Find all SVG files recursively, excluding the qa directory
    svg_files = []
    for svg_file in glob.glob(
        os.path.join(derivatives_dir, "**", "*.svg"), recursive=True
    ):
        # Skip files in the qa directory
        if "qa" not in svg_file:
            svg_files.append(svg_file)

    if not svg_files:
        print("No SVG files found!")
        return []

    print(f"Found {len(svg_files)} SVG files")

    # Just return the original file paths - no copying needed
    for svg_file in svg_files:
        print(f"Found: {Path(svg_file).name}")

    return svg_files


def kill_process_on_port(port):
    """Kill any process using the specified port."""
    try:
        # Find process using the port
        result = subprocess.run(
            ["lsof", "-ti", str(port)], capture_output=True, text=True, check=False
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid:
                    print(f"Killing process {pid} using port {port}")
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except ProcessLookupError:
                        print(f"Process {pid} already terminated")
                    except ValueError:
                        print(f"Invalid PID: {pid}")

            # Give it a moment to fully terminate
            time.sleep(0.5)
            print(f"Port {port} is now free")
        else:
            print(f"Port {port} is already free")

    except FileNotFoundError:
        print("Warning: 'lsof' command not found, cannot check for existing processes")
    except Exception as e:
        print(f"Error killing process on port {port}: {e}")


def start_local_server(port=8000, directory=None):
    """Start a simple HTTP server to serve files locally."""
    if directory is None:
        directory = os.getcwd()

    os.chdir(directory)

    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            # Add CORS headers to allow cross-origin requests
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            super().end_headers()

    handler = CustomHTTPRequestHandler

    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Server started at http://localhost:{port}")
        print(f"Serving files from: {directory}")
        print("Press Ctrl+C to stop the server")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


def collect_nifti_files(defaced_dir):
    """Collect NIfTI files containing 'defaced' from derivatives/petdeface directory."""
    derivatives_dir = os.path.join(defaced_dir, "derivatives", "petdeface")
    if not os.path.exists(derivatives_dir):
        print(
            f"Warning: derivatives/petdeface directory not found at {derivatives_dir}"
        )
        return {}

    # Find all NIfTI files containing 'defaced'
    nifti_files = {}
    for nifti_file in glob.glob(
        os.path.join(derivatives_dir, "**", "*.nii*"), recursive=True
    ):
        filename = Path(nifti_file).name

        # Check if file contains 'defaced'
        if ("defaced" in filename and "T1w" in filename) or (
            "defaced" in filename and "wavg" in filename and "pet" in filename
        ):
            # Extract subject ID from path
            path_parts = Path(nifti_file).parts
            subject_id = None
            for part in path_parts:
                if part.startswith("sub-"):
                    subject_id = part
                    break

            if subject_id:
                if subject_id not in nifti_files:
                    nifti_files[subject_id] = []
                nifti_files[subject_id].append(nifti_file)

    print(f"Found NIfTI files for {len(nifti_files)} subjects")
    for subject_id, files in nifti_files.items():
        print(f"  {subject_id}: {len(files)} files")
        for file in files:
            print(f"    {Path(file).name}")

    return nifti_files


def create_nifti_viewer_html(subject_id, nifti_files, output_dir, server_port=8000):
    """Create HTML viewer with rotating NIfTI images for a subject."""

    # Filter files to include only specific types
    filtered_files = []
    for nifti_file in nifti_files:
        filename = Path(nifti_file).name.lower()

        # Include files that are:
        # 1. T1w defaced images
        # 2. PET defaced images that are averaged (wavg)
        # 3. PET defaced images that are warped
        # 4. PET defaced images that are in T1w space
        if "defaced" in filename:
            if "t1w" in filename:
                # Include T1w defaced images
                filtered_files.append(nifti_file)
            elif "pet" in filename:
                # For PET images, only include if they are averaged (wavg) or have special processing
                if (
                    "wavg" in filename
                    or "warped" in filename
                    or "space-t1w" in filename
                ):
                    filtered_files.append(nifti_file)

    if not filtered_files:
        print(f"No qualifying NIfTI files found for {subject_id}")
        return None

    # Create HTML content
    html_content = f"""
    <!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8">
    <title>NiiVue - {subject_id} Defaced Images</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f0f0;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
        }}
        .comparison-title {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 20px 0;
                color: #333;
            }}
        .viewers-container {{
            display: flex;
            gap: 30px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        .viewer {{
            display: flex;
            flex-direction: column;
            align-items: center;
                background: white;
                padding: 20px;
                border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        .viewer-title {{
            font-size: 1.5em;
            font-weight: bold;
                margin-bottom: 15px;
            color: #333;
                text-align: center;
            }}
        .file-path {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 15px;
            text-align: center;
            max-width: 500px;
            word-break: break-all;
        }}
        canvas {{
            border: 2px solid #ddd;
                border-radius: 5px;
        }}
        .controls {{
            margin-top: 30px;
                text-align: center;
            }}
        .slider-container {{
                display: flex;
            align-items: center;
                justify-content: center;
            gap: 15px;
                margin-bottom: 20px;
            }}
        .slider {{
            width: 300px;
        }}
        .reset-btn {{
            padding: 10px 20px;
            background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            font-size: 1em;
        }}
        .reset-btn:hover {{
            background-color: #c82333;
            }}
        </style>
    </head>
    <body>
        <div class="header">
        <div class="comparison-title">{subject_id}</div>
        <div class="scan-type">Defaced NIfTI Images</div>
        </div>
        
    <div class="viewers-container">
"""

    # Add a viewer for each NIfTI file
    for i, nifti_file in enumerate(filtered_files):
        filename = Path(nifti_file).name
        # Create a label based on the filename
        label = filename.replace(".nii.gz", "").replace(".nii", "")
        label = label.replace("_", " ").replace("-", " ")

        # Convert file path to HTTP URL
        # Get the relative path from the derivatives directory
        derivatives_dir = os.path.join(os.path.dirname(output_dir), "..")
        relative_path = os.path.relpath(nifti_file, derivatives_dir)
        http_url = f"http://localhost:{server_port}/{relative_path}"

        html_content += f"""
            <div class="viewer">
            <div class="viewer-title">{label}</div>
            <div class="file-path">{http_url}</div>
            <canvas id="gl_{subject_id}_{i}" width="640" height="640"></canvas>
        </div>
        """

    html_content += (
        """
        </div>
    
    <div class="controls">
        <div class="slider-container">
            <label for="rotationSlider">Rotate: </label>
            <input type="range" id="rotationSlider" min="0" max="36000" value="0" class="slider">
            <span id="rotationValue">0</span>
        </div>
        <button id="resetView" class="reset-btn">Reset View</button>
    </div>

    <script type="module" async>
        import { Niivue } from "https://unpkg.com/@niivue/niivue@0.57.0/dist/index.js"
        
        const viewers = [];
        const niftiFiles = """
        + json.dumps(
            [
                f"http://localhost:{server_port}/{os.path.relpath(f, os.path.join(os.path.dirname(output_dir), '..'))}"
                for f in filtered_files
            ]
        )
        + """;
        const subjectId = """
        + json.dumps(subject_id)
        + """;
        
        async function setupViewers() {
            for (let i = 0; i < niftiFiles.length; i++) {
                const canvasId = `gl_${subjectId}_${i}`;
                
                // Create Niivue instance
                const nv = new Niivue({ 
                    isResizeCanvas: false,
                    isHighQualityCapable: true,
                    isMultiplanar: false,
                    isRadiological: false
                });
                
                await nv.attachTo(canvasId);
                
                // Configure viewer
                nv.setSliceType(nv.sliceTypeRender);
                nv.dragMode = "none";
                nv.opts.pointerInteraction = false;
                nv.opts.isMouseWheel = false;
                nv.opts.isColorbar = false;
                nv.opts.isResizeCanvas = false;
                nv.opts.isDrag = false;
                
                // Load volume
                try {
                    // Extract file extension from the path
                    const pathParts = niftiFiles[i].split('/');
                    const filename = pathParts[pathParts.length - 1];
                    const fileExt = filename.includes('.nii.gz') ? '.nii.gz' : 
                                   filename.includes('.nii') ? '.nii' : '.nii.gz';
                    
                    await nv.loadVolumes([{ 
                        url: niftiFiles[i],
                        name: `volume_${canvasId}${fileExt}`
                    }]);
                    nv.drawScene();
                    console.log(`Loaded volume for ${canvasId}`);
                } catch (error) {
                    console.error(`Error loading volume for ${canvasId}:`, error);
                }
                
                // Remove event listeners
                const canvasElement = nv.canvas;
                canvasElement.onwheel = null;
                canvasElement.onmousedown = null;
                canvasElement.onmousemove = null;
                canvasElement.onmouseup = null;
                canvasElement.onclick = null;
                canvasElement.ondblclick = null;
                canvasElement.oncontextmenu = null;
                canvasElement.onpointerdown = null;
                canvasElement.onpointermove = null;
                canvasElement.onpointerup = null;
                canvasElement.onpointerleave = null;
                canvasElement.onpointerenter = null;
                canvasElement.onpointercancel = null;
                canvasElement.onmouseenter = null;
                canvasElement.onmouseleave = null;
                canvasElement.onmouseout = null;
                canvasElement.onmouseover = null;
                
                viewers.push(nv);
            }
        }
        
        setupViewers().then(() => {
            // Set up controls
            const slider = document.getElementById('rotationSlider');
            const valueSpan = document.getElementById('rotationValue');
            const resetBtn = document.getElementById('resetView');
            
            slider.addEventListener('input', () => {
                const deg = parseFloat(slider.value);
                valueSpan.textContent = deg;
                const rad = deg * Math.PI / 180;
                viewers.forEach(nv => {
                    nv.scene.renderAzimuth = rad;
                    nv.drawScene();
                });
            });
            
            resetBtn.addEventListener('click', () => {
                slider.value = 0;
                valueSpan.textContent = 0;
                viewers.forEach(nv => {
                    nv.scene.renderAzimuth = 0;
                    nv.scene.renderElevation = 0;
                    nv.scene.volScaleMultiplier = 1;
                    nv.scene.pan2Dxyz = [0.5, 0.5, 0.5];
                    nv.setSliceType(nv.sliceTypeRender);
                    nv.drawScene();
                });
            });
        });
    </script>
</body>
</html>
"""
    )

    # Save the HTML file
    html_path = os.path.join(output_dir, f"{subject_id}_nifti_viewer.html")
    with open(html_path, "w") as f:
        f.write(html_content)

    print(f"Created NIfTI viewer: {html_path}")
    return html_path


def create_simple_viewer_html(svg_files, output_dir):
    """Create simple HTML viewer with all SVG images on one page."""

    # Create HTML content
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    <title>PET Deface SVG Reports</title>
        <style>
        body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #f5f5f5;
        }
        
        .header {
                text-align: center;
                margin-bottom: 30px;
                color: #333;
        }
        
        .svg-grid {
            display: flex;
            flex-direction: column;
            gap: 20px;
            padding: 10px;
        }
        
        .svg-item {
                background: white;
            padding: 10px;
                border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            text-align: center;
            min-height: 90vh;
            display: flex;
            flex-direction: column;
        }
        
        .svg-item h3 {
            margin: 0 0 10px 0;
            color: #2c3e50;
            font-size: 16px;
            word-break: break-all;
        }
        
        .svg-item svg {
            flex: 1;
            max-width: 100%;
            max-height: calc(90vh - 50px);
            width: auto;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
    </style>
    </head>
    <body>
        <div class="header">
        <h1>PET Deface SVG Reports</h1>
        <p>All generated SVG reports</p>
        </div>
        
    <div class="svg-grid">
"""

    # Add all SVG files
    for svg_file in svg_files:
        filename = os.path.basename(svg_file)
        with open(svg_file, "r") as f:
            svg_content = f.read()

        html_content += f"""
        <div class="svg-item">
            <h3>{filename}</h3>
            {svg_content}
        </div>
        """

    html_content += """
        </div>
    </body>
    </html>
    """

    # Write the HTML file
    html_file = os.path.join(output_dir, "svg_reports.html")
    with open(html_file, "w") as f:
        f.write(html_content)

    return html_file


def run_qa(
    defaced_dir,
    output_dir=None,
    open_browser=False,
    start_server=False,
    server_port=8000,
):
    """
    Run QA report generation for SVG reports in derivatives/petdeface.

    Args:
        defaced_dir (str): Path to defaced dataset directory (containing derivatives/petdeface)
        output_dir (str, optional): Output directory for HTML files (defaults to derivatives/petdeface/qa/)
        open_browser (bool): Whether to open browser automatically
        start_server (bool): Whether to start a local HTTP server for NIfTI files
        server_port (int): Port for the HTTP server

    Returns:
        dict: Information about generated files
    """
    defaced_dir = os.path.abspath(defaced_dir)

    # Create output directory in derivatives/petdeface/qa/
    if output_dir:
        output_dir = os.path.abspath(output_dir)
    else:
        # Look for derivatives/petdeface directory
        derivatives_dir = os.path.join(defaced_dir, "derivatives", "petdeface")
        if not os.path.exists(derivatives_dir):
            print(
                f"Warning: derivatives/petdeface directory not found at {derivatives_dir}"
            )
            print("Looking for derivatives directory in parent...")
            # Try parent directory (in case defaced_dir is the derivatives folder)
            derivatives_dir = os.path.join(
                os.path.dirname(defaced_dir), "derivatives", "petdeface"
            )
            if not os.path.exists(derivatives_dir):
                print(
                    f"Warning: derivatives/petdeface directory not found at {derivatives_dir}"
                )
                print("Creating QA output in current directory...")
                output_dir = os.path.abspath("qa_reports")
            else:
                output_dir = os.path.join(derivatives_dir, "qa")
        else:
            output_dir = os.path.join(derivatives_dir, "qa")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Collect SVG reports
    print(f"Collecting SVG reports from {defaced_dir}...")
    svg_files = collect_svg_reports(defaced_dir, output_dir)

    if not svg_files:
        print("No SVG files found to process!")
        return {"output_dir": output_dir, "error": "No SVG files found"}

    # Create HTML viewer for SVG reports
    print("Creating SVG HTML viewer...")
    svg_html_file = create_simple_viewer_html(svg_files, output_dir)

    # Collect and create NIfTI viewers
    print("Collecting NIfTI files...")
    nifti_files_by_subject = collect_nifti_files(defaced_dir)

    nifti_viewer_files = []
    if nifti_files_by_subject:
        print("Creating NIfTI viewers...")
        for subject_id, nifti_files in nifti_files_by_subject.items():
            viewer_file = create_nifti_viewer_html(
                subject_id, nifti_files, output_dir, server_port
            )
            if viewer_file:
                nifti_viewer_files.append(viewer_file)
    else:
        print("No NIfTI files found for viewing")

    # Generate NIfTI viewer links with server detection
    nifti_links = ""
    for viewer_file in nifti_viewer_files:
        viewer_name = Path(viewer_file).name
        subject_id = viewer_name.replace("_nifti_viewer.html", "")
        nifti_links += f'<a href="{viewer_name}" class="link-button nifti-link" data-subject="{subject_id}">{subject_id} NIfTI Viewer</a>\n            '

    # Create simple index
    index_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    <title>PET Deface QA Reports</title>
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
        .content {{
                background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            text-align: center;
            }}
            .link-button {{
                display: inline-block;
            margin: 10px;
            padding: 15px 25px;
                background: #3498db;
                color: white;
                text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
                font-size: 16px;
            }}
            .link-button:hover {{
                background: #2980b9;
            }}
        </style>
    </head>
    <body>
    <div class="header">
        <h1>PET Deface QA Reports</h1>
        <p>Quality assessment reports for defacing workflow</p>
    </div>
    
    <div class="content">
        <h2>Available Reports</h2>
        
        <div style="margin-bottom: 30px;">
            <h3>SVG Reports</h3>
            <p>Click the link below to view all SVG reports:</p>
            <a href="svg_reports.html" class="link-button">View All SVG Reports</a>
            <p style="margin-top: 10px; color: #666;">
                Found {len(svg_files)} SVG report(s)
            </p>
        </div>
        
        <div style="margin-bottom: 30px;">
            <h3>NIfTI Viewers</h3>
            <p>Click the links below to view rotating 3D NIfTI images:</p>
            <div id="nifti-links-container">
                {nifti_links}
            </div>
            <p style="margin-top: 10px; color: #666;">
                Found {len(nifti_viewer_files)} NIfTI viewer(s)
            </p>
            <div id="server-status" style="margin-top: 10px; padding: 10px; border-radius: 5px; display: none;">
                <p id="server-message" style="margin: 0; font-weight: bold;"></p>
                <div id="command-help" style="display: none; margin-top: 15px;">
                    <p style="margin: 10px 0; font-weight: normal;">To start the NIfTI preview server, run this command in your terminal:</p>
                    <div id="command-text" style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; font-family: 'Courier New', monospace; font-size: 12px; text-align: left; word-break: break-all; margin: 10px 0;"></div>
                    <button onclick="copyCommand()" style="background: #28a745; color: white; border: none; padding: 6px 12px; border-radius: 3px; cursor: pointer; font-size: 11px;">Copy Command</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Check if NIfTI server is available
        async function checkServerAvailability() {{
            const serverStatus = document.getElementById('server-status');
            const serverMessage = document.getElementById('server-message');
            const commandHelp = document.getElementById('command-help');
            const commandText = document.getElementById('command-text');
            const niftiLinks = document.querySelectorAll('.nifti-link');
            const serverPort = {server_port};
            const defacedDir = "{defaced_dir}";
            
            try {{
                // Try to fetch a simple request to the server
                const response = await fetch(`http://localhost:${{serverPort}}/`, {{ 
                    method: 'HEAD',
                    mode: 'no-cors'  // This allows us to check if server responds without CORS issues
                }});
                
                // If we get here, server is available
                serverStatus.style.display = 'block';
                serverStatus.style.backgroundColor = '#d4edda';
                serverStatus.style.border = '1px solid #c3e6cb';
                serverMessage.style.color = '#155724';
                serverMessage.textContent = `✓ NIfTI preview server is running on port ${{serverPort}}`;
                
                // Enable all NIfTI links
                niftiLinks.forEach(link => {{
                    link.style.opacity = '1';
                    link.style.pointerEvents = 'auto';
                }});
                
            }} catch (error) {{
                // Server is not available
                serverStatus.style.display = 'block';
                serverStatus.style.backgroundColor = '#f8d7da';
                serverStatus.style.border = '1px solid #f5c6cb';
                serverMessage.style.color = '#721c24';
                serverMessage.textContent = `✗ NIfTI preview server is not running on port ${{serverPort}}. NIfTI viewers will not work.`;
                
                // Show command help
                commandHelp.style.display = 'block';
                const command = `petdeface-qa "${{defacedDir}}" --start-server --open-browser`;
                commandText.textContent = command;
                
                // Disable all NIfTI links
                niftiLinks.forEach(link => {{
                    link.style.opacity = '0.5';
                    link.style.pointerEvents = 'none';
                    link.title = 'NIfTI server not available';
                }});
            }}
        }}
        
        // Copy command to clipboard
        function copyCommand() {{
            const commandText = document.getElementById('command-text');
            navigator.clipboard.writeText(commandText.textContent).then(() => {{
                const button = event.target;
                const originalText = button.textContent;
                button.textContent = 'Copied!';
                button.style.background = '#6c757d';
                setTimeout(() => {{
                    button.textContent = originalText;
                    button.style.background = '#28a745';
                }}, 2000);
            }});
        }}
        
        // Check server availability when page loads
        document.addEventListener('DOMContentLoaded', function() {{
            checkServerAvailability();
        }});
    </script>
    </body>
    </html>
    """

    index_file = os.path.join(output_dir, "petdeface_report.html")
    with open(index_file, "w") as f:
        f.write(index_html)

    print(f"Created main index: {index_file}")
    print(f"Created SVG viewer: {svg_html_file}")
    if nifti_viewer_files:
        print(f"Created {len(nifti_viewer_files)} NIfTI viewer(s)")

    # Open browser if requested
    if open_browser:
        webbrowser.open(f"file://{index_file}")
        print(f"Opened browser to: {index_file}")

    print(f"\nAll files generated in: {output_dir}")
    print(f"Open index.html in your browser to view reports")

    # Start server if requested
    if start_server and nifti_viewer_files:
        print(f"\nStarting HTTP server on port {server_port}...")
        print("This server is needed for NIfTI file access due to CORS restrictions.")
        print("Keep this terminal open while viewing NIfTI files.")

        # Kill any existing process on the port
        kill_process_on_port(server_port)

        # Get the derivatives directory to serve from
        derivatives_dir = os.path.join(os.path.dirname(output_dir), "..")

        print(f"Server is running at http://localhost:{server_port}")
        print("NIfTI viewers will now work properly.")
        print("Press Ctrl+C to stop the server")

        # Start server in foreground (this will block)
        start_local_server(server_port, derivatives_dir)

    return {
        "output_dir": output_dir,
        "index_file": index_file,
        "svg_viewer": svg_html_file,
        "svg_files_count": len(svg_files),
        "nifti_viewers": nifti_viewer_files,
        "nifti_viewers_count": len(nifti_viewer_files),
        "server_started": start_server and nifti_viewer_files,
        "server_port": server_port if start_server and nifti_viewer_files else None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate SVG QA reports for PET deface workflow."
    )
    parser.add_argument(
        "bids_dir",
        help="BIDS directory containing the defaced dataset (with derivatives/petdeface)",
    )
    parser.add_argument(
        "--output-dir",
        "--output_dir",
        help="Output directory for HTML files (default: derivatives/petdeface/qa/)",
    )
    parser.add_argument(
        "--open-browser",
        "--open_browser",
        action="store_true",
        help="Open browser automatically",
    )
    parser.add_argument(
        "--start-server",
        "--start_server",
        action="store_true",
        help="Start local HTTP server for NIfTI file access (required for NIfTI viewers)",
    )
    parser.add_argument(
        "--qa-port",
        "--qa_port",
        type=int,
        default=8000,
        help="User can manually choose a default port to serve the nifti images at for 3D previewing of defacing should the default value of 8000 not work.",
    )

    args = parser.parse_args()

    return run_qa(
        defaced_dir=args.bids_dir,
        output_dir=args.output_dir,
        open_browser=args.open_browser,
        start_server=args.start_server,
        server_port=args.qa_port,
    )


if __name__ == "__main__":
    main()
