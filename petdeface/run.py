import argparse
import glob
import re
import shutil
import json
import pathlib
import pprint
import nipype.interfaces.freesurfer as fs
import nipype.interfaces.fsl as fsl

from niworkflows.utils.misc import check_valid_fs_license
from nipype.pipeline import Node, MapNode, Workflow
from bids import BIDSLayout


class PetDeface():
    def __init__(self, bids_dir, output_dir=None, anat_only=False, subject="", session=""):
        self.bids_dir = bids_dir
        if not output_dir:
            self.output_dir = self.bids_dir
        else:
            self.output_dir = output_dir
        self.subject = subject
        self.session = session

        # check if freesurfer license is valid
        self.fs_license = check_valid_fs_license()
        if not self.fs_license:
            raise ValueError("Freesurfer license is not valid")

        # create map of subjects in bids_dir
        self.subjects = {}
        for s in self.collect_subjects():
            self.subjects[s] = {'anat': [], 'pet': []}

        # collect pet and anat files
        self.collect_anat()
        self.collect_pet()

        # print subjects
        print("Subjects in BIDS directory: \n{}".format(pprint.pformat(self.subjects)))

    def collect_anat(self):
        layout = BIDSLayout(self.bids_dir)
        for subject in self.subjects:
            anat_files = layout.get(subject=subject,
                                    extension=[".nii", ".nii.gz"],
                                    suffix="T1w", return_type="file")
            self.subjects[subject]['anat'] = anat_files

    def collect_pet(self):
        layout = BIDSLayout(self.bids_dir)
        for subject in self.subjects:
            pet_files = layout.get(subject=subject,
                                   extension=[".nii", ".nii.gz"],
                                   suffix="pet", return_type="file")
            self.subjects[subject]['pet'] = pet_files

    def collect_subjects(self):
        layout = BIDSLayout(self.bids_dir)
        subjects = layout.get_subjects()
        return subjects


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PetDeface")
    parser.add_argument("bids_dir", help="The directory with the input dataset", type=pathlib.Path)
    parser.add_argument("--output_dir", "-o",
                        help="The directory where the output files should be stored", type=pathlib.Path,
                        required=False, default=None)
    parser.add_argument("--anat_only", "-a", action="store_true", default=False, help="Only deface anatomical images")
    parser.add_argument("--subject", "-s", help="The label of the subject to be processed.", type=str, required=False,
                        default="")
    parser.add_argument("--session", "-ses", help="The label of the session to be processed.", type=str, required=False,
                        default="")

    args = parser.parse_args()

    petdeface = PetDeface(args.bids_dir, args.output_dir, args.anat_only, args.subject, args.session)