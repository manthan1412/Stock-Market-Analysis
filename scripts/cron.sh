#!/bin/bash

. /home/rdepaola/myproject/scripts/at_start.sh

at_start
echo "Cron received arguments": $@
/home/rdepaola/myproject/myprojectenv/bin/python /home/rdepaola/myproject/cron/cron.py "$@"
