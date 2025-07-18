import argparse
import json
import os
import pathlib
import re
import sys
import shutil
from bids import BIDSLayout, BIDSLayoutIndexer
import glob
from platform import system
from pathlib import Path
import subprocess
from typing import Union
from nipype.interfaces.freesurfer import MRICoreg
from nipype.interfaces.io import DataSink
from nipype.interfaces.base.traits_extension import File as traits_extensionFile
from nipype.pipeline import Node
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from niworkflows.utils.bids import collect_data
from niworkflows.utils.bids import collect_participants
from niworkflows.utils.misc import check_valid_fs_license
from petutils.petutils import collect_anat_and_pet
from importlib.metadata import version

# Determine if we're running as a script (including through debugger)
is_script = (
    __name__ == "__main__"
    or len(sys.argv) > 0
    and sys.argv[0].endswith("petdeface.py")
    or "debugpy" in sys.modules
)

if is_script:
    # Running as script - add current directory to path for local imports
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))

    # Import using absolute imports (script mode)
    from mideface import ApplyMideface, Mideface
    from pet import WeightedAverage
    from qa import run_qa
    from utils import run_validator
    from noanat import copy_default_anat_to_subject, remove_default_anat
else:
    # Running as module - use relative imports
    from .mideface import ApplyMideface, Mideface
    from .pet import WeightedAverage
    from .qa import run_qa
    from .utils import run_validator
    from .noanat import copy_default_anat_to_subject, remove_default_anat


# collect version from pyproject.toml
places_to_look = [
    pathlib.Path(__file__).parent.absolute(),
    pathlib.Path(__file__).parent.parent.absolute(),
]

__version__ = "unable to locate version number"
# we use the default version at the time of this writing, but the most current version
# can be found in the pyproject.toml file under the [tool.bids] section
__bids_version__ = "1.8.0"

temp_anat_subjects = []


if __version__ == "unable to locate version number":
    # we try to load the version using import lib
    try:
        __version__ = version(__package__)
    except ValueError:
        # if we can't load the version using importlib we try to load it from the pyproject.toml
        for place in places_to_look:
            try:
                with open(place / "pyproject.toml") as f:
                    for line in f:
                        if "version" in line and "bid" not in line.lower():
                            __version__ = line.split("=")[1].strip().replace('"', "")
                            break
            except FileNotFoundError:
                pass


def locate_freesurfer_license():
    """
    Checks for freesurfer license on host system and returns path to license file if it exists.
    Raises error if $FREESURFER_HOME is not set or if license file does not exist at $FREESURFER_HOME/license.txt

    :raises ValueError: if FREESURFER_HOME environment variable is not set
    :raises ValueError: if license file does not exist at FREESURFER_HOME/license.txt
    :return: full path to Freesurfer license file
    :rtype: pathlib.Path
    """

    # check to see if FREESURFER_LICENSE variable is set, if so we can skip the rest of this function
    if os.environ.get("FREESURFER_LICENSE", ""):
        fs_license_env_var = pathlib.Path(os.environ.get("FREESURFER_LICENSE", ""))
        if not fs_license_env_var.exists():
            raise ValueError(
                f"Freesurfer license file does not exist at {fs_license_env_var}, but is set under $FREESURFER_LICENSE variable."
                f"Update or unset this varible to use the license.txt at $FREESURFER_HOME"
            )
        else:
            return fs_license_env_var
    else:
        # collect freesurfer home environment variable and look there instead
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
    """
    Checks to see if docker is installed on the host system, raises exception if it is not.

    :raises Exception: if docker is not installed
    :return: status of docker installation
    :rtype: bool
    """
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
    """
    Determines if the script is running in a docker container, returns True if it is, False otherwise

    :return: if running in docker container
    :rtype: bool
    """
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
    """
    Checks to see if a docker image exists, if it does not and build is set to True, it will attempt to build the image.

    :param image_name: name of docker image
    :type image_name: string
    :param build: try to build a docker image if none is found, defaults to False
    :type build: bool, optional
    :return: status of whether or not the image exists
    :rtype: bool
    """
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
    """
    Main function for the PET Deface workflow.

    :param args: given a dictionary or argparsed namespace, this function will run the defacing workflow
    :type args: Union[dict, argparse.Namespace]
    :raises Exception: if a valid FreeSurfer license is not found
    """

    if type(args) is dict:
        args = argparse.Namespace(**args)
    else:
        args = args

    # first check to see if the dataset is bids valid
    if not args.skip_bids_validator:
        run_validator(args.bids_dir)

    if not check_valid_fs_license() and not locate_freesurfer_license().exists():
        raise Exception("You need a valid FreeSurfer license to proceed!")

    if args.participant_label:
        subjects = args.participant_label
        # if subject contains the string sub-, remove it to avoid redundancy as pybids will add it uses the
        # right side of the sub- string as the subject label
        if any("sub-" in subject for subject in subjects):
            print("One or more subject contains sub- string")
        subjects = [subject.replace("sub-", "") for subject in subjects]
        # raise error if a supplied subject is not contained in the dataset
        participants = collect_participants(
            args.bids_dir, bids_validate=~args.skip_bids_validator
        )
        for subject in subjects:
            if subject not in participants:
                raise FileNotFoundError(
                    f"sub-{subject} not found in dataset {args.bids_dir}"
                )
    else:
        subjects = collect_participants(
            args.bids_dir, bids_validate=~args.skip_bids_validator
        )

    # check to see if any subjects are excluded from the defacing workflow
    if args.participant_label_exclude != []:
        print(
            f"Removing the following subjects {args.participant_label_exclude} from the defacing workflow"
        )
        args.participant_label_exclude = [
            subject.replace("sub-", "") for subject in args.participant_label_exclude
        ]
        subjects = [
            subject
            for subject in subjects
            if subject not in args.participant_label_exclude
        ]

        print(f"Subjects remaining in the defacing workflow: {subjects}")

    # clean up and create derivatives directories
    if args.output_dir == "None" or args.output_dir is None:
        output_dir = os.path.join(args.bids_dir, "derivatives", "petdeface")
    else:
        output_dir = args.output_dir

    petdeface_wf = Workflow(name="petdeface_wf", base_dir=output_dir)

    missing_file_errors = []

    for subject_id in subjects:
        try:
            single_subject_wf = init_single_subject_wf(
                subject_id,
                args.bids_dir,
                preview_pics=args.preview_pics,
                anat_only=args.anat_only,
                session_label=args.session_label,
                session_label_exclude=args.session_label_exclude,
                use_template_anat=args.use_template_anat,
            )
        except FileNotFoundError as error:
            single_subject_wf = None
            missing_file_errors.append(str(error))
        if single_subject_wf:
            petdeface_wf.add_nodes([single_subject_wf])

    if (
        missing_file_errors
    ):  # todo add conditional later for cases where a template t1w is used
        raise FileNotFoundError(
            "The following subjects are missing t1w images:\n"
            + "\n".join(missing_file_errors)
        )

    try:
        petdeface_wf.write_graph("petdeface.dot", graph2use="colored", simple_form=True)
    except OSError as Err:
        print(f"Raised this error {Err}\nGraphviz may not be installed.")
    petdeface_wf.run(plugin="MultiProc", plugin_args={"n_procs": int(args.n_procs)})

    # write out dataset_description.json file to derivatives directory
    write_out_dataset_description_json(args.bids_dir)

    # remove temp outputs - this is commented out to enable easier testing for now
    if str(os.getenv("PETDEFACE_DEBUG", "false")).lower() != "true":
        shutil.rmtree(os.path.join(output_dir, "petdeface_wf"))

    return {"subjects": subjects}


