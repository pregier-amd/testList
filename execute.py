import logging
import argparse
import multiprocessing as mp
from subprocess import Popen, PIPE, STDOUT
from types import NoneType
import psutil
import subprocess
import time
from datetime import datetime
import pytz
from LogClass import LogClass
import yaml
import os
import re
import json

class execute(object):
   
    def __init__(self,filename=None ): 
        if not filename:
            self.runlog = 'runlog.log'
        else:
            self.runlog = filename
        self.lock_log_dir = '.\\'
        self.lockFilename = 'lock.yml'
        self.execFilename = 'exec.log'
        # apply directory to filenames
        self.set_dir(self.lock_log_dir)
        self.proc_name    = 'Exec Workload'
        self.lock_data = None
        self.loop_checkpoint_timeout = 2
        self.exec_limit = None
        self.notes = None
       
        # Logger
        
        log = LogClass(None,"log\execute.log",False)
        self.logger = log.logger
        self.logger.setLevel('WARNING')

    def set_dir(self,data=None):
       
        self.lockFilename = self.clean_dir(data + '/' + os.path.basename(self.lockFilename) )
        self.execFilename = self.clean_dir(data + '/' + os.path.basename(self.execFilename) )

    def clean_dir(self,data):
        data = data.replace('//','/').strip()
        return data

    def run(self,args=None):

        # Check if Last Run Complete:
        # isbusy = lock data  when busy, 
        # isbusy = None    free 
        lockdata ,busy_filename = self.check_isbusy(self.lockFilename)
        lockinfo ={'lockProc': lockdata, 'locFile': busy_filename}

        # Set Check for Busy, if not then launch the provided workload.
        if lockdata:
            status = 'Busy'

        else:    
            # Launch the provided Workload
            # Returns the Shell PID
            lock_proc = self.launch(args)
            #Retun a Fail status if both the Workload or  Monitor Tasks fail to start. 
            if not lock_proc:
                self.logger.error("Failed to Launch Workload " )
                status = 'Fail'
            else:
                # Expected state of new Workload running.
                status = 'Running'
                lockinfo = {'locProc': self.exec_sub_pid ,'lockFile': self.full_lock_filename}

        return status, lockinfo

    def check_isbusy(self,filename=None):
        result = None
        directory = os.path.dirname(filename)
        file_list = os.listdir(directory)
        busy_fname = None
        for fname in file_list:
            m = re.match('.*' + os.path.basename(filename),fname)
            if m:
                self.logger.debug('Check File: ' + str(m) )
                # Check for status = 'end' for not Busy
                full_fname = os.path.join(directory, fname)
                try:
                    data = self.read_yaml(full_fname )
                except Exception as e:
                    self.logger.error("Skipping Malformed Yaml File:" + str( fname)  )
                    next
                for row in data:
                    if 'status' in row:
                        if not row['status'] == 'end':
                            result = data
                            busy_fname = fname
                            alive = "Not Running"
                            if psutil.pid_exists(row['pid']):
                                alive = "Running"
                            self.logger.warning("Lock File is Busy:" + "\nStatus:" + row['status'] )  
                            self.logger.warning('filename:' + str(full_fname))  
                            self.logger.warning('PID: ' + str( row['pid'] ) + ' PID Status:' + alive)  
        if busy_fname:
            self.logger.warning("Options: Kill the Busy Processes(See Files PID), or if not running remove the file.\n\n\n")
        return result,busy_fname

    def calc_duration(self,start=None,end=None,prec=3):
        duration = None
        if not end:
            end = time.time()
        # duration in Seconds
        if start:
            duration = round(end - start,prec)

        return duration

        
    def cleanup(self,filename,proc=None):
        proc.terminate()
        result = self.manage_lockfile(filename,'remove')
        return result

    def frmt_fname(self,filename=None,uuid=None):
        dirname   = os.path.dirname(os.path.abspath(filename))
        basename  = os.path.basename(filename)
        #Assemble the Path + uuid + "_" + Basename + extension
        data =  dirname + '/'
        if uuid:
            data = data +  str(uuid) + '_'
        
        data = data + basename 
        return data

    
    def read_yaml(self,filename):
        if not os.path.isfile(filename):
            return
        data =[]
        try:
            with open(filename, 'r') as file:
                docs = yaml.safe_load_all(file)
                for doc in docs:
                    data.append(doc)
        except:
            self.logger.error('Failed to read Yaml file: ' + filename)
            data = []

        return data

    def write_yaml(self,filename=None,data=None,mode='w'):
        if not filename:
            return
        with open(filename, 'w') as file:
           yaml.dump(data, file)

    def info(self,title):
        print(title)
        print('module name:', __name__)
        print('parent process:', os.getppid())
        print('process id:', os.getpid())
    
    def launch(self,args=None):
        self.info("Launched workload")
       # mp.set_start_method('fork',force=True)

       # open execution Log
        # Use the File name, but no Timestamp on the Filename
        # Add pid
        current_pid = os.getpid()
        exec_filename = self.frmt_fname(self.execFilename,current_pid)
        self.full_lock_filename = self.frmt_fname(self.lockFilename,current_pid)

        # launch the Function with args      
        # Generate Subprocess Detached, returns Sub Process info 
        exec_sub = self.execWorkload(args['cmd'],exec_filename,self.full_lock_filename)
        exec_sub.start()

        self.logger.info("Execute Shell Process: " + str(exec_sub) )
       # Wait for Sub Processes to Start
        self.exec_sub_pid = None

        # Loop until sub Process has started
        while not self.exec_sub_pid:
            time.sleep(0.25)
            children = psutil.Process().children(recursive=True)
            for child in children:
                self.logger.info('Child pid is {}'.format(child.pid) )
                if child.name() == 'cmd.exe': 
                    self.exec_sub_pid = child.pid
                    self.logger.info('Child name is {}'.format(child.name()) )
                    
        if not self.exec_sub_pid:
            self.logger.error("Failed to Start runShell Process for workload.")
            sys.exit(1)

        # launch the Function with args      
        msg = 'Execute: ' + "cmd: " + str(args['cmd'] + " Execute PID: " + str(self.exec_sub_pid) + " Execute File: " + exec_filename)
        self.logger.info(msg)
       
        # Monitor the Executed Cmd
        lockArgs = self.format_monitor_args(args['cmd'],self.exec_sub_pid,exec_filename,self.full_lock_filename,self.notes)
        lockcmd  = 'python3 monitorProcess.py'
        lockcmd  = lockcmd  + ' -m ' + " " + lockArgs

        # Generate Subprocess Detached, returns Sub Process info 
        # monitor_sub_process = self.runShell(lockcmd,None)
        # Run Monitor Daemon, send no File Names for daemon
