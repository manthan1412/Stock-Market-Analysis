#!/bin/bash

echo
date
source /home/rdepaola/myproject/environments/environment.sh
/home/rdepaola/myproject/myprojectenv/bin/python /home/rdepaola/myproject/cron/cron.py --delay
