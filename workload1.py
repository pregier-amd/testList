from signal import raise_signal
import time
import os
import sys

def foo(data=2):
        i = 1
        while i <= data:
           print(i,flush=True)
           time.sleep(2)
           i += 1
           if i == 50:
               # inject error
               print ("Inject Error:" + str(i))
               sys.exit(12)
        return int(0)
print('start')
print("PID: " + str(os.getppid())  )

rc = foo(45)
sys.exit(rc)
