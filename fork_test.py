import os
import time
import subprocess
from multiprocessing import Process
import multiprocessing as mp
import psutil

def func():
    if os.fork() != 0:  # <--
        return          # <--
    print('sub process is running')
    time.sleep(5)
    print('sub process finished')  
def runShell(cmd):
    print(cmd)
    pid = os.getpid()
    filename=str(pid) + '_' + 'test_popen.log'
    f=open(filename,"w")
    
    # name=str(pid) + 'runShell'
    p = subprocess.Popen(cmd, shell=True,stdout=f,stderr=subprocess.STDOUT ) 
#    print(p)
    print(p.pid)
#    p.wait()
    f.close()
    return p.pid
        
    #f.close
def tmp(cmd):
    print(cmd)

def foo(max):
    i = 1
    while i < max:
        print(i,flush)
        time.sleep(4)
        i +=1
def kill(pid=None):
    if os.name == 'nt':
        os.system('taskkill /F /PID ' + str(pid) )
    else:
        os.system('kill -9 '  + str(pid))


if __name__ == '__main__':
    # detach sub process
    cmd='python3 ./workload1.py'

#    p = Process(target=runShell,args=(cmd,), daemon=True)
    pid = os.getpid()
    filename=str(pid) + '_' + 'test_popen.log'
    print(filename)
    f=open(filename,"w")
    p = subprocess.Popen(cmd, shell=True,stdout=f,stderr=subprocess.STDOUT ) 
    print(p.pid)
    #p.start()
    count = 1
    while psutil.pid_exists(p.pid):
        print("runShell: " + str(p.pid) + " Count: " + str(count) )

        if count > 5:
            kill(p.pid)
        count += 1
        time.sleep(1)

   
    print('exit')                                       

#    p = Process(target=func)
#    p.start()
#    p.join()
#    print('done')