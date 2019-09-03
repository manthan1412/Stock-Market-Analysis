#!/bin/bash

wait() {
    wait_loop=290
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

date
source /home/rdepaola/myproject/environments/environment.sh
/home/rdepaola/myproject/myprojectenv/bin/python /home/rdepaola/myproject/cron/iqfeed_status.py --version 6.0.0.5 --table_name stocks_iqfeedstatus & wait "iqfeed_status.py"
