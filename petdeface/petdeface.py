import argparse
import shutil
import os
import subprocess
import pathlib
import bids
from typing import Union
from nipype import Function
from nipype.interfaces.io import SelectFiles

# some day I'll figure out how to make packing work across dev and install environments
try:
    from mideface import Mideface
    from pet import create_weighted_average_pet
except ModuleNotFoundError:
    from .mideface import Mideface
    from .pet import create_weighted_average_pet

from nipype.interfaces.freesurfer import MRICoreg
from nipype.interfaces.utility import IdentityInterface
from niworkflows.utils.misc import check_valid_fs_license
from nipype.pipeline import Node, Workflow

# collect version from pyproject.toml
places_to_look = [pathlib.Path(__file__).parent.absolute(), pathlib.Path(__file__).parent.parent.absolute()]

__version__ = "unable to locate version number in pyproject.toml"

# search for toml file
for place in places_to_look:
    for root, folders, files in os.walk(place):
        for file in files:
            if file.endswith("pyproject.toml"):
                toml_file = os.path.join(root, file)

                with open(toml_file, "r") as f:
                    for line in f.readlines():
                        if "version" in line and len(line.split("=")) > 1:
                            __version__ = line.split("=")[1].strip().replace('"', "")
                break


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


def deface(args: Union[dict, argparse.Namespace]):
    """Main function for the PET Deface workflow."""

    if type(args) is dict:
        args = argparse.Namespace(**args)
    else:
        args = args

    if os.path.exists(args.bids_dir):
        if not args.skip_bids_validator:
            layout = bids.BIDSLayout(args.bids_dir, validate=True)
        else:
            layout = bids.BIDSLayout(args.bids_dir, validate=False)
    else:
        raise Exception('BIDS directory does not exist')

    if check_valid_fs_license() is not True:
        raise Exception('You need a valid FreeSurfer license to proceed!')

    # Get all PET files
    if args.participant_label is None:
        args.participant_label = layout.get(suffix='pet', target='subject', return_type='id')

    # create output derivatives directory
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # create output directory for this pipeline
    pipeline_dir = os.path.join(args.output_dir, 'petdeface')
    if not os.path.exists(pipeline_dir):
        os.makedirs(pipeline_dir)

    infosource = Node(IdentityInterface(
        fields = ['subject_id','session_id']),
        name = "infosource")

    sessions = layout.get_sessions()
    if sessions:
        infosource.iterables = [('subject_id', args.participant_label),
                                ('session_id', sessions)]
    else:
        infosource.iterables = [('subject_id', args.participant_label)]

    templates = {'t1w_file': 'sub-{subject_id}/anat/*_T1w.[n]*' if not sessions else 'sub-{subject_id}/*/anat/*_T1w.[n]*',
                 'pet_file': 'sub-{subject_id}/pet/*_pet.[n]*' if not sessions else 'sub-{subject_id}/ses-{session_id}/pet/*_pet.[n]*',
                 'json_file': 'sub-{subject_id}/pet/*_pet.json' if not sessions else 'sub-{subject_id}/ses-{session_id}/pet/*_pet.json'}

    selectfiles = Node(SelectFiles(templates,
                                   base_directory = args.bids_dir),
                       name = "select_files")

    substitutions = [('_subject_id', 'sub'), ('_session_id_', 'ses')]
    subjFolders = [('sub-%s' % (sub), 'sub-%s' % (sub))
                   for sub in layout.get_subjects()] if not sessions else [('sub-%s_ses-%s' % (sub, ses), 'sub-%s/ses-%s' % (sub, ses))
                                                                           for ses in layout.get_sessions()
                                                                           for sub in layout.get_subjects()]

    substitutions.extend(subjFolders)

    # clean up and create derivatives directories
    if args.output_dir is None:
        output_dir = os.path.join(args.bids_dir,'derivatives','petdeface')
    else:
        output_dir = args.output_dir

    # Define nodes for hmc workflow

    deface_t1w = Node(Mideface(out_file = 't1w_defaced.nii.gz',
                               out_facemask = 'face.mask.mgz',
                               odir = '.'),
                      name = 'deface_t1w')

    coreg_pet_to_t1w = Node(MRICoreg(),
                            name = 'coreg_pet_to_t1w')

    create_time_weighted_average = Node(Function(input_names = ['pet_file', 'bids_dir'],
                                                 output_names = ['out_file'],
                                                 function = create_weighted_average_pet),
                                        name = 'create_weighted_average_pet')

    create_time_weighted_average.inputs.bids_dir = args.bids_dir

    deface_pet = Node(Mideface(out_file = 'pet_defaced.nii.gz',
                               out_facemask = 'face.mask.mgz',
                               odir = '.'),
                      name = 'deface_pet')

    create_apply_str_node = Node(Function(input_names=['t1w_defaced','facemask', 'lta_file', 'pet_file', 'bids_dir'],
                                          output_names=['apply_str'],
                                          function=create_apply_str),
                                 name='create_apply_str')
    create_apply_str_node.inputs.bids_dir = args.bids_dir

    workflow = Workflow(name='deface_pet_workflow', base_dir=args.bids_dir)
    workflow.config['execution']['remove_unnecessary_outputs'] = 'false'
    workflow.connect([(infosource, selectfiles, [('subject_id', 'subject_id'),('session_id', 'session_id')]),
                      (selectfiles, deface_t1w, [('t1w_file', 'in_file')]),
                      (selectfiles, create_time_weighted_average, [('pet_file', 'pet_file')]),
                      (selectfiles, coreg_pet_to_t1w, [('t1w_file', 'reference_file')]),
                      (create_time_weighted_average, coreg_pet_to_t1w, [('out_file', 'source_file')]),
                      (deface_t1w, create_apply_str_node, [('out_facemask', 'facemask')]),
                      (coreg_pet_to_t1w, create_apply_str_node, [('out_lta_file', 'lta_file')]),
                      (selectfiles, create_apply_str_node, [('pet_file', 'pet_file')]),
                      (deface_t1w, create_apply_str_node, [('out_file', 't1w_defaced')]),
                      (create_apply_str_node, deface_pet, [('apply_str', 'apply')])
                      ])

    wf = workflow.run(plugin='MultiProc', plugin_args={'n_procs' : int(args.n_procs)})

    # remove temp outputs
    shutil.rmtree(os.path.join(args.bids_dir, 'deface_pet_workflow'))


