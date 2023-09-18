import pytest
from pathlib import Path
import shutil
import bids
import tempfile
from petdeface.petdeface import PetDeface

from bids.layout import BIDSLayout

# collect test bids dataset from data directory
data_dir = Path(__file__).parent.parent / 'data'

layout = BIDSLayout(data_dir, validate=True)

if layout:
    pass


def test_anat_in_first_session_folder():

    # create a temporary directory to copy the existing dataset into
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copytree(data_dir, Path(tmpdir) / 'anat_in_first_session_folder')

        # run petdeface on the copied dataset
        petdeface = PetDeface(Path(tmpdir) / 'anat_in_first_session_folder', output_dir=Path(tmpdir) / 'anat_in_first_session_folder_defaced' / 'derivatives' / 'petdeface')
        petdeface.run()