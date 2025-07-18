import pytest
from pathlib import Path
import shutil
import tempfile
import os
import re
import numpy as np
import nibabel as nib
from unittest.mock import patch, MagicMock
from petdeface.noanat import (
    get_data_path,
    get_default_anat,
    get_default_anat_data,
    extract_subject_id,
    copy_default_anat_to_subject,
    remove_default_anat,
)

# Path to the test data directory
project_root = Path(__file__).parent.parent
# data is now at the top level
data_dir = project_root / "data"


@pytest.fixture
def real_nifti_file():
    """Get the path to the real NIfTI file in the data directory."""
    nii_path = (
        data_dir / "sub-01" / "ses-baseline" / "anat" / "sub-01_ses-baseline_T1w.nii.gz"
    )
    assert nii_path.exists(), f"Expected NIfTI file not found at {nii_path}"
    return nii_path


@pytest.fixture
def real_json_file():
    """Get the path to the real JSON file in the data directory."""
    json_path = (
        data_dir / "sub-01" / "ses-baseline" / "anat" / "sub-01_ses-baseline_T1w.json"
    )
    assert json_path.exists(), f"Expected JSON file not found at {json_path}"
    return json_path


@pytest.fixture
def temp_data_dir(real_nifti_file, real_json_file):
    """Create a temporary directory with test data files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the directory structure
        data_dir = Path(tmpdir) / "data"
        anat_dir = data_dir / "sub-01" / "ses-baseline" / "anat"
        anat_dir.mkdir(parents=True)

        # Copy the real NIfTI file
        nii_path = anat_dir / "sub-01_ses-baseline_T1w.nii.gz"
        shutil.copy2(real_nifti_file, nii_path)

        # Copy the real JSON file
        json_path = anat_dir / "sub-01_ses-baseline_T1w.json"
        shutil.copy2(real_json_file, json_path)

        yield data_dir


@pytest.fixture
def mock_get_data_path(temp_data_dir):
    """Patch get_data_path to use the temporary data directory."""

    def mock_get_path(filename):
        path = temp_data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filename}")
        return path

    with patch("petdeface.noanat.get_data_path") as mock:
        mock.side_effect = mock_get_path
        yield mock


@pytest.fixture
def mock_get_default_anat(real_nifti_file):
    """Mock the get_default_anat function."""
    with patch("petdeface.noanat.get_default_anat") as mock:
        mock.return_value = real_nifti_file
        yield mock


@pytest.fixture
def mock_get_default_anat_data(real_nifti_file):
    """Mock the get_default_anat_data function."""
    with patch("petdeface.noanat.get_default_anat_data") as mock:
        mock.return_value = nib.load(real_nifti_file)
        yield mock


def test_get_data_path():
    """Test that get_data_path can find files in the data directory."""
    # Test with a file that exists in the data directory
    path = get_data_path("sub-01/ses-baseline/anat/sub-01_ses-baseline_T1w.nii.gz")
    assert path.exists()
    assert ".nii" in path.suffixes
    assert ".gz" in path.suffixes

    # Test with a file that doesn't exist
    with pytest.raises(FileNotFoundError):
        get_data_path("nonexistent_file.nii")


def test_get_default_anat():
    """Test that get_default_anat returns the correct path."""
    path = get_default_anat(anat="t1")
    assert path.exists()
    assert ".nii" in path.suffixes
    path = get_default_anat(anat="mni")
    assert path.exists()
    assert "mni305" in str(path)


def test_get_default_anat_data():
    """Test that get_default_anat_data returns a nibabel image."""
    img = get_default_anat_data(anat="t1")
    assert img is not None
    assert len(img.shape) == 3


def test_extract_subject_id():
    """Test that extract_subject_id correctly extracts subject IDs from various formats."""
    # Test with full path
    assert extract_subject_id("/path/to/sub-123/anat/file.nii") == "123"

    # Test with subject ID with prefix
    assert extract_subject_id("sub-123") == "123"

    # Test with raw subject ID
    assert extract_subject_id("123") == "123"

    # Test with subject ID followed by underscore
    assert extract_subject_id("sub-123_something") == "123"

    # Test with invalid input
    with pytest.raises(ValueError):
        extract_subject_id("invalid-subject")


def test_copy_default_anat_to_subject():
    """Test that copy_default_anat_to_subject correctly copies files to a subject directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary BIDS dataset
        tmp_bids_dir = Path(tmpdir) / "bids_dataset"
        tmp_bids_dir.mkdir()

        # Create a subject directory
        subject_dir = tmp_bids_dir / "sub-123"
        subject_dir.mkdir()

        # Copy the default anatomical image to the subject directory
        result = copy_default_anat_to_subject(tmp_bids_dir, "sub-123")

        # Check that the result dictionary contains the expected keys
        assert "subject_dir" in result
        assert "anat_dir" in result
        assert "created_dirs" in result
        assert "created_files" in result

        # Check that the subject directory is correct
        assert result["subject_dir"] == subject_dir

        # Check that the anatomical directory was created
        anat_dir = subject_dir / "anat"
        assert result["anat_dir"] == anat_dir
        assert anat_dir.exists()
        assert anat_dir in result["created_dirs"]

        # Check that the files were created
        target_nii = anat_dir / "sub-123_T1w.nii.gz"
        target_json = anat_dir / "sub-123_T1w.json"
        assert target_nii.exists()
        assert target_json.exists()
        assert target_nii in result["created_files"]
        assert target_json in result["created_files"]


