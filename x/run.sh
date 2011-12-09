#!/bin/bash

if [ $# != 1 ]; then
    echo "Usage: $0 USER PROGRAM"
    echo "Runs PROGRAM as USER in Xvfb."
    exit 1
fi

cd `dirname $0`

xvfb-run -n 19 -f Xauthority --server-args="-screen 0 448x240x24 -fbdir ." \
    $1 &
PID_XVFB_RUN=$!

XAUTHORITY=Xauthority x11vnc -display :19 &

while ! ls Xvfb_screen0 >/dev/null; do sleep .1; done

./xdisp Xvfb_screen0 &
PID_XDISP=$!

sleep 2
vncviewer localhost:5900

kill $PID_XDISP
pkill -P $PID_XVFB_RUN
rm Xauthority
