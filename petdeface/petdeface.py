import argparse
import json
import os
import pathlib
import re

# import shutil
import subprocess
from typing import Union

from nipype.interfaces.freesurfer import MRICoreg
from nipype.interfaces.io import DataSink
from nipype.pipeline import Node
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.utils.bids import collect_data
from niworkflows.utils.bids import collect_participants
from niworkflows.utils.misc import check_valid_fs_license


try:
    from mideface import ApplyMideface
    from mideface import Mideface
    from pet import WeightedAverage
except ModuleNotFoundError:
    from .mideface import ApplyMideface
    from .mideface import Mideface
    from .pet import WeightedAverage


# collect version from pyproject.toml
places_to_look = [
    pathlib.Path(__file__).parent.absolute(),
    pathlib.Path(__file__).parent.parent.absolute(),
]

__version__ = "unable to locate version number in pyproject.toml"
# we use the default version at the time of this writing, but the most current version
# can be found in the pyproject.toml file under the [tool.bids] section
__bids_version__ = "1.8.0"


# search for toml file
for place in places_to_look:
    for root, folders, files in os.walk(place):
        for file in files:
            if file.endswith("pyproject.toml"):
                toml_file = os.path.join(root, file)

                with open(toml_file, "r") as f:
                    for line in f.readlines():
                        if (
                            "version" in line
                            and len(line.split("=")) > 1
                            and "bids_version" not in line
                        ):
                            __version__ = line.split("=")[1].strip().replace('"', "")
                        if "bids_version" in line and len(line.split("=")) > 1:
                            __bids_version__ = (
                                line.split("=")[1].strip().replace('"', "")
                            )
                break


def locate_freesurfer_license():
    # collect freesurfer home environment variable
    fs_home = pathlib.Path(os.environ.get("FREESURFER_HOME", ""))
    if not fs_home:
        raise ValueError(
            "FREESURFER_HOME environment variable is not set, unable to determine location of license file"
        )
    else:
        fs_license = fs_home / pathlib.Path("license.txt")
        if not fs_license.exists():
            raise ValueError(
                "Freesurfer license file does not exist at {}".format(fs_license)
            )
        else:
            return fs_license


