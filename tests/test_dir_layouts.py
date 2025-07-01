import pytest
from pathlib import Path
import shutil
import bids
from petdeface.petdeface import PetDeface
from petdeface.utils import InvalidBIDSDataset
from os import cpu_count
from bids.layout import BIDSLayout
import subprocess

import tempfile

# collect test bids dataset from data directory
data_dir = Path(__file__).parent.parent / "data"

# get number of cores, use all but one
nthreads = cpu_count() - 1

layout = BIDSLayout(data_dir, validate=True)

if layout:
    pass


def test_anat_in_first_session_folder():
    # create a temporary directory to copy the existing dataset into
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copytree(data_dir, Path(tmpdir) / "anat_in_first_session_folder")

        # run petdeface on the copied dataset
        petdeface = PetDeface(
            Path(tmpdir) / "anat_in_first_session_folder",
            output_dir=Path(tmpdir)
            / "anat_in_first_session_folder_defaced"
            / "derivatives"
            / "petdeface",
            n_procs=nthreads,
            preview_pics=False,
        )
        petdeface.run()


def test_anat_in_each_session_folder():
    # create a temporary directory to copy the existing dataset into
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copytree(data_dir, Path(tmpdir) / "anat_in_each_session_folder")

        # create a second session
        second_session_folder = (
            Path(tmpdir) / "anat_in_each_session_folder" / "sub-01" / "ses-second"
        )
        second_session_folder.mkdir(parents=True, exist_ok=True)

        shutil.copytree(
            Path(tmpdir) / "anat_in_each_session_folder" / "sub-01" / "ses-baseline",
            second_session_folder,
            dirs_exist_ok=True,
        )

        # replace the ses- entities in the files in the newly created second session folder
        for file in second_session_folder.glob("pet/*"):
            shutil.move(
                file,
                second_session_folder
                / "pet"
                / file.name.replace("ses-baseline_", "ses-second_"),
            )

        for file in second_session_folder.glob("anat/*"):
            shutil.move(
                file,
                second_session_folder
                / "anat"
                / file.name.replace("ses-baseline_", "ses-second_"),
            )

        # run petdeface on the copied dataset
        petdeface = PetDeface(
            Path(tmpdir) / "anat_in_each_session_folder",
            output_dir=Path(tmpdir)
            / "anat_in_each_session_folder_defaced"
            / "derivatives"
            / "petdeface",
            n_procs=nthreads,
            preview_pics=False,
        )
        petdeface.run()


def test_anat_in_subject_folder():
    # create a temporary directory to copy the existing dataset into
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copytree(data_dir, Path(tmpdir) / "anat_in_subject_folder")

        original_anat_folder = (
            Path(tmpdir) / "anat_in_subject_folder" / "sub-01" / "ses-baseline" / "anat"
        )
        subject_folder = Path(tmpdir) / "anat_in_subject_folder" / "sub-01"
        # now we move the anatomical folder in the first session of our test data into the subject level folder
        shutil.move(original_anat_folder, subject_folder)

        # and next remove the ses- entities from the files in the newly created anat folder
        for file in Path(tmpdir).glob(
            "anat_in_subject_folder/sub-01/anat/sub-01_ses-baseline_*"
        ):
            shutil.move(
                file,
                Path(tmpdir)
                / "anat_in_subject_folder"
                / "sub-01"
                / "anat"
                / file.name.replace("ses-baseline_", ""),
            )

        # run petdeface on the copied dataset
        petdeface = PetDeface(
            Path(tmpdir) / "anat_in_subject_folder",
            output_dir=Path(tmpdir)
            / "anat_in_subject_folder_defaced"
            / "derivatives"
            / "petdeface",
            n_procs=nthreads,
            preview_pics=False,
        )
        petdeface.run()


