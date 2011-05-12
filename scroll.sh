#!/bin/bash

while [ 1 ]; do
    sleep 5
    for (( i=0 ; i<20 ; i++ )); do
        read asd
        echo $asd
    done
done
