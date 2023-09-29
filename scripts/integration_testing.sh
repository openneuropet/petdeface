#! /usr/bin/env bash

SCRIPT_PATH=$(dirname $(realpath -s $0))
REPO_PATH=$(dirname $SCRIPT_PATH)

while getopts 'r' flag
do
    case "$flag" in
        r) rebuildimage=true ;;
    esac

    case "$flag" in
        o) outputdir=${OPTARG} ;;
    esac

done

if [[ -n "$rebuildimage" ]]
#if $rebuildimage
then
    echo "rebuilding docker image"
    pushd $REPO_PATH
    docker build . -t petdeface
else
    echo "Using existing petdeface docker image"
fi

shift $(($OPTIND - 1))
INPUT_DIR=$1
OUTPUT_DIR=$2

echo Removing contents of existing output directory at $OUTPUT_DIR
mkdir -p $OUTPUT_DIR
rm -rf $OUTPUT_DIR/*

echo running the following command:
echo python3 petdeface/petdeface.py $INPUT_DIR \
--output $OUTPUT_DIR \
--n_procs 16 \
--skip_bids_validator \


python3 petdeface/petdeface.py $INPUT_DIR \
--output $OUTPUT_DIR \
--n_procs 16 \
--skip_bids_validator \
