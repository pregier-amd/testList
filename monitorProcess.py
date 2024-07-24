import logging
import time
from datetime import datetime
import pytz
import psutil
import os
import sys
import json
import argparse
import yaml
from LogClass import LogClass

class monitor_process(object):
    def __init__(self,):
      #  logging.getLogger().setLevel(logging.INFO)
      #  self.logger =logging.getLogger('logger')

        # Data for Lock File
        self.lock_data = {}

         # Logger
        log = LogClass(None,"log\monitorProcess.log",False)
        self.logger = log.logger
        self.logger.setLevel(logging.WARNING)



    def main(self,args=None):
        self.logger.info(args)
        for key in args:
            match key:
                case 'monitor':
                    for row in args['monitor']:
                      self.checkpoint_update( json.loads(row) )

    def checkpoint_update(self,args=None):
        print("Checkpoint")
        # Execute the args['cmd']       
        # Record the Run log Filename same string created in runShell
        # Preload data to save in Lock File
        ldata ={}
        for key in args:
            # Grab Dictionary
            ldata[key] = args[key]

        if 'verbose' in ldata:
            self.logger.setLevel(ldata['verbose'])

        self.logger.info("Monitoring Start for PID: " + str(args['pid']) )
        self.logger.info("execFname: " + args['execFname'])

        # Save the Execution State.
        # Add pid to self.lockfile filename        
        
        self.logger.debug('Create lockfile: ' + str(args['lockFname']) + " lock Data:" + str(ldata) )
        self.manage_lockfile(args['lockFname'],args['pid'],'create',ldata)

        # Create the Lock / Status file
        self.logger.debug('Start lockfile: ' + str(args['lockFname']) )
        self.manage_lockfile(args['lockFname'],args['pid'],'start',ldata)

        #Record the Starting TS
        # proc is the process being monitored.
        ts_start = time.time()
        msg=str(args['pid']) + " " + "Checkpoint Loop Start"
        self.logger.info(msg)

        while True:

            if not self.pid_alive(args['pid']):
                # Process exitied.
                break
            # wait while until checkpoint interval.
            time.sleep( args['loop_checkpoint_timeout'] )

            # Calculate the Overal Duration
            duration = self.calc_duration(ts_start)
            ldata['duration'] = duration

            
            # Check for extended execution
            if args['exec_limit']:
                if duration > args['exec_limit']:
                    try:
                        #data['exitcode']=pid.exitcode
                        msg =str(args['pid']) + " " + 'Exceeded Execution Limit: ' + str(args['exec_limit'])
                        ldata['comment']=msg
                        ldata['ReturnCode'] ='Timeout'
                        self.logger.info(msg)
                        self.manage_lockfile(args['lockFname'],args['pid'],'end',ldata)
                
                        # Terminate the Process that was being Monitored
                        self.kill(args['pid'])

                        # Exit the checkpoint loop
                        break
                    except:
                        self.logger.error("Exception in exceeded limit: "  )
                        self.kill(args['pid'])
                        return
            # Update lock file with checkpoint
            self.manage_lockfile(args['lockFname'],args['pid'],'checkpoint',ldata)

        # After the While Active: exit
        # Calculate the Overal Duration
        ldata['duration'] = self.calc_duration(ts_start)
        msg=str(args['pid']) + " " + "Process Ended:"
        self.logger.info(msg)
        self.manage_lockfile(args['lockFname'],args['pid'],'end',ldata)

    def manage_lockfile(self,filename=None,pid=None,cmd=None,data=None,):
        # Execution Status and information stored as self.lock_data
        self.logger.debug("manage_lockfile cmd: " + str(cmd) + " Data:" + str(data) )

        # Read the Contents of the Lock File
        if os.path.isfile(filename):
             for doc in self.read_yaml(filename):
                 self.lock_data = doc
                 self.logger.info("Read Data from Lockfile: " + str(self.lock_data))

        if not self.lock_data:
              self.lock_data = {}

        # update the current data.
        self.logger.debug("Input Data: " + str(data))
        if not isinstance(self.lock_data,dict):
              self.logger.info("lock Data incorrect: " + str(self.lock_data))
              self.lock_data = {}

        # Transfer Passed in data to write to file
        if data:
            for k in data:
                self.lock_data[k] = data[k]

        result = False
        # Log the file change
        self.logger.info("manage_lockfile: " + str(cmd) )
        match cmd:
            case 'create':
                # Create File with Start Date
                t = self.time_gen()
                self.lock_data['end'] =''
                self.lock_data['checkpoint'] =''
                self.lock_data['start'] =''
                self.lock_data['status'] ='Starting'
                result = True
            case 'remove':
                if not os.path.isfile(filename):
                    return None
                # Return the Contents and Delete the file
                result = self.read_yaml(self.lockfile)
                os.remove(filename)
                result = True
            case 'checkpoint' | 'start' | 'end':
                # write checkpoint/start/end: time = now
                t = self.time_gen()
                self.lock_data[cmd] = t

                # Set the Status start/end/running
                status = cmd
                if cmd == 'checkpoint':
                    status = 'running'
                self.lock_data['status'] = status
                result = True
            case 'isbusy':
                result = None
                # return the lock file data:
                rdata = self.read_yaml(filename)
                # for any other status then end, the file is busy.
                if not rdata['status'] == 'end':
                   result = rdata
        self.logger.debug("manage_lockfile lock_data: " + str(self.lock_data))
        self.write_yaml(filename,self.lock_data)                    
        return result

    def pid_alive(self,pid=None):
        return psutil.pid_exists(pid)

    def kill(self,pid=None):
        if os.name == 'nt':
            #  Kill process and children Tree /T 
            k = 'taskkill /F /T /PID ' + str(pid)
            os.system(k )
        else:
            os.system('kill -9 '  + str(pid))

        self.logger.info( "Kill Process: " + k)


    def calc_duration(self,start=None,end=None,prec=3):
        duration = None
        if not end:
            end = time.time()
        # duration in Seconds
        if start:
            duration = round(end - start,prec)

        return duration

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
    def read_yaml(self,filename):
        if not os.path.isfile(filename):
            return
        data = []
        with open(filename, 'r') as file:
            docs = yaml.safe_load_all(file)
            for doc in docs:
                data.append(doc)
        return data

    def write_yaml(self,filename=None,data=None):
        if not filename:
            return
        with open(filename, 'w') as file:
           yaml.dump(data, file)
           
if __name__ == '__main__':
    mp = monitor_process()
    mp.logger.info(__file__)
    parser = argparse.ArgumentParser("Execute Workload:")
    
    parser.add_argument('-m','--monitor', nargs=1, type=str, help=' json{"pid": 123,"execFname":fname,"lockfile":fname,"loop_checkpoint_timeout": seconds check loop}' ) 

#    sys.argv.append('-m')
#    data = {'pid': 38172, 'cmdline': 'python3 workload1.py', 'exec_limit': 2000, 'execFname': 'C:\\\\Users\\\\pregier\\\\Documents\\\\qTest\\\\python\\\\qTestAPI\\\\log/39060_exec.log', 'lockFname': 'C:\\\\Users\\\\pregier\\\\Documents\\\\qTest\\\\python\\\\qTestAPI\\\\log/39060_lock.yml', 'loop_checkpoint_timeout': 2}
#    sys.argv.append( json.dumps(data) )

    args = parser.parse_args()
    data = mp.main(args.__dict__) 
    sys.exit(0)