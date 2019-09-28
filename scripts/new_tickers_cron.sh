#!/bin/bash
echo "Received arguments": $@

/home/rdepaola/myproject/scripts/cron.sh --new --timeframes 5 15 60 --daily 1 7 --force4hr --update_tickers --update_signals "$@"
