from util import Util
import time

start_time = time.time()
util = Util()
args = util.get_args()
wait_time = 20
sleep_time = 1


def main():
    if args.db_connection is False:
        while time.time() - start_time < wait_time:
            util.test_iqfeed_connection()
            time.sleep(sleep_time)
        util.close("DB Connection is off. So exiting the script. The intention of using this is to connect to IQfeed socket as it drops if it's idle.")

if __name__ == '__main__':
    main()
