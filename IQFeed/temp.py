import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--debug", "-d", action='store_true', default=False, help="Debug")


try:
    args = parser.parse_args()
except IOError as msg:
    parser.error(str(msg))

print (args.debug)
