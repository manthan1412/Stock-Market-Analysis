from util import Util
import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
import traceback

util = Util(socket_connection=False)
script_run_time = 300


def was_iqfeed_okay(cursor, current_time, args):
    data = util.query_select("select last_on from {0} where version='{1}' order by last_on desc limit 1".format(args.table_name, args.version))
    util.log(data)
    if not data or not data[0]:
        return False, False
    last_time = data[0][0]
    util.log("Last on ", current_time - last_time, "minutes ago")
    return True, False if (current_time - last_time).seconds > script_run_time else True


def update_last_on_iqfeed_time(util, current_time, has_data, args):
    if has_data:
        util.query_update("Update {0} set last_on='{1}' where version='{2}'".format(args.table_name, str(current_time), args.version), commit=args.do_not_store)
    else:
        util.query_insert("Insert into {0}(last_on, version) values('{1}', '{2}')".format(args.table_name, str(current_time, args.version)), commit=args.do_not_store)


def check_iq_feed_status():
    current_time = datetime.now()
    current_time = util.localize(current_time - relativedelta(seconds=current_time.second, microseconds=current_time.microsecond))
    args = util.get_args()
    args.do_not_store = not args.fetch
    has_data, was_okay = was_iqfeed_okay(util, current_time, args)
    util.log("Has data:", has_data, "\tWas okay:", was_okay)

    if was_okay is False:
        util.report_fault('Seems like IQFeed is in idle state or not working. Trying to restart.', app_notification=True)
        util.start_iqfeed()
    util.establish_iqfeed_socket_connection()
    message = "HTD\r\n"
    util.send_to_socket(message.encode("utf-8"))

    # expect to receive error message from sock if iqfeed connection is working fine,
    # it will go into waiting state otherwise.
    buffer = util.receive_from_socket(recv_buffers=4096)
    update_last_on_iqfeed_time(util, current_time, has_data, args)
    if was_okay is False:
        util.report_fault('IQFeed restarted successfully.', app_notification=True)


if __name__ == "__main__":
    check_iq_feed_status()
