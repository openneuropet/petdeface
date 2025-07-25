#!/usr/bin/env python3
"""
Simple QA system for PET deface SVG reports.
"""

import os
import glob
import argparse
import webbrowser
from pathlib import Path


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


def run_qa(defaced_dir, output_dir=None, open_browser=False):
    """
    Run QA report generation for SVG reports in derivatives/petdeface.

    Args:
        defaced_dir (str): Path to defaced dataset directory (containing derivatives/petdeface)
        output_dir (str, optional): Output directory for HTML files (defaults to derivatives/petdeface/qa/)
        open_browser (bool): Whether to open browser automatically

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

    # Create HTML viewer
    print("Creating HTML viewer...")
    html_file = create_simple_viewer_html(svg_files, output_dir)

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
        <p>Click the link below to view all SVG reports:</p>
        
        <a href="svg_reports.html" class="link-button">View All SVG Reports</a>
        
        <p style="margin-top: 20px; color: #666;">
            Found {len(svg_files)} SVG report(s)
        </p>
    </div>
</body>
</html>
"""

    index_file = os.path.join(output_dir, "index.html")
    with open(index_file, "w") as f:
        f.write(index_html)

    print(f"Created main index: {index_file}")
    print(f"Created SVG viewer: {html_file}")

    # Open browser if requested
    if open_browser:
        webbrowser.open(f"file://{index_file}")
        print(f"Opened browser to: {index_file}")

    print(f"\nAll files generated in: {output_dir}")
    print(f"Open index.html in your browser to view reports")

    return {
        "output_dir": output_dir,
        "index_file": index_file,
        "svg_viewer": html_file,
        "svg_files_count": len(svg_files),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate SVG QA reports for PET deface workflow."
    )
    parser.add_argument(
        "--defaced-dir",
        required=True,
        help="Directory for defaced dataset (containing derivatives/petdeface)",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for HTML files (default: {dataset_name}_svg_qa)",
    )
    parser.add_argument(
        "--open-browser", action="store_true", help="Open browser automatically"
    )

    args = parser.parse_args()

    return run_qa(
        defaced_dir=args.defaced_dir,
        output_dir=args.output_dir,
        open_browser=args.open_browser,
    )


if __name__ == "__main__":
    main()
