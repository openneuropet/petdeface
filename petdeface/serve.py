from flask import Flask, render_template, send_from_directory, request, abort
import os
import socket
import argparse
import json
from glob import glob
from pathlib import Path


def create_app(subjects):
    app = Flask(__name__, static_folder="../", template_folder=".")

    @app.route("/")
    def index():
        # Prefix all nifti_paths with /file/ for the new file serving route
        modified_subjects = []
        for subject in subjects:
            modified_subject = subject.copy()
            modified_subject["sessions"] = []
            for session in subject["sessions"]:
                modified_session = session.copy()
                # Convert filesystem path to URL path
                if modified_session["nifti_path"].startswith("/"):
                    # Absolute path - prefix with /file/
                    modified_session["nifti_path"] = (
                        f"/file{modified_session['nifti_path']}"
                    )
                else:
                    # Relative path - keep as is for backward compatibility
                    pass
                modified_subject["sessions"].append(modified_session)
            modified_subjects.append(modified_subject)

        return render_template("niivue.html", subjects=modified_subjects)

    # Serve static files (NIfTI, etc.) from the project root
    @app.route("/<path:filename>")
    def serve_static(filename):
        return send_from_directory(
            __file__,
            filename,
            # os.path.dirname(__file__)
        )

    # New route to serve files from anywhere on the filesystem
    @app.route("/file/<path:filepath>")
    def serve_file(filepath):
        """
        Serve files from anywhere on the local filesystem.
        URL format: http://localhost:8000/file/path/to/file
        Example: http://localhost:8000/file/Users/username/Documents/file.txt
        """
        try:
            # Convert URL path to filesystem path
            # Remove any leading slashes and decode URL encoding
            clean_path = filepath.lstrip("/")

            # Security check: prevent directory traversal attacks
            if ".." in clean_path or clean_path.startswith("/"):
                abort(403, description="Access denied")

            # Convert to absolute path - reconstruct the full path
            # The filepath comes from the URL without the leading slash
            # So we need to add it back to make it an absolute path
            if not clean_path.startswith("/"):
                clean_path = "/" + clean_path

            file_path = Path(clean_path)

            # Additional security: ensure the file exists and is readable
            if not file_path.exists():
                abort(404, description="File not found")

            if not file_path.is_file():
                abort(400, description="Not a file")

            # Serve the file
            return send_from_directory(
                directory=str(file_path.parent),
                path=file_path.name,
                as_attachment=False,
            )

        except Exception as e:
            abort(500, description=f"Error serving file: {str(e)}")

    return app


# Default sample data
sample_subjects = [
    {
        "id": "sub-01",
        "sessions": [
            {
                "label": "Original",
                "nifti_path": "data/sub-01/ses-baseline/anat/sub-01_ses-baseline_T1w.nii",
            },
            {
                "label": "Defaced",
                "nifti_path": "data/sub-01/ses-baseline/anat/sub-01_ses-baseline_T1w.nii",
            },
        ],
    },
    {
        "id": "sub-02",
        "sessions": [
            {
                "label": "Original",
                "nifti_path": "data/sub-02/ses-baseline/anat/sub-02_ses-baseline_T1w.nii",
            },
            {
                "label": "Defaced",
                "nifti_path": "data/sub-02/ses-baseline/anat/sub-02_ses-baseline_T1w.nii",
            },
        ],
    },
]


def build_subjects_from_datasets(original_dir, defaced_dir):
    # Find all NIfTI files in both datasets
    orig_files = glob(os.path.join(original_dir, "**", "*.nii*"), recursive=True)
    defaced_files = glob(os.path.join(defaced_dir, "**", "*.nii*"), recursive=True)

    # Build a mapping from base filename (without extension) to path
    def strip_ext(path):
        base = os.path.basename(path)
        if base.endswith(".gz"):
            base = os.path.splitext(os.path.splitext(base)[0])[0]
        else:
            base = os.path.splitext(base)[0]
        return base

    orig_map = {strip_ext(f): f for f in orig_files}
    defaced_map = {strip_ext(f): f for f in defaced_files}
    # Find intersection of base names
    common_keys = sorted(set(orig_map.keys()) & set(defaced_map.keys()))
    subjects = []
    for key in common_keys:
        # Try to extract subject/session from path (BIDS-like)
        orig_path = orig_map[key]
        defaced_path = defaced_map[key]
        # Try to get subject id from path
        parts = orig_path.split(os.sep)
        sub_id = next((p for p in parts if p.startswith("sub-")), key)
        session = next((p for p in parts if p.startswith("ses-")), "session")
        print(f"defaced_path {defaced_path}")
        print(f"os.path.dirname(__file__) {os.path.dirname(__file__)}")
        print(
            f"os.path.relpath(defaced_path, os.path.dirname(__file__)) {os.path.relpath(defaced_path, os.path.dirname(__file__))}"
        )
        subjects.append(
            {
                "id": sub_id,
                "sessions": [
                    {
                        "label": "Original",
                        "nifti_path": orig_path,  # os.path.relpath(
                        # orig_path, os.path.dirname(__file__)
                        # ),
                    },
                    {
                        "label": "Defaced",
                        "nifti_path": defaced_path,  # os.path.relpath(
                        # defaced_path, os.path.dirname(__file__)
                        # ),
                    },
                ],
            }
        )
    if not subjects:
        print("No matching NIfTI files found in both datasets.")
        exit(1)
    return subjects


def run_server(subjects=None):
    if subjects is None:
        subjects = sample_subjects
    app = create_app(subjects)
    port = 8000
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                s.close()
                break
            except OSError:
                port += 1
    print(f"Serving on http://127.0.0.1:{port}")
    app.run(debug=True, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Serve NiiVue viewer with dynamic subjects."
    )
    parser.add_argument(
        "--subject-list",
        type=str,
        help="Either a path to a JSON file or a JSON string containing the subjects list (mutually exclusive with --original-dataset/--defaced-dataset)",
    )
    parser.add_argument(
        "--original-dataset",
        type=str,
        help="Path to the original dataset directory (must be used with --defaced-dataset)",
    )
    parser.add_argument(
        "--defaced-dataset",
        type=str,
        help="Path to the defaced dataset directory (must be used with --original-dataset)",
    )
    args = parser.parse_args()

    # Mutually exclusive logic
    if (args.original_dataset and not args.defaced_dataset) or (
        args.defaced_dataset and not args.original_dataset
    ):
        print(
            "Error: --original-dataset and --defaced-dataset must be provided together."
        )
        exit(1)
    if args.original_dataset and args.defaced_dataset:
        subjects = build_subjects_from_datasets(
            args.original_dataset, args.defaced_dataset
        )
    elif args.subject_list:
        if os.path.isfile(args.subject_list):
            with open(args.subject_list, "r") as f:
                subjects = json.load(f)
        else:
            try:
                subjects = json.loads(args.subject_list)
            except json.JSONDecodeError as e:
                print(
                    f"Error: --subject-list is not a valid file path or JSON string. {e}"
                )
                exit(1)
    else:
        subjects = sample_subjects

    print(subjects)
    run_server(subjects)