#        monitor_sub_process = self.runShell(lockcmd,"./log/monitor_debug.log",None)
        debugFile = "./log/monitor_debug.log"

        monitor_sub_process = self.runContainer(lockcmd,debugFile,self.full_lock_filename)
        monitor_sub_process.start()
        
        self.logger.info('monitor_sub_process: ' +  str(monitor_sub_process))

        self.logger.info("Monitor Command: " + lockcmd  + "sub Process PID: " + str(monitor_sub_process.pid) + "Lock File: " + self.lockFilename)
        self.logger.info("Monitor args: " + str(lockcmd) )
        time.sleep(1)
        return exec_sub 

    def format_monitor_args(self,cmdline=None,exec_pid=None,exec_filename=None,lock_filename=None,notes=None):
        #lockName    = self.proc_name + str('lockfile ')
        lockArgs={}
        lockArgs['pid']         = exec_pid
        lockArgs['cmdline']     = cmdline
        lockArgs['exec_limit']  = self.exec_limit
        lockArgs['execFname']   = exec_filename
        lockArgs['lockFname']   = lock_filename
        lockArgs['loop_checkpoint_timeout'] = self.loop_checkpoint_timeout
        lockArgs['notes']       = notes
        lockArgs['verbose']     = logging.getLevelName(self.logger.getEffectiveLevel() )

        self.logger.info("Python Format LockArgs: ")
        self.logger.info( lockArgs)
        # Double json escapes he Double quotes with \" to support he Windows interpretor.
        lockArgs = json.dumps(json.dumps(lockArgs))
        return lockArgs
    
    def checkpoint_update(self,pid=None,execFname=None,lockfile=None,loop_checkpoint_timeout=None):
        # python3 monitorProcess.py data
        proc_lock = mp.Process(
                               target=self.run_daemon,
                               args=(self.checkpoint_update,proc.pid,),
                               name=name1,
                               daemon =True
                               )

        proc_lock.start()

    def run_daemon(self,target=None,args=None):
       p = mp.subprocess.run(target=target,args=(args,), daemon=True)
       p.start()
       return p

    def time_gen(self,time_stamp=None,format_string='%Y-%m-%dT%H:%M:%S%z'):
 #       now = datetime.now(ZoneInfo('America/Chicago'))
        now = datetime.now(pytz.timezone('US/Central'))
        if(time_stamp):
            now = datetime.now()
            # convert from datetime to timestamp
            date =  datetime.timestamp(now)
        else:
            date =  now.strftime(format_string)
        return date      
    def runContainer(self,cmd=None,filename=None,lockFname=None,executeWorkload=False):
        print(cmd)
        p = mp.Process( target=self.runShell, args=(cmd,filename,lockFname,executeWorkload),daemon=True) 
        return p

    def execWorkload(self,cmd=None,filename=None,lockFname=None):
        # Wrap RunShell in Prcess to grab Exceptions and to write Return code on runShell exit.
        # open stdout File
        controllerCmd = 'python3 exec.py'
        exec_cmd = self.createExecOptions(controllerCmd,cmd,filename,lockFname,logging.getLevelName(self.logger.getEffectiveLevel() )  )
        self.logger.info("Exec Command: " + exec_cmd)
        p = mp.Process( target=self.runShell, args=(exec_cmd,filename,lockFname,),daemon=True) 
