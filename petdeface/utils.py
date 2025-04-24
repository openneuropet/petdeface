"""Utility functions for the petdeface package."""
from importlib import resources
from pathlib import Path
from typing import Union


def get_data_path(filename: str) -> Path:
    """Get the path to a data file included in the package.

    Parameters
    ----------
    filename : str
        Name of the file to get the path for. This should be relative to the data directory.
        For example: "sub-01/ses-baseline/anat/sub-01_ses-baseline_T1w.nii"

    Returns
    -------
    Path
        Path to the requested data file

    Raises
    ------
    FileNotFoundError
        If the requested file is not found in the package data
    """
    try:
        with resources.path("petdeface.data", filename) as path:
            return path
    except Exception as e:
        raise FileNotFoundError(
            f"Could not find data file {filename} in package data"
        ) from e


def get_default_anat() -> Path:
    """Get the path to the default anatomical image.

    Returns
    -------
    Path
        Path to the default T1w image that should be used when no anatomical
        image is available for a PET scan.
    """
    return get_data_path("sub-01/ses-baseline/anat/sub-01_ses-baseline_T1w.nii")
