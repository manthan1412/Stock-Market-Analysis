from util import Util

util = Util()
args = util.get_args()


def main():
    if args.db_connection is False:
        util.test_iqfeed_connection()
        util.close("DB Connection is off. So exiting the script. The intention of using this is to connect to IQfeed socket as it drops if it's idle.")

if __name__ == '__main__':
    main()
