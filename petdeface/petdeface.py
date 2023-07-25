import argparse
import shutil
import os
import sys
import json
import subprocess
import pathlib
import bids
import gzip
from typing import Union
from nipype import Function
from nipype.interfaces.io import SelectFiles

# some day someone will figure out how to make packing work across dev and install environments
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
                        if "version" in line and len(line.split("=")) > 1 and "bids_version" not in line:
                            __version__ = line.split("=")[1].strip().replace('"', "")
                        if "bids_version" in line and len(line.split("=")) > 1:
                            __bids_version__ = line.split("=")[1].strip().replace('"', "")
                break


def locate_freesurfer_license():
    # collect freesurfer home environment variable
    fs_home = pathlib.Path(os.environ.get("FREESURFER_HOME", ""))
    if not fs_home:
        raise ValueError(
            "FREESURFER_HOME environment variable is not set, unable to determine location of license file")
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
        # it gets really annoying when there are both gzipped and unzipped nifti files, we are going to
        # zip them all up before we get started
        layout = bids.BIDSLayout(args.bids_dir, validate=False)
        for file in layout.get(extension='nii', return_type='file'):
            zip_nifti(file)

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

    infosource = Node(IdentityInterface(
        fields=['subject_id', 'session_id']),
        name="infosource")

    sessions = layout.get_sessions()
    if sessions:
        infosource.iterables = [('subject_id', args.participant_label),
                                ('session_id', sessions)]
    else:
        infosource.iterables = [('subject_id', args.participant_label)]

    templates = {
        't1w_file': 'sub-{subject_id}/anat/*_T1w.[n]*' if not sessions else 'sub-{subject_id}/*/anat/*_T1w.[n]*',
        'pet_file': 'sub-{subject_id}/pet/*_pet.[n]*' if not sessions else 'sub-{subject_id}/ses-{session_id}/pet/*_pet.[n]*',
        'json_file': 'sub-{subject_id}/pet/*_pet.json' if not sessions else 'sub-{subject_id}/ses-{session_id}/pet/*_pet.json'}

    selectfiles = Node(SelectFiles(templates,
                                   base_directory=args.bids_dir),
                       name="select_files")

    substitutions = [('_subject_id', 'sub'), ('_session_id_', 'ses')]
    subjFolders = [('sub-%s' % (sub), 'sub-%s' % (sub))
                   for sub in layout.get_subjects()] if not sessions else [
        ('sub-%s_ses-%s' % (sub, ses), 'sub-%s/ses-%s' % (sub, ses))
        for ses in layout.get_sessions()
        for sub in layout.get_subjects()]

    substitutions.extend(subjFolders)

    # clean up and create derivatives directories
    if args.output_dir is None:
        output_dir = os.path.join(args.bids_dir, 'derivatives', 'petdeface')
    else:
        output_dir = args.output_dir

    # write out dataset_description.json file at input and output directories
    write_out_dataset_description_json(args.bids_dir, output_dir)
    write_out_dataset_description_json(args.bids_dir)

    # Define nodes for hmc workflow

    deface_t1w = Node(Mideface(out_file='t1w_defaced.nii.gz',
                               out_facemask='face.mask.mgz',
                               odir='.'),
                      name='deface_t1w')

    coreg_pet_to_t1w = Node(MRICoreg(),
                            name='coreg_pet_to_t1w')

    create_time_weighted_average = Node(Function(input_names=['pet_file', 'bids_dir'],
                                                 output_names=['out_file'],
                                                 function=create_weighted_average_pet),
                                        name='create_weighted_average_pet')

    create_time_weighted_average.inputs.bids_dir = args.bids_dir

    deface_pet = Node(Mideface(out_file='pet_defaced.nii.gz',
                               out_facemask='face.mask.mgz',
                               odir='.'),
                      name='deface_pet')

    create_apply_str_node = Node(Function(input_names=['t1w_defaced', 'facemask', 'lta_file', 'pet_file', 'bids_dir'],
                                          output_names=['apply_str'],
                                          function=create_apply_str),
                                 name='create_apply_str')
    create_apply_str_node.inputs.bids_dir = args.bids_dir

    workflow = Workflow(name='deface_pet_workflow', base_dir=args.bids_dir)
    workflow.config['execution']['remove_unnecessary_outputs'] = 'false'
    workflow.connect([(infosource, selectfiles, [('subject_id', 'subject_id'), ('session_id', 'session_id')]),
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

    wf = workflow.run(plugin='MultiProc', plugin_args={'n_procs': int(args.n_procs)})

    # remove temp outputs
    shutil.rmtree(os.path.join(args.bids_dir, 'deface_pet_workflow'))



def zip_nifti(nifti_file):
    """Zips an un-gzipped nifti file and removes the original file."""
    if str(nifti_file).endswith('.gz'):
        return nifti_file
    else:
        with open(nifti_file, 'rb') as infile:
            with gzip.open(nifti_file + '.gz', 'wb') as outfile:
                shutil.copyfileobj(infile, outfile)
        os.remove(nifti_file)
        return nifti_file + '.gz'


def write_out_dataset_description_json(input_bids_dir, output_bids_dir=None):
    # set output dir to input dir if output dir is not specified
    if output_bids_dir is None:
        output_bids_dir = pathlib.Path(os.path.join(input_bids_dir, "derivatives", "petdeface"))
        output_bids_dir.mkdir(parents=True, exist_ok=True)

    # collect name of dataset from input folder
    try:
        with open(os.path.join(input_bids_dir, 'dataset_description.json')) as f:
            source_dataset_description = json.load(f)
    except FileNotFoundError:
        source_dataset_description = {"Name": "Unknown"}

    with open(os.path.join(output_bids_dir, 'dataset_description.json'), 'w') as f:
        dataset_description = {
            "Name": f"petdeface - PET and Anatomical Defacing workflow: "
                    f"PET Defaced Version of BIDS Dataset `{source_dataset_description['Name']}`",
            "BIDSVersion": __bids_version__,
            "GeneratedBy": [
                {"Name": "PET Deface",
                 "Version": __version__,
                 "CodeURL": "https://github.com/bendhouseart/petdeface"}],
            "HowToAcknowledge": "This workflow uses FreeSurfer: `Fischl, B., FreeSurfer. Neuroimage, 2012. 62(2): p. 774-8.`,"
                                "and the MiDeFace package developed by Doug Greve: `https://surfer.nmr.mgh.harvard.edu/fswiki/MiDeFace`",
            "License": "CCBY"
        }

        json.dump(dataset_description, f, indent=4)


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
                 skip_bids_validator=True, remove_existing=True, placement="adjacent"):
        self.bids_dir = bids_dir
        self.remove_existing = remove_existing
        self.placement = placement
        if not output_dir:
            self.output_dir = self.bids_dir
        else:
            self.output_dir = output_dir
        self.anat_only = anat_only
        self.subject = subject
        self.session = session
        self.n_procs = n_procs
        self.skip_bids_validator = skip_bids_validator
        self.layout = bids.BIDSLayout(self.bids_dir)

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
        layout = self.layout
        # layout = bids.BIDSLayout(self.bids_dir)
        for subject in self.subjects:
            anat_files = layout.get(subject=subject,
                                    extension=[".nii", ".nii.gz"],
                                    suffix="T1w", return_type="file")
            self.subjects[subject]['anat'] = anat_files

    def collect_pet(self):
        layout = self.layout
        # layout = bids.BIDSLayout(self.bids_dir)
        for subject in self.subjects:
            pet_files = layout.get(subject=subject,
                                   extension=[".nii", ".nii.gz"],
                                   suffix="pet", return_type="file")
            self.subjects[subject]['pet'] = pet_files

    def collect_subjects(self):
        layout = self.layout
        # layout = bids.BIDSLayout(self.bids_dir)
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
                "placement": self.placement,
                "remove_existing": self.remove_existing,
                })

        wrap_up_defacing(self.bids_dir, self.output_dir, placement=self.placement, remove_existing=self.remove_existing)


