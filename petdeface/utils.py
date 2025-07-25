"""Utility functions for the petdeface package."""
from importlib import resources
from pathlib import Path
import subprocess
from pathlib import Path
import json


def get_data_path(filename: str) -> Path:
    """Get the path to a data file included in the package.

    Parameters
    ----------
    filename : str
        Name of the file to get the path for. This should be relative to the data directory.
        For example: "sub-01/ses-baseline/anat/sub-01_ses-baseline_T1w.nii.gz"

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
    return get_data_path("sub-01/ses-baseline/anat/sub-01_ses-baseline_T1w.nii.gz")


class InvalidBIDSDataset(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = errors
        print(f"{message}\n{errors}")


def deno_validator_installed():
    get_help = subprocess.run(
        "bids-validator-deno --help", shell=True, capture_output=True
    )
    if get_help.returncode == 0:
        return True
    else:
        return False


def run_validator(bids_path):
    bids_path = Path(bids_path)
    if bids_path.exists():
        pass
    else:
        raise FileNotFoundError(bids_path)
    if deno_validator_installed():
        command = f"bids-validator-deno {bids_path.resolve()} --ignoreWarnings --json --no-color"
        run_validator = subprocess.run(command, shell=True, capture_output=True)
        json_output = json.loads(run_validator.stdout.decode("utf-8"))
        # since we've ignored warnings any issue in issue is an error
        issues = json_output.get("issues").get("issues")
        formatted_errors = ""
        for issue in issues:
            formatted_errors += "\n" + json.dumps(issue, indent=4)
        if formatted_errors != "":
            raise InvalidBIDSDataset(
                message=f"Dataset at {bids_path} is invalid, see:",
                errors=formatted_errors,
            )

    else:
        raise Exception(
            f"bids-validator-deno not found"
            + "\nskip validation with --skip_bids_validator"
            + "\nor install with pip install bids-validator-deno"
        )
