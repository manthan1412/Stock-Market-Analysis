#!/bin/bash

. /home/rdepaola/myproject/scripts/at_start.sh
. /home/rdepaola/myproject/scripts/wait.sh

connect_to_iqfeed() {
    /home/rdepaola/myproject/myprojectenv/bin/python /home/rdepaola/myproject/cron/connect_to_iqfeed.py --no-db_connection --update_tickers & wait "connect_to_iqfeed.py"
}

at_start
connect_to_iqfeed;
sleep 29;
connect_to_iqfeed;
