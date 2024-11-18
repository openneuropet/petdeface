# petdeface

A nipype implementation of an anatomical MR and PET defacing pipeline for BIDS datasets. This is a working prototype,
in active development denoted by the 0.x.x version number. However, it is functional and can be used to deface PET and
MR data as well as co-register the two modalities. Use is encouraged and feedback via Github issues or email to
openneuropet@gmail.com is more than welcome. As is often the case, this medical research software is constrained
to testing on data that its developers have access to.

This software can be installed via source or via pip from PyPi with `pip install petdeface`

---

| CI  | Status |   
|---------| ------ |
| `docker build . -t petdeface` | ![docker_build](https://codebuild.us-east-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiYzdXV0tYSkQzTVNkcG04cHA2S055UXlKRlZTU1VONThUMVRoZVcwU3l1aHFhdVBlNDNaRGVCYzdWM1Q0WjYzQ1lRU2ZTSHpmSERPWFRkVXVyb3k3RTZBPSIsIml2UGFyYW1ldGVyU3BlYyI6IjRCZFFIQnNGT2lKcDA1VG4iLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=main) |
| `docker push` | ![docker push icon](https://codebuild.us-east-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoia0c1bEJYUGI2SXlWYi9JMm1tcGtiYWVTdVd3bmlnOUFaTjN4QjJITU5PTVpvQnN3TlowajhxNmhHY2RwQ2Z5SU93OExqc2xvMzFnTHFvajlqVk1MV2FzPSIsIml2UGFyYW1ldGVyU3BlYyI6Ikl6SzRyc1RabzBnSkplTjciLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=main) |

## Requirements

### Non-Python Dependencies

- FreeSurfer and MiDeFAce >= 7.3.2
  - https://surfer.nmr.mgh.harvard.edu/
  - https://surfer.nmr.mgh.harvard.edu/fswiki/MiDeFace

### Python Dependencies

- nipype >= 1.6.0
  - https://nipype.readthedocs.io/en/latest/
- pybids

*for a full list of dependencies see the pyproject.toml in this repo*

## Usage
**_NOTE:_** This project is currently in beta release, some features listed below may not be available for version numbers < 1.0.0

```bash
usage: petdeface.py [-h] [--anat_only] [--participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [--docker] [--singularity] [--n_procs N_PROCS]
                    [--skip_bids_validator] [--version] [--placement PLACEMENT] [--remove_existing] [--preview_pics]
                    [--participant_label_exclude participant_label_exclude [participant_label_exclude ...]] [--session_label SESSION [SESSION ...]]
                    [--session_label_exclude session_label_exclude [session_label_exclude ...]]
                    bids_dir [output_dir] [analysis_level]

PetDeface

positional arguments:
  bids_dir              The directory with the input dataset
  output_dir            The directory where the output files should be stored, if not supplied will default to <bids_dir>/derivatives/petdeface
  analysis_level        This BIDS app always operates at the participant level, if this argument is changed it will be ignored and run as a participant level
                        analysis

options:
  -h, --help            show this help message and exit
  --anat_only, -a       Only deface anatomical images
  --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], -pl PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                        The label(s) of the participant/subject to be processed. When specifying multiple subjects separate them with spaces.
  --docker, -d          Run in docker container
  --singularity, -si    Run in singularity container
  --n_procs N_PROCS     Number of processors to use when running the workflow
  --skip_bids_validator
  --version, -v         show program's version number and exit
  --placement PLACEMENT, -p PLACEMENT
                        Where to place the defaced images. Options are 'adjacent': next to the bids_dir (default) in a folder appended with _defaced'inplace':
                        defaces the dataset in place, e.g. replaces faced PET and T1w images w/ defaced at bids_dir'derivatives': does all of the defacing within
                        the derivatives folder in bids_dir.
  --remove_existing, -r
                        Remove existing output files in output_dir.
  --preview_pics        Create preview pictures of defacing, defaults to false for docker
  --participant_label_exclude participant_label_exclude [participant_label_exclude ...]
                        Exclude a subject(s) from the defacing workflow. e.g. --participant_label_exclude sub-01 sub-02
  --session_label SESSION [SESSION ...]
                        Select only a specific session(s) to include in the defacing workflow
  --session_label_exclude session_label_exclude [session_label_exclude ...]
                        Select a specific session(s) to exclude from the defacing workflow
```

Working example usage:

```bash
petdeface /inputfolder /outputfolder --n_procs 16 --skip_bids_validator --placement adjacent
```

### Docker Usage

Requirements:
- Docker must be installed and access to `docker run` must be available to the current user
- `openneuropet/petdeface` must be present or reachable at dockerhub from the machine the cli is installed at, e.g. `docker pull openneuropet/petdeface` must work
- if one is unable to pull the image on can build locally with `make dockerbuild`

**_NOTE:_** The docker image for petdeface is not intended to be used by itself, but instead accessed via the `petdeface` command line written in Python.

Appending the `--docker` after including all of the required arguments for petdeface will 
automatically launch the dockerized version of this application, no additional input after
that is required.

**Running directly with Docker, no Python, no installation:**

If you run without using the CLI you will need to:
- bind the input and output volumes to the container
- bind a freesurfer license to the container at `/opt/freesurfer/license.txt`
- provide all of the arguments you would normally need to provide to the Python CLI
- provide $UID and $GID if running on linux so that your output isn't written as root, you may disregard this if you're handy.

An example of the command generated from the Python cli to run the docker based version can
be seen below:

```bash
docker run --user=$UID:$GID -a stderr -a stdout --rm \
-v /Data/faced_pet_data/:/input \
-v /Data/defaced_pet_data/:/output \
-v /home/freesurfer/license.txt:/opt/freesurfer/license.txt \
--platform linux/amd64 \
petdeface:latest  /input /output --n_procs 16 --skip_bids_validator  --placement adjacent --user=$UID:$GID system_platform=Linux
```

### Singularity Usage

Requirements:
  - Singularity must be installed
  - `openneuropet/petdeface` must be present or reachable at dockerhub

One can execute petdeface in singularity either directly via:

```bash
singularity exec -e --bind license.txt:/opt/freesurfer/license.txt docker://openneuropet/petdeface:0.1.1 petdeface
```

Input and Output directories don't need to be bound, but one does need to bind a freesurfer license to the image before they can proceed with defacing.
Otherwise, one can run and execute petdeface with the same syntax as calling it from the command line, the only difference being that petdeface is prepended
with `singularity exec -e`

```bash
singularity exec -e --bind license.txt:/opt/freesurfer/license.txt docker://openneuropet/petdeface:0.1.1 petdeface /input /output --n_procs 10
```

**_NOTE_**: Testing with singularity has been limited to version singularity-ce 4.2.0, please let us know in the issues section of this repo if you have 
trouble running this container in singularity/apptainer.

## Development

This project uses poetry to package and build, to create a pip installable version of the package run:

```bash
git clone https://github.com/openneuropet/petdeface.git
cd petdeface
poetry build
pip install dist/petdeface-<X.X.X>-py3-none-any.whl # where X.X.X is the version number of the generated file
```

Then install the tar or wheel file created in `dist`:

```bash
pip install petdeface-<X.X.X>-py3-none-any.whl # where X.X.X is the version number of the generated file
```

## Citations

1. Dale A, Fischl B, Sereno MI. Cortical Surface-Based Analysis: I. Segmentation and Surface Reconstruction.
   Neuroimage. 1999;9(2):179–94. doi:10.1006/nimg.1998.0395.
2. Fischl B. FreeSurfer. Neuroimage. 2012 Aug 15;62(2):774-81. doi: 10.1016/j.neuroimage.2012.01.021.
   Epub 2012 Jan 10. PMID: 22248573; PMCID: PMC3685476.
3. Stefano Cerri, Douglas N. Greve, Andrew Hoopes, Henrik Lundell, Hartwig R. Siebner, Mark Mühlau, Koen Van Leemput,
   An open-source tool for longitudinal whole-brain and white matter lesion segmentation,
   NeuroImage: Clinical, Volume 38, 2023, 103354, ISSN 2213-1582, https://doi.org/10.1016/j.nicl.2023.103354.
   (https://www.sciencedirect.com/science/article/pii/S2213158223000438)
4. Gorgolewski, Krzysztof J. ; Esteban, Oscar ; Burns, Christopher ; Ziegler, Erik ; Pinsard, Basile ; Madison, Cindee ;
   Waskom, Michael ; Ellis, David Gage ; Clark, Dav ; Dayan, Michael ; Manhães-Savio, Alexandre ;
   Notter, Michael Philipp ; Johnson, Hans ; Dewey, Blake E ; Halchenko, Yaroslav O. ; Hamalainen, Carlo ;
   Keshavan, Anisha ; Clark, Daniel ; Huntenburg, Julia M. ; Hanke, Michael ; Nichols, B. Nolan ; Wassermann , Demian ;
   Eshaghi, Arman ; Markiewicz, Christopher ; Varoquaux, Gael ; Acland, Benjamin ; Forbes, Jessica ; Rokem, Ariel ;
   Kong, Xiang-Zhen ; Gramfort, Alexandre ; Kleesiek, Jens ; Schaefer, Alexander ; Sikka, Sharad ;
   Perez-Guevara, Martin Felipe ; Glatard, Tristan ; Iqbal, Shariq ; Liu, Siqi ; Welch, David ; Sharp, Paul ;
   Warner, Joshua ; Kastman, Erik ; Lampe, Leonie ; Perkins, L. Nathan ; Craddock, R. Cameron ; Küttner, René ;
   Bielievtsov, Dmytro ; Geisler, Daniel ; Gerhard, Stephan ; Liem, Franziskus ; Linkersdörfer, Janosch ;
   Margulies, Daniel S. ; Andberg, Sami Kristian ; Stadler, Jörg ; Steele, Christopher John ; Broderick, William ;
   Cooper, Gavin ; Floren, Andrew ; Huang, Lijie ; Gonzalez, Ivan ; McNamee, Daniel ; Papadopoulos Orfanos, Dimitri ;
   Pellman, John ; Triplett, William ; Ghosh, Satrajit (2016). Nipype: a flexible, lightweight and extensible
   neuroimaging data processing framework in Python. 0.12.0-rc1. Zenodo. 10.5281/zenodo.50186