def test_participant_exclusion():
    """Test that participant exclusion works correctly by excluding sub-02"""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        
        # Create the test directory and copy our data
        shutil.copytree(data_dir, test_dir / "participant_exclusion")

        # run petdeface on the copied dataset, excluding sub-02
        petdeface = PetDeface(
            test_dir / "participant_exclusion",
            n_procs=nthreads,
            preview_pics=False,
            placement="adjacent",
            participant_label_exclude=["sub-02"],  # Exclude sub-02
        )
        petdeface.run()

        # Check the final defaced dataset directory
        final_defaced_dir = test_dir / "participant_exclusion_defaced"
        
        # Count files in the final defaced dataset
        all_files = list(final_defaced_dir.rglob("*"))
        all_files = [f for f in all_files if f.is_file()]  # Only files, not directories
        
        # Count files by subject
        sub01_files = [f for f in all_files if "sub-01" in str(f)]
        sub02_files = [f for f in all_files if "sub-02" in str(f)]
        
        print(f"Total files in defaced dataset: {len(all_files)}")
        print(f"sub-01 files: {len(sub01_files)}")
        print(f"sub-02 files: {len(sub02_files)}")
        
        # Verify that sub-02 does NOT appear anywhere in the final defaced dataset
        assert len(sub02_files) == 0, f"sub-02 should be completely excluded from final defaced dataset, but found {len(sub02_files)} files: {[str(f) for f in sub02_files]}"
        
        # Verify that sub-01 exists and was processed
        assert len(sub01_files) > 0, "sub-01 should exist in final defaced dataset"
        assert (final_defaced_dir / "sub-01").exists(), "sub-01 directory should exist in final defaced dataset"
        
        # Verify processing artifacts exist for sub-01 in derivatives
        derivatives_dir = final_defaced_dir / "derivatives" / "petdeface"
        if derivatives_dir.exists():
            sub01_defacemasks = list(derivatives_dir.glob("**/sub-01*defacemask*"))
            sub01_lta_files = list(derivatives_dir.glob("**/sub-01*.lta"))
            
            print(f"sub-01 defacemasks found: {len(sub01_defacemasks)}")
            print(f"sub-01 lta files found: {len(sub01_lta_files)}")
            
            assert len(sub01_defacemasks) > 0, "sub-01 should have been processed and have defacemasks"
            assert len(sub01_lta_files) > 0, "sub-01 should have been processed and have lta registration files"


def test_no_anat():
    # create a temporary directory to copy the existing dataset into
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copytree(data_dir, Path(tmpdir) / "no_anat")

        subject_folder = Path(tmpdir) / "no_anat" / "sub-01"
        # next we delete the anat fold in the subject folder
        shutil.rmtree(subject_folder / "ses-baseline" / "anat")

        # run petdeface on the copied dataset
        petdeface = PetDeface(
            Path(tmpdir) / "no_anat",
            output_dir=Path(tmpdir) / "no_anat_defaced" / "derivatives" / "petdeface",
            n_procs=nthreads,
        )

        # now we want to assert that this pipeline crashes and print the error
        with pytest.raises(FileNotFoundError) as exc_info:
            petdeface.run()


def test_invalid_bids():
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copytree(data_dir, Path(tmpdir) / "invalid")
        # rename the files in the pet folder to a different subject id
        subject_folder = Path(tmpdir) / "invalid" / "sub-01"
        pet_folder = subject_folder / "ses-baseline" / "pet"
        for file in pet_folder.glob("sub-01_*"):
            shutil.move(
                file, pet_folder / file.name.replace("sub-01", "sub-01-bestsubject")
            )

        # run petdeface on the invalid dataset
        petdeface = PetDeface(
            Path(tmpdir) / "invalid",
            output_dir=Path(tmpdir) / "invalid_defaced" / "derivatives" / "petdeface",
            n_procs=nthreads,
        )

        # Run it and see what error gets raised
        with pytest.raises(InvalidBIDSDataset) as exc_info:
            petdeface.run()
        assert "Dataset at" in str(exc_info.value)
