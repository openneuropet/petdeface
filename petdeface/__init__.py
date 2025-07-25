"""
PET Deface - A nipype PET and MR defacing pipeline for BIDS datasets.

This package provides tools for defacing PET and MR images using FreeSurfer's MiDeFace.
"""

import sys
from pathlib import Path

# Add the package directory to sys.path when running as script
if __name__ == "__main__" or (
    len(sys.argv) > 0 and sys.argv[0].endswith("petdeface.py")
):
    # Running as script - add current directory to path
    package_dir = Path(__file__).parent
    if str(package_dir) not in sys.path:
        sys.path.insert(0, str(package_dir))

# Import main components
try:
    from .petdeface import PetDeface, deface, cli, main
    from .mideface import ApplyMideface, Mideface
    from .pet import WeightedAverage
    from .qa import run_qa
    from .utils import run_validator
    from .noanat import copy_default_anat_to_subject, remove_default_anat
except ImportError:
    # Fallback for when running as script
    try:
        from petdeface import PetDeface, deface, cli, main
        from mideface import ApplyMideface, Mideface
        from pet import WeightedAverage
        from qa import run_qa
        from utils import run_validator
        from noanat import copy_default_anat_to_subject, remove_default_anat
    except ImportError:
        # Last resort - import from current directory
        import os

        sys.path.insert(0, os.path.dirname(__file__))
        from petdeface import PetDeface, deface, cli, main
        from mideface import ApplyMideface, Mideface
        from pet import WeightedAverage
        from qa import run_qa
        from utils import run_validator
        from noanat import copy_default_anat_to_subject, remove_default_anat

# Version info
try:
    from importlib.metadata import version

    __version__ = version("petdeface")
except ImportError:
    __version__ = "unknown"

__bids_version__ = "1.8.0"

# Main exports
__all__ = [
    "PetDeface",
    "deface",
    "cli",
    "main",
    "ApplyMideface",
    "Mideface",
    "WeightedAverage",
    "run_qa",
    "run_validator",
    "copy_default_anat_to_subject",
    "remove_default_anat",
    "__version__",
    "__bids_version__",
]
