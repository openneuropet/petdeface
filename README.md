# petdeface
A nipype implementation of an anatomical MR and PET defacing pipeline for BIDS datasets

## Usage
```bash
usage: petdeface.py [-h] [--output_dir OUTPUT_DIR] [--anat_only] [--subject SUBJECT] 
       [--session SESSION] [--docker] [--n_procs N_PROCS] [--skip_bids_validator] 
       [--version] input_dir

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
```

## Development

This project uses poetry to package and build, to create a pip installable version of the package run:

```bash
git clone https://github.com/bendhouseart/petdeface.git
cd petdeface
poetry build
```

Then install the tar or wheel file created in `dist`:

```bash
pip install petdeface-<X.X.X>-py3-none-any.whl # where X.X.X is the version number of the generated file
```

