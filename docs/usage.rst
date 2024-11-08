.. _usage:

Usage
=====

General
-------

After installation PETdeface can be run from as follows::

    petdeface /inputfolder --output_dir /outputfolder

.. raw:: html

    <script async id="asciicast-626691" src="https://asciinema.org/a/626691.js"
    async data-autoplay="true" data-speed="1.5" data-loop="true"></script>

Given a PET BIDS dataset like below::

    tree /inputfolder
    .
    ├── README
    ├── dataset_description.json
    └── sub-PS50
        ├── anat
        │   ├── sub-PS50_T1w.json
        │   └── sub-PS50_T1w.nii
        ├── ses-baseline
        │   └── pet
        │       ├── sub-PS50_ses-baseline_pet.json
        │       └── sub-PS50_ses-baseline_pet.nii.gz
        └── ses-blocked
            └── pet
                ├── sub-PS50_ses-blocked_pet.json
                └── sub-PS50_ses-blocked_pet.nii.gz

    6 directories, 8 files

The following output will be produced::

    tree /outputfolder
    /outputfolder
    ├── README
    ├── dataset_description.json
    ├── derivatives
    │   └── petdeface
    │       └── sub-PS50
    │           ├── anat
    │           │   ├── sub-PS50_T1w_defacemask.nii
    │           │   ├── sub-PS50_desc-faceafter_T1w.png
    │           │   └── sub-PS50_desc-facebefore_T1w.png
    │           ├── ses-baseline
    │           │   └── pet
    │           │       └── sub-PS50_ses-baseline_desc-pet2anat_pet.lta
    │           └── ses-blocked
    │               └── pet
    │                   └── sub-PS50_ses-blocked_desc-pet2anat_pet.lta
    └── sub-PS50
        ├── anat
        │   ├── sub-PS50_T1w.json
        │   └── sub-PS50_T1w.nii
        ├── ses-baseline
        │   └── pet
        │       ├── sub-PS50_ses-baseline_pet.json
        │       └── sub-PS50_ses-baseline_pet.nii.gz
        └── ses-blocked
            └── pet
                ├── sub-PS50_ses-blocked_pet.json
                └── sub-PS50_ses-blocked_pet.nii.gz

    14 directories, 13 files

Previously faced files are replaced with defaced images while the registration, mask files, and before and after photos are stored in the derivatives folder.

When viewed, a succesfully defaced PET image will have varying intensities in the face region, as shown below:

.. image:: /_static/sagittal.gif
    :align: left

-----------------

The number of processors made available to PETdeface can be set by the `--n_procs`  flag e.g.::

    petdeface /inputfolder --output_dir /outputfolder --n_procs 4

Additional options can be found in the help menu::

    petdeface -h
    usage: petdeface [-h] [--output_dir OUTPUT_DIR] [--anat_only] [--subject SUBJECT] [--session SESSION] [--docker] [--n_procs N_PROCS] [--skip_bids_validator] [--version]
                 [--placement PLACEMENT] [--remove_existing]
                 input_dir

    PetDeface

    positional arguments:
    input_dir             The directory with the input dataset

    options:
    -h, --help            show this help message and exit
    --output_dir OUTPUT_DIR, -o OUTPUT_DIR
                            The directory where the output files should be stored
    --anat_only, -a       Only deface anatomical images
    --subject SUBJECT, -s SUBJECT
                            The label of the subject to be processed.
    --session SESSION, -ses SESSION
                            The label of the session to be processed.
    --docker, -d          Run in docker container
    --n_procs N_PROCS     Number of processors to use when running the workflow
    --skip_bids_validator
    --version, -v         show program's version number and exit
    --placement PLACEMENT, -p PLACEMENT
                            Where to place the defaced images. Options are 'adjacent': next to the input_dir (default) in a folder appended with _defaced'inplace': defaces the dataset in place,
                            e.g. replaces faced PET and T1w images w/ defaced at input_dir'derivatives': does all of the defacing within the derivatives folder in input_dir.
    --remove_existing, -r
                            Remove existing output files in output_dir.
    --excludesubject EXCLUDESUBJECT [EXCLUDESUBJECT ...]
                        Exclude a subject(s) from the defacing workflow. e.g. --excludesubject sub-01 sub-02

Docker Based
------------

PETdeface can be run in a docker container using the `--docker` flag::

    petdeface /inputfolder --output_dir /outputfolder --docker

Alternatively, if one is unable to install PETdeface from source or PIP, but can execute running a docker image they can run this pipeline usin the syntax below::

    docker run --user=$UID:$GID -a stderr -a stdout --rm \
    -v /Data/faced_pet_data/:/input \
    -v /Data/defaced_pet_data/:/output \
    -v /home/user/freesurfer/license.txt:/opt/freesurfer/license.txt \
    --platform linux/amd64 \
    petdeface:latest  /input \
    --output_dir /output \
    --n_procs 16 \
    --skip_bids_validator \
    --placement adjacent \
    --user=$UID:$GID \
    system_platform=Linux

One needs to create 3 bind mounts to the docker container when running PETdeface directly from docker:

1. /input needs to mounted to the input BIDS dataset on the host machine
2. /output needs to be mounted to the output directory on the host machine
3. /opt/freesurfer/license.txt needs to be mounted to the freesurfer license file on the host machine

If one is running PETdeface on a linux machine and desires non-root execution of the container, 
the ``--user`` flag needs to be set to the UID and GID of the user running the container.

Of course all of the above is done automatically when running PETdeface using the ``--docker`` flag.