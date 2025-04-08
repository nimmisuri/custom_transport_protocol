import sys
import datetime
import time

#shows current time in seconds
def currentTime():
    
    return time.time()

#logs with timestamp
def log(string):
    
    sys.stderr.write("{timestamp} {msg}\n".format(
        timestamp=datetime.datetime.now().strftime("%H:%M:%S.%f"),
        msg=string
    ))

#wraps sequence number back to 0 at 2^32
def wrapSequence(sequence, data=None):

    data_length = len(data) if data is not None else 0
    return (sequence + data_length) % (2**32 - 1)