def init_single_subject_wf(
    subject_id: str,
    bids_data: Union[pathlib.Path, BIDSLayout],
    output_dir: pathlib.Path = None,
    preview_pics=False,
    anat_only=False,
    session_label=[],
    session_label_exclude=[],
    use_template_anat=None,
) -> Workflow:
    """
    Organize the preprocessing pipeline for a single subject.

    :param subject_id: _description_
    :type subject_id: str
    :param bids_data: _description_
    :type bids_data: pathlib.Path, BIDSLayout]
    :param output_dir: _description_, defaults to None
    :type output_dir: pathlib.Path, optional
    :param preview_pics: _description_, defaults to False (soon to be deprecated)
    :type preview_pics: bool, optional
    :param anat_only: _description_, defaults to False
    :type anat_only: bool, optional
    :param session: _description_, will default to only selecting session(s) supplied to this argument, defaults to []
    :type session: list, optional
    :param session_label_exclude: _description_, will exclude any session(s) supplied to this argument, defaults to []
    :type session_label_exclude: list, optional
    :param use_template_anat: _description_, will attempt to deface PET images lacking a T1w with existing template T1w packaged in petdeface, default to False,
    :type use_template_anat: str, optional
    :raises FileNotFoundError: _description_
    :return: _description_
    :rtype: Workflow
    """
    name = f"single_subject_{subject_id}_wf"

    if isinstance(bids_data, pathlib.Path):
        bids_data = BIDSLayout(bids_data)
    elif isinstance(bids_data, BIDSLayout):
        pass

    data = collect_anat_and_pet(bids_data)
    subject_data = data.get(subject_id)
    if subject_data is None:
        raise FileNotFoundError(f"Could not find data for subject sub-{subject_id}")

    # we combine the sessions to include and exclude into a single set of sessions to exclude from
    # the set of all sessions
    if session_label:
        sessions_to_exclude = list(
            set(bids_data.get_sessions())
            - (set(bids_data.get_sessions()) & set(session_label))
            | set(session_label_exclude)
        )
    else:
        sessions_to_exclude = session_label_exclude

    # check if any t1w images exist for the pet images
    for pet_image, t1w_image in subject_data.items():
        if t1w_image == "" and not use_template_anat:
            raise FileNotFoundError(
                f"Could not find t1w image for pet image {pet_image}"
            )
        elif t1w_image == "" and use_template_anat:
            created_items = copy_default_anat_to_subject(
                bids_dir=bids_data.root,
                subject_id=str(pet_image),
                pet_image=pet_image,
                default_anat=use_template_anat,
            )
            global temp_anat_subjects
            temp_anat_subjects.append(created_items)
            subject_data[pet_image] = str(
                created_items.get("created_files", ["", ""])[0]
            )

    # if we're adding in new t1w's and folder's we'll need to refresh the BIDS.layout object to reflect
    # those new changes
    bids_data = BIDSLayout(bids_data.root)

    bids_dir = bids_data.root

    if not output_dir:
        output_dir = pathlib.Path(bids_dir) / "derivatives" / "petdeface"

    output_dir.mkdir(parents=True, exist_ok=True)

    datasink = Node(
        DataSink(base_directory=str(output_dir)),
        name="sink",
    )

    datasink.inputs.substitutions = [
        (".face-after", "_desc-faceafter_T1w"),
        (".face-before", "_desc-facebefore_T1w"),
    ]

    # deface t1w(s)
    # an MRI might get matched with multiple PET scans, but we need to run
    # deface only once per MRI. This MRI file is the value for each entry in the output of
    # petutils.collect_anat_and_pet
    t1w_workflows = {}
    for t1w_file in set(subject_data.values()):
        ses_id = re.search("ses-[^_|\/]*", t1w_file)
        if ses_id:
            ses_id = f"{ses_id.group(0)}"
            anat_string = f"sub-{subject_id}_{ses_id}"
        else:
            ses_id = ""
            anat_string = f"sub-{subject_id}"

        workflow_name = f"t1w_{anat_string}_wf"

        t1w_wf = Workflow(name=workflow_name)

        # always set preview pics to false if running in docker
        if determine_in_docker():
            preview_pics = False

        # Check if this is a template anatomical image created from PET averaging
        is_template_from_pet = use_template_anat == "pet" and "desc-totallyat1w" in str(
            t1w_file
        )

        if is_template_from_pet:
            # For PET-averaged templates, we need to create a facemask without defacing the template
            # We'll use Mideface to generate the facemask but not apply it to the template

            # Create a node that generates facemask but doesn't deface the template
            template_facemask = Node(
                Mideface(
                    in_file=pathlib.Path(t1w_file),
                    pics=False,  # No preview pics for templates
                    odir=".",
                    code=f"{anat_string}_template",
                ),
                name=f"deface_t1w_{anat_string}",
            )

            # Only connect the facemask output, not the defaced template
            # This way we get the facemask for PET defacing but don't deface the template itself
            t1w_wf.connect(
                [
                    (
                        template_facemask,
                        datasink,
                        [
                            (
                                "out_facemask",
                                f"{anat_string.replace('_', '.')}.anat.@defacemask",
                            ),
                        ],
                    ),
                ]
            )
        else:
            # Normal defacing for real anatomical images
            deface_t1w = Node(
                Mideface(
                    in_file=pathlib.Path(t1w_file),
                    pics=preview_pics,
                    odir=".",
                    code=f"{anat_string}",
                ),
                name=f"deface_t1w_{anat_string}",
            )
            t1w_wf.connect(
                [
                    (
                        deface_t1w,
                        datasink,
                        [
                            ("out_file", f"{anat_string.replace('_', '.')}.anat"),
                            (
                                "out_facemask",
                                f"{anat_string.replace('_', '.')}.anat.@defacemask",
                            ),
                            (
                                "out_before_pic",
                                f"{anat_string.replace('_', '.')}.anat.@before",
                            ),
                            (
                                "out_after_pic",
                                f"{anat_string.replace('_', '.')}.anat.@after",
                            ),
                        ],
                    ),
                ]
            )

        t1w_workflows[t1w_file] = {
            "workflow": t1w_wf,
            "anat_string": anat_string,
            "is_template_from_pet": is_template_from_pet,
        }

    workflow = Workflow(name=name)
    if anat_only:
        for each in t1w_workflows.values():
            workflow.add_nodes([each["workflow"]])
    else:
        for pet_file, t1w_file in subject_data.items():
            try:
                ses_id = re.search("ses-[^_|\/]*", str(pet_file)).group(0)
                pet_string = f"sub-{subject_id}_{ses_id}"
            except AttributeError:
                ses_id = ""
                pet_string = f"sub-{subject_id}"

            # skip anything in the exclude list
            if ses_id.replace("ses-", "") in sessions_to_exclude:
                continue

            # collect tracer for filename only
            tracer_info = ""
            if re.search("trc-[^_|\/]*", str(pet_file)):
                tracer_info = "_" + re.search("trc-[^_|\/]*", str(pet_file)).group(0)

            # collect recontstruction
            if re.search("rec-[^_|\/]*", str(pet_file)):
                pet_string += "_" + re.search("rec-[^_|\/]*", str(pet_file)).group(0)

            # collect run info from pet file
            try:
                run_id = "_" + re.search("run-[^_|\/]*", str(pet_file)).group(0)
            except AttributeError:
                run_id = ""
            # Create workflow name with tracer for uniqueness
            pet_wf_name = f"pet_{pet_string}{tracer_info}{run_id}_wf"
            pet_wf = Workflow(name=pet_wf_name)

            weighted_average = Node(
                WeightedAverage(pet_file=pet_file), name="weighted_average"
            )

            # rename registration file to something more descriptive than registration.lta
            # we do this here to account for mulitple runs during the same session
            mricoreg = MRICoreg(reference_file=t1w_file)
            if use_template_anat:
                mricoreg.inputs.dof = 12

            mricoreg.inputs.out_lta_file = (
                f"{pet_string}{tracer_info}{run_id}_desc-pet2anat_pet.lta"
            )

            coreg_pet_to_t1w = Node(mricoreg, "coreg_pet_to_t1w")

            deface_pet = Node(ApplyMideface(in_file=pet_file), name="deface_pet")

            pet_wf.connect(
                [
                    (weighted_average, coreg_pet_to_t1w, [("out_file", "source_file")]),
                    (coreg_pet_to_t1w, deface_pet, [("out_lta_file", "lta_file")]),
                    (
                        coreg_pet_to_t1w,
                        datasink,
                        [
                            (
                                "out_lta_file",
                                f"{pet_string.replace('_', '.')}.pet.@{run_id}",
                            )
                        ],
                    ),
                    (
                        deface_pet,
                        datasink,
                        [
                            (
                                "out_file",
                                f"{pet_string.replace('_', '.')}.pet.@defaced{run_id}",
                            )
                        ],
                    ),
                ]
            )

            workflow.connect(
                [
                    (
                        t1w_workflows[t1w_file]["workflow"],
                        pet_wf,
                        [
                            (
                                f"deface_t1w_{t1w_workflows[t1w_file]['anat_string']}.out_facemask",
                                "deface_pet.facemask",
                            )
                        ],
                    )
                ]
            )

    return workflow


