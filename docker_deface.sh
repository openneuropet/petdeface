#!/bin/bash

GIVEN_INPUT=$*
trap own_files ERR INT

own_files()
{
    local command_status=$?
    local platform uid gid

    platform=$(echo $GIVEN_INPUT | grep -oP 'system_platform=\K[^&]*')
    # if UID or GID is present in GIVEN_INPUT collect them and assign to variables
    if [[ $GIVEN_INPUT == *\-\-user=* ]]
    then
        uid=$(echo $GIVEN_INPUT | grep -oP '\-\-user=\K[0-9]*')
        gid=$(echo $GIVEN_INPUT | grep -oP '\-\-user=[0-9]*:\K[0-9]*')
    fi

    # Only Docker on Linux needs ownership correction. Apptainer/Singularity
    # normally runs as the invoking user and does not provide this metadata.
    # windows and mac handle permissions via their docker VM's
    if [[ $platform != 'Linux' || -z $uid || -z $gid ]]
    then
        return 0
    fi
    
    echo "petdeface container main process exited with code $command_status."
    echo "Changing ownership of files at /output directory to UID: $uid and GID: $gid"
    chown "$uid:$gid" /output/
    chown -R "$uid:$gid" /output

}

# run the python command minus the GID and UID arguments
echo Command Given: $GIVEN_INPUT
GIVEN_INPUT_MINUS_UID_GID_PLATFORM=$(echo $GIVEN_INPUT | sed -e 's/--user=[0-9]*:[0-9]*//' -e 's/system_platform=[^&]*//')
own_files
echo Command executing in Container: $GIVEN_INPUT_MINUS_UID_GID_PLATFORM
eval $GIVEN_INPUT_MINUS_UID_GID_PLATFORM

# own files in /output directory
own_files
