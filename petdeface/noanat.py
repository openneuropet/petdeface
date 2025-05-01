"""Functionality for handling cases where anatomical images are not available."""
import nibabel
import numpy
import shutil
import os
import re
import tempfile
from pathlib import Path
from typing import Union, Dict, Optional


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
    # Get the path to the data directory
    data_dir = Path(__file__).parent.parent / "data"

    # Construct the full path
    full_path = data_dir / filename

    # Check if the file exists
    if not full_path.exists():
        raise FileNotFoundError(
            f"Could not find data file {filename} in data directory"
        )

    return full_path


def get_default_anat(anat) -> Path:
    """Get the path to the default anatomical image.

    Returns
    -------
    Path
        Path to the default T1w image that should be used when no anatomical
        image is available for a PET scan.
    """
    if anat == "t1":
        return get_data_path("sub-01/ses-baseline/anat/sub-01_ses-baseline_T1w.nii.gz")
    elif anat == "mni":
        return get_data_path("sub-mni305/anat/sub-mni305_T1w.nii.gz")
    elif anat == "pet":
        return tempfile.TemporaryDirectory()
    else:
        raise Exception(
            f"Choice of file for template anat must be one of: t1, mni, or pet. given: {anat}"
        )


def get_default_anat_data(anat) -> nibabel.Nifti1Image:
    """Get the default anatomical image as a nibabel image object.

    Returns
    -------
    nibabel.Nifti1Image
        The default T1w image loaded as a nibabel image object
    """
    return nibabel.load(get_default_anat(anat))


def extract_subject_id(input_str: str) -> str:
    """Extract subject ID from various input formats.

    This function can handle:
    - Full paths (e.g., "/path/to/sub-123/anat/file.nii")
    - Subject IDs with prefix (e.g., "sub-123")
    - Raw subject IDs (e.g., "123")

    Parameters
    ----------
    input_str : str
        Input string containing a subject ID in any format

    Returns
    -------
    str
        Extracted subject ID without the 'sub-' prefix

    Raises
    ------
    ValueError
        If no valid subject ID can be extracted
    """
    # Pattern to match 'sub-XXXX' in various contexts
    # The pattern captures everything after 'sub-' until it hits a non-alphanumeric character or the end of the string
    pattern = r"sub-([a-zA-Z0-9]+)(?:_|$)"

    # Try to find a match
    match = re.search(pattern, input_str)

    if match:
        # Return the captured group (the subject ID without 'sub-' prefix)
        return match.group(1)
    else:
        # If no 'sub-' prefix is found, check if the input is a valid subject ID
        if re.match(r"^[a-zA-Z0-9]+$", input_str):
            return input_str
        else:
            # Try a more flexible approach for paths
            path_match = re.search(r"sub-([a-zA-Z0-9]+)", input_str)
            if path_match:
                return path_match.group(1)
            else:
                raise ValueError(
                    f"Could not extract a valid subject ID from '{input_str}'"
                )


def copy_default_anat_to_subject(
    bids_dir: Union[str, Path],
    subject_id: str,
    pet_image=Union[str, Path],
    default_anat="t1",
) -> dict:
    """Copy the default anatomical image to a PET subject's folder in a BIDS dataset.

    This function extracts the subject ID from the provided string using regex,
    then copies the default anatomical image and its JSON metadata to the subject's folder in the BIDS dataset.

    Parameters
    ----------
    bids_dir : Union[str, Path]
        Path to the BIDS dataset
    subject_id : str
        Subject ID in any format:
        - Full path (e.g., "/path/to/sub-123/anat/file.nii")
        - Subject ID with prefix (e.g., "sub-123")
        - Raw subject ID (e.g., "123")
    pet_image: Union[str, Path]
        Path to the pet image that is lacking an anatomical
    default_anat : str
        The anat file to use as a 'default' can be a the t1w, mni, or averaged PET image
        defaults to the t1w included in this library.

    Returns
    -------
    dict
        A dictionary containing information about the created files and directories:
        {
            'subject_dir': Path to the subject directory,
            'anat_dir': Path to the anatomical directory,
            'created_dirs': List of paths to newly created directories,
            'created_files': List of paths to newly created files
        }

    Raises
    ------
    FileNotFoundError
        If the BIDS directory or subject directory does not exist
    ValueError
        If the subject ID is invalid or cannot be extracted
    """
    # Convert bids_dir to Path if it's a string
    bids_dir = Path(bids_dir)

    # Check if the BIDS directory exists
    if not bids_dir.exists():
        raise FileNotFoundError(f"BIDS directory {bids_dir} does not exist")

    # Extract subject ID using regex
    try:
        extracted_id = extract_subject_id(subject_id)
    except ValueError as e:
        raise ValueError(f"Invalid subject ID: {e}")

    # Create the subject directory structure
    subject_dir = bids_dir / f"sub-{extracted_id}"

    # Check if the subject directory exists
    if not subject_dir.exists():
        raise FileNotFoundError(f"Subject directory {subject_dir} does not exist")

    anat_dir = subject_dir / "anat"

    # Create the anatomical directory if it doesn't exist
    created_dirs = []
    if not anat_dir.exists():
        anat_dir.mkdir(parents=True, exist_ok=True)
        created_dirs.append(anat_dir)

    # Define the target file paths
    target_nii = anat_dir / f"sub-{extracted_id}_T1w.nii.gz"
    target_json = anat_dir / f"sub-{extracted_id}_T1w.json"

    # Get the source file paths
    source_nii = get_default_anat(anat=default_anat)
    if type(source_nii) is tempfile.TemporaryDirectory:
        # load the pet image for that subject
        input_image = nibabel.load(pet_image)
        # average the pet file
        average = numpy.mean(input_image.dataobj, axis=3)
        # save the average to the source nifti path, in this case a temp file
        with source_nii as tmpdirname:
            save_path = os.path.join(
                tmpdirname, f"sub-{extracted_id}_desc-totallyat1w.nii.gz"
            )
            nibabel.save(nibabel.Nifti1Image(average, input_image.affine), save_path)
            shutil.copy2(save_path, target_nii)
    else:
        shutil.copy2(source_nii, target_nii)

    source_json = get_data_path("sub-01/ses-baseline/anat/sub-01_ses-baseline_T1w.json")
    created_files = []
    created_files.append(target_nii)

    shutil.copy2(source_json, target_json)
    created_files.append(target_json)

    print(f"Copied {default_anat} anatomical image to {target_nii}")
    print(f"Copied {default_anat} anatomical metadata to {target_json}")

    # Return information about created files and directories
    return {
        "subject_dir": subject_dir,
        "anat_dir": anat_dir,
        "created_dirs": created_dirs,
        "created_files": created_files,
    }