def write_out_dataset_description_json(input_bids_dir, output_bids_dir=None):
    """
    Writes an generic dataset_description.json file to the output directory.

    :param input_bids_dir: the input bids directory
    :type input_bids_dir: Union[pathlib.Path, str]
    :param output_bids_dir: the output defaced directory, defaults to None
    :type output_bids_dir: Union[pathlib.Path, str]
    """
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


def wrap_up_defacing(
    path_to_dataset,
    output_dir=None,
    placement="adjacent",
    remove_existing=True,
    participant_label_exclude=[],
    session_label_exclude=[],
    indexer=None,
):
    """
    This function maps the output of this pipeline to the original dataset and depending on the
    flag/arg for placement either replaces the defaced images in the same directory as the original images,
    creates a copy of the original dataset at {path_to_dataset}_defaced and places the defaced images there
    along with the defacing masks and registration files at the copied dir in the deriviatives folder, or lastly
    leaves things well enough alone and just places the defaced images in the derivatives folder (does nothing).

    path_to_dataset : path like object (str or pathlib.Path)

    output_dir : path like object (str or pathib.Path), optional
        Specific directory to place output, this seems redundant given placemnent, by default None
    placement : str, optional
        Can be one of three values
        - adjacent creates (but doesn't overrwrite) a new dataset with only defaced images
        - inplace replaces original images with defaced versions (not recommended)
        - derivatives does nothing, defaced images exist only within the derivitives/petdeface dir
        by default "adjacent"

    :param path_to_dataset: Path to original dataset
    :type path_to_dataset: path like object (str or pathlib.Path)
    :param output_dir: Specific directory to place output, arguably redundant given placemnent, defaults to
        bids_dir/derivatives/petdeface
    :type output_dir: path like object (str or pathlib.Path), optional
    :param placement:  str, optional
        Can be one of three values
        - adjacent creates (but doesn't overrwrite) a new dataset with only defaced images
        - inplace replaces original images with defaced versions (not recommended)
        - derivatives does nothing, defaced images exist only within the derivitives/petdeface dir
        by default "adjacent"
    :type placement: str, optional
    :param remove_existing: _description_, defaults to True
    :type remove_existing: bool, optional
    :param participant_label_exclude: Excludes set of participants from the finalized output
    :type participant_label_exclude: list, optional
    :param session_label_exclude: Excludes set of sessions from the finalized output
    :type session_label_exclude: list, optional
    :param indexer: Pre-built BIDSLayoutIndexer with exclusion patterns, defaults to None
    :type indexer: BIDSLayoutIndexer, optional
    :raises ValueError: _description_
    """
    # Use provided indexer or create one from exclude lists (fallback for compatibility)
    if indexer is None:
        subjects_to_exclude = [f"sub-{sub}/*" for sub in participant_label_exclude]
        sessions_to_exclude = [f"*ses-{ses}/*" for ses in session_label_exclude]
        exclude_total = subjects_to_exclude + sessions_to_exclude
        indexer = BIDSLayoutIndexer(ignore=exclude_total)

    # get bids layout of dataset using the indexer
    layout = BIDSLayout(
        path_to_dataset, derivatives=True, validate=False, indexer=indexer
    )

    # collect defaced images
    try:
        defacing_files = [f for f in layout.get() if "defaced" in str(f)]
    except ValueError as err:
        print(err)
        print(
            f"No defaced images found at {path_to_dataset}, you might need to rerun the petdeface workflow"
        )
        sys.exit(1)

    # collect all original images and jsons
    raw_only = BIDSLayout(path_to_dataset, derivatives=False, indexer=indexer)

    raw_images_only = raw_only.get(suffix=["pet", "T1w"])

    # if output_dir is not None and is not the same as the input dir we want to clear it out
    if output_dir is not None and output_dir != path_to_dataset and remove_existing:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True, mode=0o775)

    # create dictionary of original images and defaced images
    mapping_dict = {}
    for defaced in defacing_files:
        for raw in raw_images_only:
            if (defaced.filename).replace("_defaced.", ".") == raw.filename:
                mapping_dict[defaced] = raw

    if placement == "adjacent":
        if (
            output_dir is None
            or output_dir == path_to_dataset
            or pathlib.Path(output_dir)
            == pathlib.Path(os.path.join(path_to_dataset, "derivatives", "petdeface"))
        ):
            final_destination = f"{path_to_dataset}_defaced"
        else:
            final_destination = output_dir

        # copy original dataset to new location, respecting exclusions
        # Use a set to track copied files to avoid duplicates
        copied_files = set()

        for entry in raw_only.files:
            # Check if this file belongs to an excluded subject
            should_exclude = False
            for excluded_subject in participant_label_exclude:
                # Handle both cases: excluded_subject with or without 'sub-' prefix
                if excluded_subject.startswith("sub-"):
                    subject_pattern = f"/{excluded_subject}/"
                    subject_pattern_underscore = f"/{excluded_subject}_"
                else:
                    subject_pattern = f"/sub-{excluded_subject}/"
                    subject_pattern_underscore = f"/sub-{excluded_subject}_"

                if subject_pattern in entry or subject_pattern_underscore in entry:
                    should_exclude = True
                    break

            # Skip excluded subject files, but copy everything else (including dataset-level files)
            if should_exclude:
                continue

            # Create the destination path
            copy_path = entry.replace(str(path_to_dataset), str(final_destination))

            # Check if we've already copied a file with the same basename
            # This prevents duplicates like trc-sf51/pet/file.nii.gz and pet/file.nii.gz
            basename = os.path.basename(entry)
            if basename in copied_files:
                continue

            pathlib.Path(copy_path).parent.mkdir(
                parents=True, exist_ok=True, mode=0o775
            )
            if entry != copy_path:
                shutil.copy(entry, copy_path)
                copied_files.add(basename)

        # update paths in mapping dict
        move_defaced_images(mapping_dict, final_destination)

        # we also want to carry over the defacing masks and registration files
        masks_and_reg = list(
            set(
                layout.get(extension=["mgz", "lta", "png"])
                + layout.get(suffix="defacemask", extension=["nii.gz", "nii", "mgz"])
            )
        )
        derivatives_source_and_dest = {}
        for file in masks_and_reg:
            source_path = pathlib.Path(file.path)
            dest_path = pathlib.Path(
                file.path.replace(str(path_to_dataset), str(final_destination))
            )
            if dest_path.parent.exists() is False:
                dest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o775)
            try:
                shutil.copy(
                    file.path,
                    file.path.replace(str(path_to_dataset), str(final_destination)),
                )
            except shutil.SameFileError:
                pass

    elif placement == "inplace":
        final_destination = path_to_dataset
        move_defaced_images(mapping_dict, final_destination)
        # remove all anat nii's and pet niis from derivatives folder
        inplace_layout = BIDSLayout(path_to_dataset, derivatives=True)
        derivatives = inplace_layout.get(
            suffix=["pet", "T1w"],
            extension=["nii.gz", "nii"],
            desc="defaced",
            return_type="file",
        )
        if str(os.getenv("PETDEFAC_DEBUG", "false")).lower() != "true":
            for extraneous in derivatives:
                os.remove(extraneous)

    elif placement == "derivatives":
        pass
    else:
        raise ValueError(
            "placement must be one of ['adjacent', 'inplace', 'derivatives']"
        )

    if not os.getenv("PETDEFACE_DEBUG"):
        # clean up any errantly leftover files with glob in destination folder
        leftover_files = [
            pathlib.Path(defaced_nii)
            for defaced_nii in glob.glob(
                f"{final_destination}/**/*_defaced*.nii*", recursive=True
            )
        ]
        for leftover in leftover_files:
            leftover.unlink()

    print(f"completed copying dataset to {final_destination}")