def test_copy_default_anat_to_subject_existing_anat_dir():
    """Test that copy_default_anat_to_subject works when the anatomical directory already exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary BIDS dataset
        tmp_bids_dir = Path(tmpdir) / "bids_dataset"
        tmp_bids_dir.mkdir()

        # Create a subject directory and anatomical directory
        subject_dir = tmp_bids_dir / "sub-123"
        subject_dir.mkdir()
        anat_dir = subject_dir / "anat"
        anat_dir.mkdir()

        # Copy the default anatomical image to the subject directory
        result = copy_default_anat_to_subject(tmp_bids_dir, "sub-123")

        # Check that the anatomical directory was not created (it already existed)
        assert anat_dir not in result["created_dirs"]

        # Check that the files were created
        target_nii = anat_dir / "sub-123_T1w.nii.gz"
        target_json = anat_dir / "sub-123_T1w.json"
        assert target_nii.exists()
        assert target_json.exists()
        assert target_nii in result["created_files"]
        assert target_json in result["created_files"]


def test_copy_default_anat_to_subject_nonexistent_subject():
    """Test that copy_default_anat_to_subject raises an error when the subject directory doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary BIDS dataset
        tmp_bids_dir = Path(tmpdir) / "bids_dataset"
        tmp_bids_dir.mkdir()

        # Try to copy the default anatomical image to a nonexistent subject directory
        with pytest.raises(FileNotFoundError):
            copy_default_anat_to_subject(tmp_bids_dir, "sub-123")