def remove_default_anat(
    bids_dir: Union[str, Path],
    subject_id: Optional[str] = None,
    created_items: Optional[Dict] = None,
) -> None:
    """Remove the default anatomical image and directory created for a subject.

    This function can be used in two ways:
    1. With the bids_dir and subject_id to identify what to remove
    2. With the bids_dir and the dictionary returned by copy_default_anat_to_subject

    Parameters
    ----------
    bids_dir : Union[str, Path]
        Path to the BIDS dataset
    subject_id : Optional[str]
        Subject ID in any format (if created_items is not provided)
    created_items : Optional[Dict]
        Dictionary returned by copy_default_anat_to_subject (if subject_id is not provided)

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If neither subject_id nor created_items is provided, or if both are provided
    FileNotFoundError
        If the BIDS directory or subject directory does not exist
    """
    # Convert bids_dir to Path if it's a string
    bids_dir = Path(bids_dir)

    # Check if the BIDS directory exists
    if not bids_dir.exists():
        raise FileNotFoundError(f"BIDS directory {bids_dir} does not exist")

    # Determine which approach to use
    if subject_id is not None and created_items is not None:
        raise ValueError("Cannot provide both subject_id and created_items")
    elif subject_id is None and created_items is None:
        raise ValueError("Must provide either subject_id or created_items")

    if created_items is not None:
        # Use the dictionary returned by copy_default_anat_to_subject
        anat_dir = created_items["anat_dir"]
        created_files = created_items["created_files"]
        created_dirs = created_items["created_dirs"]
    else:
        # Extract subject ID using regex
        try:
            extracted_id = extract_subject_id(subject_id)
        except ValueError as e:
            raise ValueError(f"Invalid subject ID: {e}")

        # Create the subject directory structure
        subject_dir = bids_dir / f"sub-{extracted_id}"

        # Check if the subject directory exists
        if not subject_dir.exists():
            raise FileNotFoundError(f"Subject directory {subject_dir} does not exist")

        anat_dir = subject_dir / "anat"

        # Define the file paths
        target_nii = anat_dir / f"sub-{extracted_id}_T1w.nii"
        target_json = anat_dir / f"sub-{extracted_id}_T1w.json"

        # Check if the files exist
        created_files = []
        if target_nii.exists():
            created_files.append(target_nii)
        if target_json.exists():
            created_files.append(target_json)

        # Check if the directory exists and is empty
        created_dirs = []
        if anat_dir.exists():
            # Only add to created_dirs if it's empty or only contains our files
            remaining_files = set(anat_dir.iterdir()) - set(created_files)
            if not remaining_files:
                created_dirs.append(anat_dir)

    # Remove the files
    for file_path in created_files:
        if file_path.exists():
            file_path.unlink()
            print(f"Removed file: {file_path}")

    # Remove the directories (only if they're empty)
    for dir_path in created_dirs:
        if dir_path.exists() and not any(dir_path.iterdir()):
            dir_path.rmdir()
            print(f"Removed directory: {dir_path}")

    print("Cleanup completed successfully")