def wrap_up_defacing(path_to_dataset, output_dir=None, placement="adjacent", remove_existing=True):
    """
    This function maps the output of this pipeline to the original dataset and depending on the
    flag/arg for placement either replaces the defaced images in the same directory as the original images,
    creates a copy of the original dataset at {path_to_dataset}_defaced and places the defaced images there
    along with the defacing masks and registration files at the copied dir in the deriviatives folder, or lastly
    leaves things well enough alone and just places the defaced images in the derivatives folder (does nothing).

    Parameters
    ----------
    path_to_dataset : path like object (str or pathlib.Path)
        Path to original dataset
    output_dir : path like object (str or pathib.Path), optional
        Specific directory to place output, this seems redundant given placemnent, by default None
    placement : str, optional
        Can be one of three values
        - adjacent creates (but doesn't overrwrite) a new dataset with only defaced images
        - inplace replaces original images with defaced versions (not recommended)
        - derivatives does nothing, defaced images exist only within the derivitives/petdeface dir
        by default "adjacent"
    """
    # get bids layout of dataset
    layout = bids.BIDSLayout(path_to_dataset, derivatives=True)

    # collect defaced images
    try:
        defacing_files = layout.get(desc='defaced')
    except ValueError as err:
        print(err)
        print(f"No defaced images found at {path_to_dataset}, you might need to rerun the petdeface workflow")
        sys.exit(1)

    # collect all original images and jsons
    raw_only = bids.BIDSLayout(path_to_dataset, derivatives=False)
    raw_images_only = raw_only.get(suffix=['pet', 'T1w'])

    # if output_dir is not None and is not the same as the input dir we want to clear it out
    if output_dir is not None and output_dir != path_to_dataset and remove_existing:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True, mode=0o775)

    # create dictionary of original images and defaced images
    mapping_dict = {}
    for defaced in defacing_files:
        for raw in raw_images_only:
            if \
                    defaced.entities['subject'] == raw.entities['subject'] and \
                    defaced.entities['session'] == raw.entities['session'] and \
                    raw.extension == defaced.extension:
                mapping_dict[defaced] = raw

    if placement == "adjacent":
        if output_dir is None or output_dir == path_to_dataset:
            final_destination = f"{path_to_dataset}_defaced"
        else:
            final_destination = output_dir

        # copy original dataset to new location
        for entry in raw_only.files:
            copy_path = entry.replace(str(path_to_dataset), str(final_destination))
            pathlib.Path(copy_path).parent.mkdir(parents=True, exist_ok=True, mode=0o775)
            if entry != copy_path:
                shutil.copy(entry, copy_path)

        # update paths in mapping dict
        move_defaced_images(mapping_dict, final_destination)

        # we also want to carry over the defacing masks and registration files
        masks_and_reg = layout.get(extension=['mgz', 'lta'])
        derivatives_source_and_dest = {}
        for file in masks_and_reg:
            source_path = pathlib.Path(file.path)
            dest_path = pathlib.Path(file.path.replace(str(path_to_dataset), str(final_destination)))
            if dest_path.parent.exists() is False:
                dest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o775)
            try:
                shutil.copy(file.path, file.path.replace(str(path_to_dataset), str(final_destination)))
            except shutil.SameFileError:
                pass

    elif placement == "inplace":
        final_destination = path_to_dataset
        move_defaced_images(mapping_dict, final_destination)
        # remove all anat nii's and pet niis from derivatives folder
        inplace_layout = bids.BIDSLayout(path_to_dataset, derivatives=True)
        derivatives = inplace_layout.get(suffix=['pet', 'T1w'], extension=['nii.gz', 'nii'], desc='defaced', return_type='file')
        for extraneous in derivatives:
            os.remove(extraneous)

    elif placement == "derivatives":
        pass
    else:
        raise ValueError("placement must be one of ['adjacent', 'inplace', 'derivatives']")

    print(f"completed copying dataset to {final_destination}")


