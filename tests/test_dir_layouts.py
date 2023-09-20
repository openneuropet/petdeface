import pytest
from pathlib import Path
import shutil
import bids
import tempfile
from petdeface.petdeface import PetDeface
from os import cpu_count
from bids.layout import BIDSLayout

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
        )
        petdeface.run()
