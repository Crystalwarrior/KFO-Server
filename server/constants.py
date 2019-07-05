import time

from enum import Enum

class TargetType(Enum):
        #possible keys: ip, OOC, id, cname, ipid, hdid
        IP = 0
        OOC_NAME = 1
        ID = 2
        CHAR_NAME = 3
        IPID = 4
        HDID = 5
        ALL = 6

class Constants():
    def get_time():
        return time.asctime(time.localtime(time.time()))

    def get_time_iso():
        return time.strftime('[%Y-%m-%dT%H:%M:%S]')

    def time_remaining(start, length):
        current = time.time()
        remaining = start+length-current
        return remaining, Constants.time_format(remaining)

    def time_elapsed(start):
        current = time.time()
        return Constants.time_format(current-start)

    def time_format(length):
        if length < 10:
            text = "{} seconds".format('{0:.1f}'.format(length))
        elif length < 60:
            text = "{} seconds".format(int(length))
        elif length < 3600:
            text = "{}:{}".format(int(length//60),
                                  '{0:02d}'.format(int(length%60)))
        else:
            text = "{}:{}:{}".format(int(length//3600),
                                     '{0:02d}'.format(int((length%3600)//60)),
                                     '{0:02d}'.format(int(length%60)))
        return text
