#!/bin/bash

wait() {
    wait_loop=15
    loop_time=1
    status=$(pgrep -f "$1")
    while [ $? -eq 0 ]
    do
        sleep $loop_time
        wait_loop=$((wait_loop-loop_time))
        if [ $wait_loop -lt 0 ]; then
            echo "killing"
            pkill -9 -f "$1"
            break
        fi
        status=$(pgrep -f "$1")
    done
}
