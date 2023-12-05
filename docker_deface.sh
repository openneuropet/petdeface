#!/bin/bash

GIVEN_INPUT=$*
trap own_files ERR INT

own_files()
{
    platform=$(echo $GIVEN_INPUT | grep -oP 'system_platform=\K[^&]*')
    # if uid or gid is present in GIVEN_INPUT collect them and assign to variables
    if [[ $GIVEN_INPUT == *uid* ]]
    then
        uid=$(echo $GIVEN_INPUT | grep -oP 'uid=\K[0-9]*')
    fi
    if [[ $GIVEN_INPUT == *gid* ]]
    then
        gid=$(echo $GIVEN_INPUT | grep -oP 'gid=\K[0-9]*')
    fi

    # dont run any of this if the host system that initiated this container isn't linux as 
    # docker running on windows or mac handles file ownership differently and we just don't 
    # need to worry about root owning files there.
    if [[ $platform != 'Linux' ]]
    then
        echo "Host system is not linux. Not changing ownership of files at /output directory"
        exit 0
    fi

    echo "petdeface container main process exited with code $?."
    echo "Changing ownership of files at /output directory to uid: $uid and gid: $gid"
    chown $uid:$gid /output/
    chown -R $uid:$gid /output
}

# run the python command minus the gid and uid arguments
GIVEN_INPUT_MINUS_UID_GID_PLATFORM=$(echo $GIVEN_INPUT | sed -e 's/uid=[0-9]*//' -e 's/gid=[0-9]*//' -e 's/system_platform=[^&]*//')
echo Command executing in Container: $GIVEN_INPUT_MINUS_UID_GID_PLATFORM
eval $GIVEN_INPUT_MINUS_UID_GID_PLATFORM

# own files in /output directory
own_files