def move_defaced_images(
    mapping_dict: dict,
    final_destination: Union[str, pathlib.Path],
    move_files: bool = False,
):
    """
    Moves images created in defacing workflow to final destination given a dictionary mapping
    the defaced images to the original images.

    :param mapping_dict: dictionary mapping defaced images to original images
    :type mapping_dict: dict
    :param final_destination: final destination for defaced images
    :type final_destination: Union[str, pathlib.Path]
    :param move_files: delete defaced images in "working" directory, e.g. move them to the destination dir instead of copying them there, defaults to False
    :type move_files: bool, optional
    """
    # Create a new mapping with destination paths
    dest_mapping = {}

    for defaced, raw in mapping_dict.items():
        # get common path and replace with final_destination to get new path
        common_path = os.path.commonpath([defaced.path, raw.path])
        new_path = pathlib.Path(
            defaced.path.replace(common_path, str(final_destination))
        )

        if "_defaced." in str(new_path):
            new_path = pathlib.Path(str(new_path).replace("_defaced.", "."))

        # replace derivative and pet deface parts of path
        new_path = pathlib.Path(
            *(
                [
                    part
                    for part in new_path.parts
                    if part != "derivatives" and part != "petdeface"
                ]
            )
        )
        dest_mapping[defaced] = new_path

    # copy defaced images to new location
    for defaced, dest_path in dest_mapping.items():
        if pathlib.Path(defaced).exists():
            pathlib.Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(defaced.path, dest_path)

        if move_files:
            os.remove(defaced.path)


