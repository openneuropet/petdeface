import argparse
import glob
import re
import shutil
import json
import os
import subprocess
import pathlib
import pprint
import nipype.interfaces.freesurfer as fs
import nipype.interfaces.fsl as fsl
from nipype.interfaces.utility import IdentityInterface
from niworkflows.utils.misc import check_valid_fs_license
from nipype.pipeline import Node, MapNode, Workflow
from nipype.interfaces.io import DataSink
from bids import BIDSLayout


def locate_freesurfer_license():
    # collect freesurfer home environment variable
    fs_home = pathlib.Path(os.environ.get("FREESURFER_HOME", ""))
    if not fs_home:
        raise ValueError("FREESURFER_HOME environment variable is not set, unable to determine location of license file")
    else:
        fs_license = fs_home / pathlib.Path("license.txt")
        if not fs_license.exists():
            raise ValueError("Freesurfer license file does not exist at {}".format(fs_license))
        else:
            return fs_license


def check_docker_installed():
    """Checks to see if docker is installed on the system"""
    try:
        subprocess.run(["docker", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        docker_installed = True
    except subprocess.CalledProcessError:
        raise Exception("Could not detect docker installation, exiting")
    return docker_installed


def determine_in_docker():
    """Determines if the script is running in a docker container, returns True if it is, False otherwise"""
    in_docker = False
    # check if /proc/1/cgroup exists
    if pathlib.Path("/proc/1/cgroup").exists():
        with open("/proc/1/cgroup", "rt") as infile:
            lines = infile.readlines()
            for line in lines:
                if "docker" in line:
                    in_docker = True
    if pathlib.Path("/.dockerenv").exists():
        in_docker = True
    if pathlib.Path("/proc/1/sched").exists():
        with open("/proc/1/sched", "rt") as infile:
            lines = infile.readlines()
            for line in lines:
                if "bash" in line:
                    in_docker = True
    return in_docker


def check_docker_image_exists(image_name, build=False):
    """Checks to see if a docker image exists"""
    try:
        subprocess.run(["docker", "inspect", image_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        image_exists = True
        print("Docker image {} exists".format(image_name))
    except subprocess.CalledProcessError:
        image_exists = False
        print("Docker image {} does not exist".format(image_name))

    if build:
        try:
            # get dockerfile path
            dockerfile_path = pathlib.Path(__file__).parent / pathlib.Path("Dockerfile")
            subprocess.run(["docker", "build", "-t", image_name, str(dockerfile_path)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=True)
            image_exists = True
            print("Docker image {} has been built.".format(image_name))
        except subprocess.CalledProcessError:
            image_exists = False
            print("Docker image {} could not be built.".format(image_name))
    return image_exists


class PetDeface:
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

        # create nipype inputs
        self.inputs = Node(IdentityInterface(fields=['anat', 'pet']), name="inputs")

        self.datasink= Node(DataSink(base_directory=str(self.output_dir / pathlib.Path("petdeface")),
                                     container="petdeface"), name="datasink")

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

    @staticmethod
    def convert_to_mgz(self):
        """
        Converts nii.gz images to mgz format
        :return:
        :rtype:
        """
        convert = Node(fs.MRIConvert(out_type="mgz"), name="convert_to_mgz")
        return convert

    @staticmethod
    def register_anat_to_pet(self):
        """
        Performs image registration of anatomical image to pet image using freesurfer's mri_robust_register
        :return:
        :rtype:
        """

        fs.init() # initialize freesurfer
        fs.mri_robust_register()
        pass


def cli():
    parser = argparse.ArgumentParser(description="PetDeface")

    parser.add_argument("input_dir", help="The directory with the input dataset", type=pathlib.Path)
    parser.add_argument("--output_dir", "-o",
                        help="The directory where the output files should be stored", type=pathlib.Path,
                        required=False, default=None)
    parser.add_argument("--anat_only", "-a", action="store_true", default=False, help="Only deface anatomical images")
    parser.add_argument("--subject", "-s", help="The label of the subject to be processed.", type=str, required=False,
                        default="")
    parser.add_argument("--session", "-ses", help="The label of the session to be processed.", type=str, required=False,
                        default="")
    parser.add_argument("--docker", "-d", action="store_true", default=False, help="Run in docker container")
    parser.add_argument("--version", "-v", action="version", version="PetDeface 0.0.1")

    arguments = parser.parse_args()

    return arguments


if __name__ == "__main__":
    # determine present working directory
    pwd = pathlib.Path.cwd()

    # if this script is being run where this file is located assume that the user wants to mount the code folder
    # into the docker container
    if pwd == pathlib.Path(__file__).parent:
        code_dir = str(pathlib.Path(__file__).parent.absolute())
    else:
        code_dir = None

    # check to see if this script is running in a docker container
    running_in_docker = determine_in_docker()

    args = cli()

    if type(args.input_dir) == pathlib.PosixPath and '~' in str(args.input_dir):
        args.input_dir = args.input_dir.expanduser().resolve()
    else:
        args.input_dir = args.input_dir.absolute()
    if type(args.output_dir) == pathlib.PosixPath and '~' in str(args.output_dir):
        args.output_dir = args.output_dir.expanduser().resolve()
    else:
        if not args.output_dir:
            args.output_dir = args.input_dir
        args.output_dir = args.output_dir.absolute()

    if args.docker:
        check_docker_installed()
        check_docker_image_exists('petdeface', build=False)

        input_mount_point = str(args.input_dir)
        output_mount_point = str(args.output_dir)
        args.input_dir = pathlib.Path("/input")
        args.output_dir = pathlib.Path("/output")
        print("Attempting to run in docker container, mounting {} to {} and {} to {}".format(input_mount_point,
                                                                                             args.input_dir,
                                                                                             output_mount_point,
                                                                                             args.output_dir))
        # convert args to dictionary
        args_dict = vars(args)
        for key, value in args_dict.items():
            if type(value) == pathlib.PosixPath:
                args_dict[key] = str(value)

        args_dict.pop("docker")

        args_string = " ".join(["--{} {}".format(key, value) for key, value in args_dict.items() if value])

        # remove --input_dir from args_string
        args_string = args_string.replace("--input_dir", "")

        docker_command = f"docker run --rm " \
                         f"-v {input_mount_point}:{args.input_dir} " \
                         f"-v {output_mount_point}:{args.output_dir} "
        if code_dir:
            docker_command += f"-v {code_dir}:/project/petdeface "

        # collect location of freesurfer license if it's installed and working
        if check_valid_fs_license():
            license_location = locate_freesurfer_license()
            if license_location:
                docker_command += f"-v {license_location}:/usr/local/freesurfer/license.txt "

        # specify platform
        docker_command += f"--platform linux/amd64 "

        docker_command += f"petdeface:latest " \
                          f"python3.9 /project/petdeface/run.py {args_string}"

        print("Running docker command: \n{}".format(docker_command))

        subprocess.run(docker_command, shell=True)

    else:
        petdeface = PetDeface(args.input_dir, args.output_dir, args.anat_only, args.subject, args.session)