def create_apply_str(t1w_defaced, pet_file, facemask, lta_file, bids_dir):
    """Create string to be used for the --apply flag for defacing PET using mideface."""
    import bids
    import pathlib
    import shutil
    layout = bids.BIDSLayout(bids_dir)
    entities = layout.parse_file_entities(pet_file)

    subject = entities['subject']
    session = entities['session']
    out_file = f"{bids_dir}/derivatives/petdeface/sub-{subject}/ses-{session}/pet/sub-{subject}_ses-{session}_desc-defaced_pet.nii.gz"

    out_lta_file = f"{bids_dir}/derivatives/petdeface/sub-{subject}/ses-{session}/pet/sub-{subject}_ses-{session}_desc-pet2anat_pet.lta"
    out_mask_file = f"{bids_dir}/derivatives/petdeface/sub-{subject}/ses-{session}/anat/sub-{subject}_ses-{session}_desc-defaced_mask.mgz"
    out_t1w_defaced = f"{bids_dir}/derivatives/petdeface/sub-{subject}/ses-{session}/anat/sub-{subject}_ses-{session}_desc-defaced_T1w.nii.gz"

    pathlib.Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out_lta_file).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out_mask_file).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out_t1w_defaced).parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(t1w_defaced, out_t1w_defaced)
    shutil.copyfile(lta_file, out_lta_file)
    shutil.copyfile(facemask, out_mask_file)

    apply_str = f"{pet_file} {facemask} {lta_file} {out_file}"

    return apply_str


class PetDeface:
    def __init__(self, bids_dir, output_dir=None, anat_only=False, subject="", session="", n_procs=2,
                 skip_bids_validator=True):
        self.bids_dir = bids_dir
        if not output_dir:
            self.output_dir = self.bids_dir
        else:
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

        # create map of subjects in bids_dir
        self.subjects = {}
        for s in self.collect_subjects():
            self.subjects[s] = {'anat': [], 'pet': []}

        # collect pet and anat files
        self.collect_anat()
        self.collect_pet()

        # run pipeline


    def collect_anat(self):
        layout = bids.BIDSLayout(self.bids_dir)
        for subject in self.subjects:
            anat_files = layout.get(subject=subject,
                                    extension=[".nii", ".nii.gz"],
                                    suffix="T1w", return_type="file")
            self.subjects[subject]['anat'] = anat_files

    def collect_pet(self):
        layout = bids.BIDSLayout(self.bids_dir)
        for subject in self.subjects:
            pet_files = layout.get(subject=subject,
                                   extension=[".nii", ".nii.gz"],
                                   suffix="pet", return_type="file")
            self.subjects[subject]['pet'] = pet_files

    def collect_subjects(self):
        layout = bids.BIDSLayout(self.bids_dir)
        subjects = layout.get_subjects()
        return subjects

    def run(self):
        deface({"bids_dir": self.bids_dir,
                "output_dir": self.output_dir,
                "anat_only": self.anat_only,
                "subject": self.subject,
                "session": self.session,
                "n_procs": self.n_procs,
                "skip_bids_validator": self.skip_bids_validator,
                "participant_label": None,  # this should be updated to subject?
               })


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
    parser.add_argument('--n_procs', help='Number of processors to use when running the workflow', default=2)
    parser.add_argument("--skip_bids_validator", action="store_true", default=False)
    parser.add_argument("--version", "-v", action="version", version="PetDeface version {}".format(__version__))

    arguments = parser.parse_args()

    return arguments


def main():
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
                docker_command += f"-v {license_location}:/opt/freesurfer/license.txt "

        # specify platform
        docker_command += f"--platform linux/amd64 "

        docker_command += f"petdeface:latest " \
                          f"python3 /petdeface/petdeface/run.py {args_string}"

        print("Running docker command: \n{}".format(docker_command))

        subprocess.run(docker_command, shell=True)

    else:
        petdeface = PetDeface(args.input_dir, args.output_dir, args.anat_only, args.subject, args.session, args.n_procs)
        petdeface.run()


if __name__ == "__main__":
    main()
