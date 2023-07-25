# petdeface
A nipype implementation of an anatomical MR and PET defacing pipeline for BIDS datasets. This is a working prototype,
in active development denoted by the 0.x.x version number. However, it is functional and can be used to deface PET and
MR data as well as co-register the two modalities. Use is encouraged and feedback via Github issues or email to 
openneuropet@gmail.com is more than welcome. As is often the case this medical research software is constrained 
to testing on data that its developers have access to.

This software can be installed via source or via pip from PyPi.

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
```bash
usage: petdeface.py [-h] [--output_dir OUTPUT_DIR] [--anat_only] 
       [--subject SUBJECT] [--session SESSION] [--docker] 
       [--n_procs N_PROCS] [--skip_bids_validator] [--version] 
       [--placement PLACEMENT] [--remove_existing] input_dir

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
                        Where to place the defaced images. Options are 
                        'adjacent': next to the input_dir (default) in a folder appended with _defaced
                        'inplace': defaces the dataset in place, e.g. replaces faced PET and T1w images 
                        w/ defaced at input_dir
                        'derivatives': does all of the defacing within the derivatives folder in input_dir.
  --remove_existing, -r Remove existing output files in output_dir.
```

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
2. Gorgolewski, Krzysztof J. ; Esteban, Oscar ; Burns, Christopher ; Ziegler, Erik ; Pinsard, Basile ; Madison, Cindee ; 
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