def move_defaced_images(mapping_dict: dict,
                        final_destination: Union[str, pathlib.Path],
                        include_extra_anat: bool = False,
                        move_files: bool = False):
    # update paths in mapping dict
    for defaced, raw in mapping_dict.items():
        # get common path and replace with final_destination to get new path
        common_path = os.path.commonpath([defaced.path, raw.path])
        new_path = pathlib.Path(defaced.path.replace(common_path, str(final_destination)).replace('desc-defaced_', ''))
        # replace derivative and pet deface parts of path
        new_path = pathlib.Path(
            *([part for part in new_path.parts if part != 'derivatives' and part != 'petdeface']))
        mapping_dict[defaced] = new_path

    # copy defaced images to new location
    for defaced, raw in mapping_dict.items():
        # it should be noted that the defacing pipeline creates a copy of the t1w image and json in an anat folder
        # for every session. This isn't always desirable.
        if pathlib.Path(raw).exists() and pathlib.Path(defaced).exists() and not include_extra_anat:
            shutil.copy(defaced.path, raw)
        else:
            pathlib.Path(raw).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(defaced.path, raw)

        if move_files:
            os.remove(defaced.path)


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
    parser.add_argument("--placement", "-p", help="Where to place the defaced images. Options are "
                                                  "'adjacent': next to the input_dir (default) in a folder appended with _defaced"
                                                  "'inplace': defaces the dataset in place, e.g. replaces faced PET and T1w images w/ defaced at input_dir"
                                                  "'derivatives': does all of the defacing within the derivatives folder in input_dir.",
                        type=str, required=False, default="adjacent")
    parser.add_argument("--remove_existing", "-r", help="Remove existing output files in output_dir.",
                        action="store_true", default=False)

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

        # remove False boolean keys and values, and set true boolean keys to empty string
        args_dict = {key: value for key, value in args_dict.items() if value != False}
        set_to_empty_str = [key for key, value in args_dict.items() if value == True]
        for key in set_to_empty_str:
            args_dict[key] = "empty_str"

        args_string = " ".join(["--{} {}".format(key, value) for key, value in args_dict.items() if value])
        args_string = args_string.replace("empty_str", "")

        # remove --input_dir from args_string as input dir is positional, we
        # we're simply removing an artifact of argparse
        args_string = args_string.replace("--input_dir", "")

        # invoke docker run command to run petdeface in container, while redirecting stdout and stderr to terminal
        docker_command = f"docker run -a stderr -a stdout --rm " \
                         f"-v {input_mount_point}:{args.input_dir} " \
                         f"-v {output_mount_point}:{args.output_dir} "
        if code_dir:
            docker_command += f"-v {code_dir}:/petdeface "

        # collect location of freesurfer license if it's installed and working
        if check_valid_fs_license():
            license_location = locate_freesurfer_license()
            if license_location:
                docker_command += f"-v {license_location}:/opt/freesurfer/license.txt "

        # specify platform
        docker_command += f"--platform linux/amd64 "

        docker_command += f"petdeface:latest " \
                          f"{args_string}"
        # f"python3 /petdeface/petdeface.py {args_string}"

        print("Running docker command: \n{}".format(docker_command))

        subprocess.run(docker_command, shell=True)

    else:
        petdeface = PetDeface(bids_dir=args.input_dir, output_dir=args.output_dir,
                              anat_only=args.anat_only, subject=args.subject,
                              session=args.session, n_procs=args.n_procs,
                              skip_bids_validator=args.skip_bids_validator, remove_existing=args.remove_existing,
                              placement=args.placement)
        petdeface.run()


if __name__ == "__main__":
    main()
