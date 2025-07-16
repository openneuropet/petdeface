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
            output_dir=Path(tmpdir)
            / "no_anat_defaced"
            / "derivatives"
            / "petdeface",
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
                file,
                pet_folder / file.name.replace("sub-01", "sub-01-bestsubject")
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
        