#        p = subprocess.run( self.runShell,args=(cmd,),stdout=f,shell=False,check=True,stderr=subprocess.STDOUT)
        return p

    def createExecOptions(self,controllerCmd=None, cmd=None,filename=None,lockFname=None,verbose=None):
        outdata = str(controllerCmd)
        outdata = outdata + ' ' + str('-run')  + ' ' + str('\"' + cmd + '\"') 
        outdata = outdata + ' ' + str('-file') + ' ' + str(filename)
        outdata = outdata + ' ' + str('-lock') + ' ' + str(lockFname) 
        outdata = outdata + ' ' + str('-v')    + ' ' + str(verbose) 
        return outdata

    def runShell(self,cmd=None,filename=None,lockFname=None,executeWorkload=None):
        f = None
        sub = None
        returnCode=0
        comment="Success"
        print("runShell: " + str(filename) )
        if executeWorkload:
            print("runShell: " + str(filename) )
            f = open(filename,"w")
        else:
            print("runShell: Devnull" )
            f = open(os.devnull,"w")

        try:
            # run hte Sub Process Execute Workload  / or Monitor Process
            sub = subprocess.run( str(cmd),stdout=f,shell=True,check=True,stderr=subprocess.STDOUT)
       
        except subprocess.CalledProcessError as e:
            returnCode = str(e)
            #self.logger.error("Subprocess Check Exception: " + str(returnCode) )  
            # Send to Lock File, append to file
            returnCode=e.returncode

            # Write to Execute Log
            returnCode = 'ReturnCode: ' + str(returnCode)
            comment ='Comment: ' + str(e)

        # Send the Return Code to the Execute log and lockfile
        if executeWorkload:
            print("Exit Status Write: " + str(comment))
            self.write_exit_status(f,lockFname,comment,returnCode)
        # Close file
        if f:
            f.close()

    def write_exit_status(self,filehandle=None,filename=None,comment=None,rc=None):             

            filehandle.write('ReturnCode: ' + str(rc) + "\n" + str(comment) + "\n")

            # Send to Lock File, append to file
            self.updateLock(filename,str(rc),'ReturnCode')            
            self.updateLock(filename,str(comment),'Comment')

    def updateLock(self,fname=None,msg=None, key='ReturnCode'):
        if fname:
            if not os.path.isfile(fname):
                docs = [{}]
            else:
                # Get the Existing Yaml Data
                docs = self.read_yaml(fname)
            for doc in docs:
                # update
                doc[key] = msg

            # Write data
            self.write_yaml(fname,doc,'w')

    def setup(self,filename):
        pass

    def setvalue(self,key=None,data=None):
        match key:
            case 'verbose':
                self.logger.setLevel(data.upper())
                
            case 'run_limit':
                # length of time to run before Killing process
                sec = self.to_sec(data)
                self.exec_limit = sec
            case 'lock_log_dir':
                self.lock_log_dir = data
                self.set_dir(self.lock_log_dir)
            case 'notes':
                self.notes = data
            case 'name':
                self.proc_name = data
            case _:
                self.logger.error('Un-supported Option: ' + str(key))
                sys.exit(1)

    def to_sec(self,data):
        pat_list = [{'p':'([0-9]*)\s*[m]','conv': 60},{'p':'([0-9]*)\s*[h]','conv': 3600},{'p':'([0-9]*\s*)','conv': 1}]
        for p in pat_list:
           # Remove leading and trailing whitespace, and force lower case.
           m = re.match(p['p'],data.strip().lower())
           if m:
               value = int(p['conv'])
               dat = int(m.group(1))
               sec = int(dat) * value
               self.logger.info("to_sec(" + str(dat) + ')=' + str(sec))
               break
        return sec

    def main(self,argsDict=None):
        # Set the Parameters as given.
        # Process each option
        for key in argsDict:
            if not key == 'run':
                if argsDict[key]:
                    for v in argsDict[key]:
                        self.setvalue(key,v)

        # run the Workload
        # argsDict['run'] == None unless a value has been given
        status = 'Not Run'
        for cmd in argsDict['run']:
            self.logger.info('run workload: cmdline: ' + str(cmd))
            runArgs={}
            for r in argsDict['run']:
                runArgs['cmd']=self.json_decode(str(r))
            status,info = self.run(runArgs)
        print("Run Status: " + status)
        print("Run Info: " + str(info) )
        return status,info

    def json_decode(self,data=None):
        try:
            d = json.loads(data)
          
        except Exception as e:
            self.logger.error('Json Decode failed for:' + '\'' + str(data)+ '\''  )
            self.logger.error('Exception: ' + str(e))
            sys.exit()
        return d

            