def check_docker_installed():
    """Checks to see if docker is installed on the system"""
    try:
        subprocess.run(
            ["docker", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
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
        subprocess.run(
            ["docker", "inspect", image_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        image_exists = True
        print("Docker image {} exists".format(image_name))
    except subprocess.CalledProcessError:
        image_exists = False
        print("Docker image {} does not exist".format(image_name))

    if build:
        try:
            # get dockerfile path
            dockerfile_path = pathlib.Path(__file__).parent / pathlib.Path("Dockerfile")
            subprocess.run(
                ["docker", "build", "-t", image_name, str(dockerfile_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            image_exists = True
            print("Docker image {} has been built.".format(image_name))
        except subprocess.CalledProcessError:
            image_exists = False
            print("Docker image {} could not be built.".format(image_name))
    return image_exists


def deface(args: Union[dict, argparse.Namespace]) -> None:
    """Main function for the PET Deface workflow."""

    if type(args) is dict:
        args = argparse.Namespace(**args)
    else:
        args = args

    if not check_valid_fs_license():
        raise Exception("You need a valid FreeSurfer license to proceed!")

    if args.participant_label:
        participants = [args.participant_label]
    else:
        participants = collect_participants(
            args.bids_dir, bids_validate=~args.skip_bids_validator
        )

    # clean up and create derivatives directories
    if args.output_dir is None:
        output_dir = os.path.join(args.bids_dir, "derivatives", "petdeface")
    else:
        output_dir = args.output_dir

    petdeface_wf = Workflow(name="petdeface_wf", base_dir=output_dir)

    for subject_id in participants:
        single_subject_wf = init_single_subject_wf(subject_id, args.bids_dir)
        petdeface_wf.add_nodes([single_subject_wf])

    try:
        petdeface_wf.write_graph("petdeface.dot", graph2use="colored", simple_form=True)
    except OSError as Err:
        print(f"Raised this error {Err}\nGraphviz may not be installed.")
    petdeface_wf.run(plugin="MultiProc", plugin_args={"n_procs": int(args.n_procs)})

    # write out dataset_description.json file to derivatives directory
    write_out_dataset_description_json(args.bids_dir)

    # remove temp outputs - this is commented out to enable easier testing for now
    # shutil.rmtree(os.path.join(output_dir, "petdeface_wf"))


def count_matching_chars(a: str, b: str) -> int:
    """Count the number of matching characters up to first discrepancy."""
    n = min(len(a), len(b))
    result = 0
    for i in range(n):
        if a[i] == b[i]:
            result += 1
        else:
            return result
    return result


def init_single_subject_wf(subject_id: str, bids_dir: str) -> Workflow:
    """Organize the preprocessing pipeline for a single subject.

    Args:
        subject_id: Subject label for this single-subject workflow.

    Returns:
        workflow for subject
    """
    name = f"single_subject_{subject_id}_wf"
    subject_data = collect_data(
        bids_dir,
        subject_id,
    )[0]

    if not subject_data["pet"]:
        raise RuntimeError(
            "No PET images found for participant {}. "
            "All workflows require PET images.".format(subject_id)
        )

    if not subject_data["t1w"]:
        raise RuntimeError(
            "No T1w images found for participant {}. "
            "All workflows require T1w images.".format(subject_id)
        )

    # find the best matching t1w for each pet
    # we do this by comparing file names and picking the t1w that has the highest
    # number of matching characters with pet up to first discrepancy
    t1w_best_matches = []
    for pet_file in subject_data["pet"]:
        t1w_best_matches.append(
            sorted(
                subject_data["t1w"], key=lambda x: -count_matching_chars(pet_file, x)
            )[0]
        )

    datasink = Node(
        DataSink(base_directory=os.path.join(bids_dir, "derivatives", "petdeface")),
        name="sink",
    )

    # deface t1w(s)
    # defacing is not necessary for MRIs without a matching PET
    # an MRI might get matched with multiple PET scans, but we need to run
    # deface only once
    # t1w_wf = Workflow(name=f"single_subject_t1w_{subject_id}_wf")
    t1w_wf = Workflow(name="t1w_wf")
    unique_t1w_best_matches = sorted(set(t1w_best_matches))
    for j, t1w_file in enumerate(unique_t1w_best_matches):
        ses_id = re.search("/ses-(.+?)/", t1w_file).group(1)
        deface_t1w = Node(
            Mideface(in_file=t1w_file),
            name=f"deface_t1w{j}",
        )
        t1w_wf.connect(
            [
                (
                    deface_t1w,
                    datasink,
                    [
                        ("out_file", f"sub-{subject_id}.ses-{ses_id}.anat"),
                        (
                            "out_facemask",
                            f"sub-{subject_id}.ses-{ses_id}.anat.@facemask",
                        ),
                    ],
                ),
            ]
        )

    workflow = Workflow(name=name)
    for i, pet_file in enumerate(subject_data["pet"]):
        ses_id = re.search("/ses-(.+?)/", str(subject_data["pet"])).group(1)

        t1w_best_match = t1w_best_matches[i]
        pet_wf = Workflow(name=f"pet{i}_wf")

        weighted_average = Node(
            WeightedAverage(pet_file=pet_file), name="weighted_average"
        )

        coreg_pet_to_t1w = Node(
            MRICoreg(reference_file=t1w_best_match), name="coreg_pet_to_t1w"
        )

        deface_pet = Node(ApplyMideface(in_file=pet_file), name="deface_pet")

        pet_wf.connect(
            [
                (weighted_average, coreg_pet_to_t1w, [("out_file", "source_file")]),
                (coreg_pet_to_t1w, deface_pet, [("out_lta_file", "lta_file")]),
                (
                    coreg_pet_to_t1w,
                    datasink,
                    [("out_lta_file", f"sub-{subject_id}.ses-{ses_id}.pet")],
                ),
                (
                    deface_pet,
                    datasink,
                    [("out_file", f"sub-{subject_id}.ses-{ses_id}.pet.@defaced")],
                ),
            ]
        )

        # find the t1w index
        j = unique_t1w_best_matches.index(t1w_best_match)
        workflow.connect(
            [(t1w_wf, pet_wf, [(f"deface_t1w{j}.out_facemask", "deface_pet.facemask")])]
        )

    return workflow


def write_out_dataset_description_json(input_bids_dir, output_bids_dir=None):
    # set output dir to input dir if output dir is not specified
    if output_bids_dir is None:
        output_bids_dir = pathlib.Path(
            os.path.join(input_bids_dir, "derivatives", "petdeface")
        )
        output_bids_dir.mkdir(parents=True, exist_ok=True)

    # collect name of dataset from input folder
    try:
        with open(os.path.join(input_bids_dir, "dataset_description.json")) as f:
            source_dataset_description = json.load(f)
    except FileNotFoundError:
        source_dataset_description = {"Name": "Unknown"}

    with open(os.path.join(output_bids_dir, "dataset_description.json"), "w") as f:
        dataset_description = {
            "Name": f"petdeface - PET and Anatomical Defacing workflow: "
            f"PET Defaced Version of BIDS Dataset `{source_dataset_description['Name']}`",
            "BIDSVersion": __bids_version__,
            "GeneratedBy": [
                {
                    "Name": "PET Deface",
                    "Version": __version__,
                    "CodeURL": "https://github.com/openneuropet/petdeface",
                }
            ],
            "HowToAcknowledge": "This workflow uses FreeSurfer: `Fischl, B., FreeSurfer. Neuroimage, 2012. 62(2): p. 774-8.`,"
            "and the MiDeFace package developed by Doug Greve: `https://surfer.nmr.mgh.harvard.edu/fswiki/MiDeFace`",
            "License": "CCBY",
        }

        json.dump(dataset_description, f, indent=4)


class PetDeface:
    def __init__(
        self,
        bids_dir,
        output_dir=None,
        anat_only=False,  # TODO: currently not implemented
        subject="",
        session="",  # TODO: currently not implemented
        n_procs=2,
        skip_bids_validator=True,
        remove_existing=True,  # TODO: currently not implemented
        placement="adjacent",  # TODO: currently not implemented
    ):
        self.bids_dir = bids_dir
        self.remove_existing = remove_existing
        self.placement = placement
        self.output_dir = output_dir
        self.anat_only = anat_only
        self.subject = subject
        self.session = session
        self.n_procs = n_procs
        self.skip_bids_validator = skip_bids_validator

        # check if freesurfer license is valid
        self.fs_license = check_valid_fs_license()
        if not self.fs_license:
            raise ValueError("Freesurfer license is not valid")

    def run(self):
        deface(
            {
                "bids_dir": self.bids_dir,
                "output_dir": self.output_dir,
                "anat_only": self.anat_only,
                "subject": self.subject,
                "session": self.session,
                "n_procs": self.n_procs,
                "skip_bids_validator": self.skip_bids_validator,
                "participant_label": self.subject,
                "placement": self.placement,
                "remove_existing": self.remove_existing,
            }
        )


def cli():
    parser = argparse.ArgumentParser(description="PetDeface")

    parser.add_argument(
        "input_dir", help="The directory with the input dataset", type=pathlib.Path
    )
    parser.add_argument(
        "--output_dir",
        "-o",
        help="The directory where the output files should be stored",
        type=pathlib.Path,
        required=False,
        default=None,
    )
    parser.add_argument(
        "--anat_only",
        "-a",
        action="store_true",
        default=False,
        help="Only deface anatomical images",
    )
    parser.add_argument(
        "--subject",
        "-s",
        help="The label of the subject to be processed.",
        type=str,
        required=False,
        default="",
    )
    parser.add_argument(
        "--session",
        "-ses",
        help="The label of the session to be processed.",
        type=str,
        required=False,
        default="",
    )
    parser.add_argument(
        "--docker",
        "-d",
        action="store_true",
        default=False,
        help="Run in docker container",
    ),
    parser.add_argument(
        "--n_procs",
        help="Number of processors to use when running the workflow",
        default=2,
    )
    parser.add_argument("--skip_bids_validator", action="store_true", default=False)
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="PetDeface version {}".format(__version__),
    )
    parser.add_argument(
        "--placement",
        "-p",
        help="Where to place the defaced images. Options are "
        "'adjacent': next to the input_dir (default) in a folder appended with _defaced"
        "'inplace': defaces the dataset in place, e.g. replaces faced PET and T1w images w/ defaced at input_dir"
        "'derivatives': does all of the defacing within the derivatives folder in input_dir.",
        type=str,
        required=False,
        default="adjacent",
    )
    parser.add_argument(
        "--remove_existing",
        "-r",
        help="Remove existing output files in output_dir.",
        action="store_true",
        default=False,
    )

    arguments = parser.parse_args()

    return arguments


def main():  # noqa: max-complexity: 12
    # determine present working directory
    pwd = pathlib.Path.cwd()

    # if this script is being run where this file is located assume that the user wants to mount the code folder
    # into the docker container
    if pwd == pathlib.Path(__file__).parent:
        code_dir = str(pathlib.Path(__file__).parent.absolute())
    else:
        code_dir = None

    args = cli()

    if isinstance(args.input_dir, pathlib.PosixPath) and "~" in str(args.input_dir):
        args.input_dir = args.input_dir.expanduser().resolve()
    else:
        args.input_dir = args.input_dir.absolute()
    if isinstance(args.output_dir, pathlib.PosixPath) and "~" in str(args.output_dir):
        args.output_dir = args.output_dir.expanduser().resolve()
    else:
        if args.output_dir:
            args.output_dir = args.output_dir.absolute()

    if args.docker:
        check_docker_installed()
        check_docker_image_exists("petdeface", build=False)

        input_mount_point = str(args.input_dir)
        output_mount_point = str(args.output_dir)
        args.input_dir = pathlib.Path("/input")
        args.output_dir = pathlib.Path("/output")
        print(
            "Attempting to run in docker container, mounting {} to {} and {} to {}".format(
                input_mount_point, args.input_dir, output_mount_point, args.output_dir
            )
        )
        # convert args to dictionary
        args_dict = vars(args)
        for key, value in args_dict.items():
            if isinstance(value, pathlib.PosixPath):
                args_dict[key] = str(value)

        args_dict.pop("docker")

        # remove False boolean keys and values, and set true boolean keys to empty string
        args_dict = {key: value for key, value in args_dict.items() if value}
        set_to_empty_str = [key for key, value in args_dict.items() if value == True]
        for key in set_to_empty_str:
            args_dict[key] = "empty_str"

        args_string = " ".join(
            ["--{} {}".format(key, value) for key, value in args_dict.items() if value]
        )
        args_string = args_string.replace("empty_str", "")

        # remove --input_dir from args_string as input dir is positional, we
        # we're simply removing an artifact of argparse
        args_string = args_string.replace("--input_dir", "")

        # invoke docker run command to run petdeface in container, while redirecting stdout and stderr to terminal
        docker_command = (
            f"docker run -a stderr -a stdout --rm "
            f"-v {input_mount_point}:{args.input_dir} "
            f"-v {output_mount_point}:{args.output_dir} "
        )
        if code_dir:
            docker_command += f"-v {code_dir}:/petdeface "

        # collect location of freesurfer license if it's installed and working
        if check_valid_fs_license():
            license_location = locate_freesurfer_license()
            if license_location:
                docker_command += f"-v {license_location}:/opt/freesurfer/license.txt "

        # specify platform
        docker_command += "--platform linux/amd64 "

        docker_command += f"petdeface:latest " f"{args_string}"

        print("Running docker command: \n{}".format(docker_command))

        subprocess.run(docker_command, shell=True)

    else:
        petdeface = PetDeface(
            bids_dir=args.input_dir,
            output_dir=args.output_dir,
            anat_only=args.anat_only,
            subject=args.subject,
            session=args.session,
            n_procs=args.n_procs,
            skip_bids_validator=args.skip_bids_validator,
            remove_existing=args.remove_existing,
            placement=args.placement,
        )
        petdeface.run()


if __name__ == "__main__":
    main()