def test_remove_default_anat_with_created_items():
    """Test that remove_default_anat correctly removes files and directories when using created_items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary BIDS dataset
        tmp_bids_dir = Path(tmpdir) / "bids_dataset"
        tmp_bids_dir.mkdir()

        # Create a subject directory
        subject_dir = tmp_bids_dir / "sub-123"
        subject_dir.mkdir()

        # Copy the default anatomical image to the subject directory
        created_items = copy_default_anat_to_subject(tmp_bids_dir, "sub-123")

        # Check that the files and directories exist
        anat_dir = subject_dir / "anat"
        target_nii = anat_dir / "sub-123_T1w.nii.gz"
        target_json = anat_dir / "sub-123_T1w.json"
        assert anat_dir.exists()
        assert target_nii.exists()
        assert target_json.exists()

        # Remove the default anatomical image and directory
        remove_default_anat(tmp_bids_dir, created_items=created_items)

        # Check that the files and directories were removed
        assert not target_nii.exists()
        assert not target_json.exists()
        assert not anat_dir.exists()


def test_remove_default_anat_with_subject_id():
    """Test that remove_default_anat correctly removes files and directories when using subject_id."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary BIDS dataset
        tmp_bids_dir = Path(tmpdir) / "bids_dataset"
        tmp_bids_dir.mkdir()

        # Create a subject directory
        subject_dir = tmp_bids_dir / "sub-123"
        subject_dir.mkdir()

        # Copy the default anatomical image to the subject directory
        copy_default_anat_to_subject(tmp_bids_dir, "sub-123")

        # Check that the files and directories exist
        anat_dir = subject_dir / "anat"
        target_nii = anat_dir / "sub-123_T1w.nii.gz"
        target_json = anat_dir / "sub-123_T1w.json"
        assert anat_dir.exists()
        assert target_nii.exists()
        assert target_json.exists()

        # Remove the default anatomical image and directory
        remove_default_anat(tmp_bids_dir, subject_id="sub-123")

        # Check that the files and directories were removed
        assert not target_nii.exists()
        assert not target_json.exists()
        assert not anat_dir.exists()


def test_remove_default_anat_nonexistent_files():
    """Test that remove_default_anat handles nonexistent files gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary BIDS dataset
        tmp_bids_dir = Path(tmpdir) / "bids_dataset"
        tmp_bids_dir.mkdir()

        # Create a subject directory
        subject_dir = tmp_bids_dir / "sub-123"
        subject_dir.mkdir()

        # Create a dictionary with nonexistent files and directories
        created_items = {
            "subject_dir": subject_dir,
            "anat_dir": subject_dir / "anat",
            "created_dirs": [subject_dir / "anat"],
            "created_files": [
                subject_dir / "anat" / "sub-123_T1w.nii.gz",
                subject_dir / "anat" / "sub-123_T1w.json",
            ],
        }

        # Remove the default anatomical image and directory
        remove_default_anat(tmp_bids_dir, created_items=created_items)

        # Check that the function didn't raise an error


def test_remove_default_anat_invalid_input():
    """Test that remove_default_anat raises an error with invalid input."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary BIDS dataset
        tmp_bids_dir = Path(tmpdir) / "bids_dataset"
        tmp_bids_dir.mkdir()

        # Try to remove the default anatomical image with both subject_id and created_items
        with pytest.raises(ValueError):
            remove_default_anat(tmp_bids_dir, subject_id="sub-123", created_items={})

        # Try to remove the default anatomical image with neither subject_id nor created_items
        with pytest.raises(ValueError):
            remove_default_anat(tmp_bids_dir)

        # Try to remove the default anatomical image with a nonexistent BIDS directory
        with pytest.raises(FileNotFoundError):
            remove_default_anat(Path(tmpdir) / "nonexistent", subject_id="sub-123")

        # Try to remove the default anatomical image with a nonexistent subject directory
        with pytest.raises(FileNotFoundError):
            remove_default_anat(tmp_bids_dir, subject_id="sub-123")


def test_remove_default_anat_nonempty_directory():
    """Test that remove_default_anat doesn't remove a nonempty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a temporary BIDS dataset
        tmp_bids_dir = Path(tmpdir) / "bids_dataset"
        tmp_bids_dir.mkdir()

        # Create a subject directory
        subject_dir = tmp_bids_dir / "sub-123"
        subject_dir.mkdir()

        # Copy the default anatomical image to the subject directory
        created_items = copy_default_anat_to_subject(tmp_bids_dir, "sub-123")

        # Add an extra file to the anatomical directory
        anat_dir = subject_dir / "anat"
        extra_file = anat_dir / "extra_file.txt"
        extra_file.write_text("This is an extra file")

        # Remove the default anatomical image and directory
        remove_default_anat(tmp_bids_dir, created_items=created_items)

        # Check that the files were removed but the directory still exists
        assert not (anat_dir / "sub-123_T1w.nii.gz").exists()
        assert not (anat_dir / "sub-123_T1w.json").exists()
        assert anat_dir.exists()
        assert extra_file.exists()