class PetDeface:
    """
    Defacing class used to collect inputs, out dirs, perform initial setup, and finally run the defacing workflow.
    """

    def __init__(
        self,
        bids_dir,
        output_dir=None,
        anat_only=False,
        subject="",
        n_procs=2,
        skip_bids_validator=False,
        remove_existing=True,
        placement="adjacent",
        preview_pics=False,
        participant_label_exclude=[],
        session_label=[],
        session_label_exclude=[],
        use_template_anat=False,
    ):
        self.bids_dir = bids_dir
        self.remove_existing = remove_existing
        self.placement = placement
        self.output_dir = output_dir
        self.anat_only = anat_only
        self.subject = subject
        self.n_procs = n_procs
        self.skip_bids_validator = skip_bids_validator
        self.preview_pics = preview_pics
        self.participant_label_exclude = participant_label_exclude
        self.session_label = session_label
        self.session_label_exclude = session_label_exclude
        self.use_template_anat = use_template_anat

        # Build the exclusion indexer
        self.exclude_indexer = self._build_exclusion_indexer()

        # check if freesurfer license is valid
        self.fs_license = check_valid_fs_license()
        if not self.fs_license:
            self.fs_license = locate_freesurfer_license()
            if not self.fs_license.exists():
                raise ValueError("Freesurfer license is not valid")
            else:
                print(
                    f"Using freesurfer license at {self.fs_license} found in system env at $FREESURFER_LICENSE"
                )

    def _build_exclusion_indexer(self):
        """
        Build a comprehensive BIDSLayoutIndexer that excludes subjects and sessions based on:
        1. Explicit exclusion lists (participant_label_exclude, session_label_exclude)
        2. Implicit exclusions from include-only lists (participant_label, session_label)

        Returns:
            BIDSLayoutIndexer: Indexer configured to ignore excluded subjects/sessions
        """
        # Create a temporary layout to get all available subjects and sessions
        temp_layout = BIDSLayout(self.bids_dir, derivatives=False, validate=False)
        all_subjects = temp_layout.get_subjects()
        all_sessions = temp_layout.get_sessions()

        # Start with explicitly excluded subjects
        excluded_subjects = set(self.participant_label_exclude)

        # If specific subjects are requested (include-only), exclude all others
        if self.subject and self.subject != "":
            # Handle both string and list formats
            if isinstance(self.subject, str):
                included_subjects = [self.subject] if self.subject else []
            else:
                included_subjects = self.subject

            # Remove 'sub-' prefix if present
            included_subjects = [sub.replace("sub-", "") for sub in included_subjects]

            # Add all subjects not in the include list to exclusions
            excluded_subjects.update(
                sub for sub in all_subjects if sub not in included_subjects
            )

        # Start with explicitly excluded sessions
        excluded_sessions = set(self.session_label_exclude)

        # If specific sessions are requested (include-only), exclude all others
        if self.session_label:
            # Remove 'ses-' prefix if present
            included_sessions = [ses.replace("ses-", "") for ses in self.session_label]

            # Add all sessions not in the include list to exclusions
            excluded_sessions.update(
                ses for ses in all_sessions if ses not in included_sessions
            )

        # Convert to ignore patterns for BIDSLayoutIndexer
        ignore_patterns = []

        # Add subject exclusion patterns
        ignore_patterns.extend([f"sub-{sub}/*" for sub in excluded_subjects])

        # Add session exclusion patterns
        ignore_patterns.extend([f"*/ses-{ses}/*" for ses in excluded_sessions])

        # Build and return the indexer
        return BIDSLayoutIndexer(ignore=ignore_patterns)

    def run(self):
        """
        Runs the defacing workflow given inputs from instiantiation and wraps up defacing by collecting output
        files and moving them to their final destination.
        """
        deface(
            {
                "bids_dir": self.bids_dir,
                "output_dir": self.output_dir,
                "anat_only": self.anat_only,
                "subject": self.subject,
                "n_procs": self.n_procs,
                "skip_bids_validator": self.skip_bids_validator,
                "participant_label": self.subject,
                "placement": self.placement,
                "remove_existing": self.remove_existing,
                "preview_pics": self.preview_pics,
                "participant_label_exclude": self.participant_label_exclude,
                "session_label": self.session_label,
                "session_label_exclude": self.session_label_exclude,
                "use_template_anat": self.use_template_anat,
            }
        )

        # we want to remove any "t1ws" that we previously substituted in before we copy all
        # of them into the final directory
        global temp_anat_subjects
        for temp_anat_subject in temp_anat_subjects:
            remove_default_anat(bids_dir=self.bids_dir, created_items=temp_anat_subject)

        wrap_up_defacing(
            self.bids_dir,
            self.output_dir,
            placement=self.placement,
            remove_existing=self.remove_existing,
            participant_label_exclude=self.participant_label_exclude,
            session_label_exclude=self.session_label_exclude,
            indexer=self.exclude_indexer,
        )


