#!/bin/bash

if [ ! $# -eq 2 ]; then
    echo "$0 -- Prints NUMBER lines every TIME seconds from standard input" \
        "to standard output."
    echo "Usage: $0 NUMBER TIME"
    exit 1
fi

LINES_AT_ONCE=$1
INTERVAL_IN_SECONDS=$2

while [ 1 ]; do
    for (( i=0 ; i<$LINES_AT_ONCE; i++ )); do
        read input
        echo $input
    done
    sleep $INTERVAL_IN_SECONDS
done