if __name__ == '__main__':
    import sys

    # Execute Class
    ex = execute()

#    ex.checkpoint_update({'cmd':'python3 workload1.py'})   
    #ex.launch({'
    #cmd':'python3 workload1.py'})
    #data = json.dumps({'cmd':'python3 workload1.py'})
   
    # Command line Parser
    parser = argparse.ArgumentParser("Execute Workload:")
    start_ts = ex.time_gen(True)
    parser.add_argument('-v'    ,'--verbose'        , nargs=1, type=str, help='<verbose [error]> Options are debug,info,warning,error Default is error'  ) 
    parser.add_argument('-run'  ,'--run'            , nargs=1, type=str, help='Run the attached command string <python3 python3 workload1.py>' ) 
    parser.add_argument('-notes' ,'--notes'         , nargs=1, type=str, help='Notes String, Entered in lock file' ) 
    parser.add_argument('-rl'   ,'--run_limit'      , nargs=1, type=str, help='Error and Kill the Processes after runing for <run limit 300>  No Limit if not supplied' ) 
    parser.add_argument('-ldir' ,'--lock_log_dir'   , nargs=1, type=str, help='lock and log directory' )

    # Verbosity
#    sys.argv.append('-v')
#    sys.argv.append('WARNING')

    # ./log/<lock and log directory> 
    #sys.argv.append('-ldir')
    #sys.argv.append("./log")

 #   sys.argv.append('--notes')
 #   sys.argv.append('Remote Exec and Monitor test')

    # Limit exec
    #sys.argv.append('-rl')
    #sys.argv.append('1000')


    # execute command
    #sys.argv.append('-run')
    #data = json.dumps("python3 workload1.py")    
    #sys.argv.append(data)
    #print(sys.argv)
    args = parser.parse_args()
    ex.logger.info('Starting Workload with Parameters: ' + str(args.__dict__) )
    data = ex.main(args.__dict__) 
    