def cli():
    """
    Argparse based cli for petdeface
    """
    parser = argparse.ArgumentParser(description="PetDeface")

    parser.add_argument(
        "bids_dir", help="The directory with the input dataset", type=pathlib.Path
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        help="The directory where the output files should be stored, if not supplied will default to <bids_dir>/derivatives/petdeface",
        type=pathlib.Path,
        default=None,
    )
    parser.add_argument(
        "analysis_level",
        nargs="?",
        default="participant",
        help="This BIDS app always operates at the participant level, if this argument is changed it will be ignored and run as "
        "a participant level analysis",
    )
    parser.add_argument(
        "--anat_only",
        "-a",
        action="store_true",
        default=False,
        help="Only deface anatomical images",
    )
    parser.add_argument(
        "--participant_label",
        "-pl",
        help="The label(s) of the participant/subject to be processed. When specifying multiple subjects separate them with spaces.",
        type=str,
        nargs="+",
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
        "--singularity",
        "-si",
        action="store_true",
        default=False,
        help="Run in singularity container",
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
        "'adjacent': next to the bids_dir (default) in a folder appended with _defaced"
        "'inplace': defaces the dataset in place, e.g. replaces faced PET and T1w images w/ defaced at bids_dir"
        "'derivatives': does all of the defacing within the derivatives folder in bids_dir.",
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
    parser.add_argument(
        "--preview_pics",
        help="Create preview pictures of defacing, defaults to false for docker",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--participant_label_exclude",
        help="Exclude a subject(s) from the defacing workflow. e.g. --participant_label_exclude sub-01 sub-02",
        type=str,
        nargs="+",
        required=False,
        default=[],
    )
    parser.add_argument(
        "--session_label",
        help="Select only a specific session(s) to include in the defacing workflow",
        type=str,
        nargs="+",
        required=False,
        default=[],
    )
    parser.add_argument(
        "--session_label_exclude",
        help="Select a specific session(s) to exclude from the defacing workflow",
        type=str,
        nargs="+",
        required=False,
        default=[],
    )
    parser.add_argument(
        "--use_template_anat",
        help="Use template anatomical image when no T1w is available for PET scans. Options: 't1' (included T1w template), 'mni' (MNI template), or 'pet' (averaged PET image).",
        type=str,
        required=False,
        default=False,
    )
    parser.add_argument(
        "--open_browser",
        help="Open browser to show QA reports after completion",
        action="store_true",
        default=False,
    )

    arguments = parser.parse_args()
    return arguments


def main():  # noqa: max-complexity: 12
    """
    Main function for petdeface, uses argparse to collect inputs and then runs the defacing workflow and additionally
    performs steps required for running petdeface in docker if the --docker flag is passed. This includes mounting
    the input, output, and freesurfer license as well as creating the command to for docker run to execute the workflow.
    """
    # determine present working directory
    pwd = pathlib.Path.cwd()

    # if this script is being run where this file is located assume that the user wants to mount the code folder
    # into the docker container
    if pwd == pathlib.Path(__file__).parent:
        code_dir = str(pathlib.Path(__file__).parent.absolute())
    else:
        code_dir = None

    args = cli()

    if isinstance(args.bids_dir, pathlib.PosixPath) and "~" in str(args.bids_dir):
        args.bids_dir = args.bids_dir.expanduser().resolve()
    else:
        args.bids_dir = args.bids_dir.absolute()
    if isinstance(args.output_dir, pathlib.PosixPath) and "~" in str(args.output_dir):
        args.output_dir = args.output_dir.expanduser().resolve()
    else:
        if args.output_dir:
            args.output_dir = args.output_dir.absolute()

    if args.docker:
        check_docker_installed()
        check_docker_image_exists("petdeface", build=False)

        # add string to docker command that collects local user id and gid, then runs the docker command as the local user
        # this is necessary to avoid permission issues when writing files to the output directory
        uid = os.geteuid()
        gid = os.getegid()
        system_platform = system()

        input_mount_point = str(args.bids_dir)
        output_mount_point = str(args.output_dir)

        if output_mount_point == "None" or output_mount_point is None:
            output_mount_point = str(args.bids_dir / "derivatives" / "petdeface")

        # create output directory if it doesn't exist
        if not pathlib.Path(output_mount_point).exists():
            pathlib.Path(output_mount_point).mkdir(parents=True, exist_ok=True)
        subprocess.run(f"chown -R {uid}:{gid} {str(output_mount_point)}", shell=True)

        args.bids_dir = pathlib.Path("/input")
        args.output_dir = pathlib.Path("/output")
        print(
            "Attempting to run in docker container, mounting {} to {} and {} to {}".format(
                input_mount_point, args.bids_dir, output_mount_point, args.output_dir
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

        # remove --bids_dir from args_string as input dir is positional, we
        # we're simply removing an artifact of argparse
        args_string = args_string.replace("--bids_dir", "")

        # invoke docker run command to run petdeface in container, while redirecting stdout and stderr to terminal
        docker_command = f"docker run "

        if system_platform == "Linux":
            docker_command += f"--user={uid}:{gid} "

        docker_command += (
            f"-a stderr -a stdout --rm "
            f"-v {input_mount_point}:{args.bids_dir} "
            f"-v {output_mount_point}:{args.output_dir} "
        )
        if code_dir:
            docker_command += f"-v {code_dir}:/petdeface "

        # collect location of freesurfer license if it's installed and working
        try:
            check_valid_fs_license()
        except:
            if locate_freesurfer_license().exists():
                license_location = locate_freesurfer_license()
            else:
                raise FileNotFoundError(
                    "Freesurfer license not found, please set FREESURFER_LICENSE environment variable or place license.txt in FREESURFER_HOME"
                )

            if license_location:
                docker_command += f"-v {license_location}:/opt/freesurfer/license.txt "

        # specify platform
        docker_command += "--platform linux/amd64 "

        docker_command += f"petdeface:latest " f"{args_string}"

        docker_command += f" --user={uid}:{gid}"
        docker_command += f" system_platform={system_platform}"

        print("Running docker command: \n{}".format(docker_command))

        subprocess.run(docker_command, shell=True)

    elif args.singularity:
        singularity_command = f"singularity exec -e"

        if (
            args.output_dir == "None"
            or args.output_dir is None
            or args.output_dir == ""
        ):
            args.output_dir = args.bids_dir / "derivatives" / "petdeface"

        # create output directory if it doesn't exist
        if not args.output_dir.exists():
            args.output_dir.mkdir(parents=True, exist_ok=True)

        # convert args to dictionary
        args_dict = vars(args)
        for key, value in args_dict.items():
            if isinstance(value, pathlib.PosixPath):
                args_dict[key] = str(value)

        args_dict.pop("singularity")

        # remove False boolean keys and values, and set true boolean keys to empty string
        args_dict = {key: value for key, value in args_dict.items() if value}
        set_to_empty_str = [key for key, value in args_dict.items() if value == True]
        for key in set_to_empty_str:
            args_dict[key] = "empty_str"

        args_string = " ".join(
            ["--{} {}".format(key, value) for key, value in args_dict.items() if value]
        )
        args_string = args_string.replace("empty_str", "")

        # remove --bids_dir from args_string as input dir is positional, we
        # we're simply removing an artifact of argparse
        args_string = args_string.replace("--bids_dir", "")

        # collect location of freesurfer license if it's installed and working
        try:
            check_valid_fs_license()
        except:
            if locate_freesurfer_license().exists():
                license_location = locate_freesurfer_license()
            else:
                raise FileNotFoundError(
                    "Freesurfer license not found, please set FREESURFER_LICENSE environment variable or place license.txt in FREESURFER_HOME"
                )

        singularity_command += (
            f" --bind {str(license_location)}:/opt/freesurfer/license.txt"
        )
        singularity_command += f" docker://openneuropet/petdeface:{__version__}"
        singularity_command += f" petdeface"
        singularity_command += args_string

        print("Running singularity command: \n{}".format(singularity_command))

        subprocess.run(singularity_command, shell=True)

    else:
        petdeface = PetDeface(
            bids_dir=args.bids_dir,
            output_dir=args.output_dir,
            anat_only=args.anat_only,
            subject=args.participant_label,
            n_procs=args.n_procs,
            skip_bids_validator=args.skip_bids_validator,
            remove_existing=args.remove_existing,
            placement=args.placement,
            preview_pics=args.preview_pics,
            participant_label_exclude=args.participant_label_exclude,
            session_label=args.session_label,
            session_label_exclude=args.session_label_exclude,
            use_template_anat=args.use_template_anat,
        )
        petdeface.run()

        # Generate QA reports if requested
        print("\n" + "=" * 60)
        print("Generating QA reports...")
        print("=" * 60)

        try:
            # Determine the defaced directory based on placement

            # Run QA
            qa_result = run_qa(
                faced_dir=str(args.bids_dir),
                defaced_dir=str(args.output_dir),
                output_dir=str(args.bids_dir / "derivatives" / "petdeface"),
                subject=(
                    " ".join(args.participant_label) if args.participant_label else None
                ),
                open_browser=args.open_browser,
            )

            print("\n" + "=" * 60)
            print("QA reports generated successfully!")
            print(f"Reports available at: {qa_result['output_dir']}")
            print("=" * 60)

        except Exception as e:
            print(f"\nError generating QA reports: {e}")
            print("QA report generation failed, but defacing completed successfully.")


if __name__ == "__main__":
    main()
