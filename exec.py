import logging
from LogClass import LogClass
import subprocess
import argparse
import sys,os
import yaml

class exec(object ):
    def __init__ (self,cmd=None,fname=None,lockFname=None):

        self.logdir = ''

        # Logger
        log = LogClass(None,"log\exec.log",False)
        self.logger = log.logger
        self.logger.setLevel(logging.WARNING)

        self.cmd = 'echo \\"Hello World\\"'
        if cmd:
            self.cmd = cmd

        self.fname = self.logdir + 'exec.log'
        if fname:
            self.fname = self.logdir  + str(fname)

        self.lockFname = self.logdir + 'lock.log'
        if lockFname:
            self.lockFname = self.logdir + lockFname
       

    def runShell(self,cmd=None,filename=None,lockFname=None):
        f = None
        sub = None

        # Success Status
        returnCode=0
        comment="Success"

        print("runShell: " + str(filename) )
        if filename:
            f = open(filename,"w")
        else:
            f = open(os.devnull,"w")

        try:
            # run the Sub Process Execute Workload  / or Monitor Process
            subprocess.run( str(cmd),stdout=f,shell=True,check=True,stderr=subprocess.STDOUT)
       
        except subprocess.CalledProcessError as e:
            returnCode = str(e)
            #self.logger.error("Subprocess Check Exception: " + str(returnCode) )  
            # Send to Lock File, append to file
            returnCode=e.returncode

            # Write to Execute Log
            returnCode = 'ReturnCode: ' + str(returnCode)
            comment = str(e)

        # Send the Return Code to the Execute log and lockfile
        print("Exit Status Write: " + str(comment))

        # Send to Lock File, append to file
        data = {'ReturnCode': returnCode,'Comment':comment}
        self.write_exit_status(f,lockFname,data)

        # Close file
        if f:
            f.close()

    def write_exit_status(self,filehandle=None,filename=None,indata=None): #comment=None,rc=None):             
            for key in indata:
            
                filehandle.write(str(key) + ': ' + str( indata[key] ) + "\n")
#                filehandle.write('ReturnCode: ' + str(rc) + "\n" + str(comment) + "\n")
            # Send to Lock File, append to file
            self.updateLock(filename,indata)            

    def updateLock(self,fname=None,indata= None): # msg=None, key='ReturnCode'):
        if fname:
            if not os.path.isfile(fname):
                docs = [{}]
            else:
                # Get the Existing Yaml Data
                docs = self.read_yaml(fname)
            doc = {}
            if docs:
                for d in docs:
                    # update
                    doc = d

            # update multiple Keys
            for key in indata:
                doc[key] = indata[key]
            # Write data
            self.write_yaml(fname,doc,'w')

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
    def write_yaml(self,filename=None,data=None,mode='w'):
            if not filename:
                return
            with open(filename, 'w') as file:
               yaml.dump(data, file)

    def main(self,argsDict=None):
        # Set the Parameters as given.
        # Process each option
        for key in argsDict:
            if argsDict[key]:
                match key:
                    case 'verbose':                    
                            for v in argsDict[key]:
                                self.logger.setLevel(v.upper())
                    case 'execFile':
                        for v in argsDict[key]:
                             self.fname = v
                    case 'lockFile':
                        for v in argsDict[key]:
                             self.lockFname = v
                    case 'run':
                        for v in argsDict[key]:
                            self.cmd = v

        # Execute the Command
        self.runShell(self.cmd,self.fname,self.lockFname)


if __name__ == '__main__':
    exc = exec()
    parser = argparse.ArgumentParser("Exec Controller:")

    parser.add_argument('-v'    ,'--verbose'        , nargs=1, type=str, help='<verbose [error]> Options are debug,info,warning,error Default is error'  )     
    parser.add_argument('-file' ,'--execFile'      , nargs=1, type=str, help='Error and Kill the Processes after runing for <run limit 300>  No Limit if not supplied' ) 
    parser.add_argument('-lock' ,'--lockFile'      , nargs=1, type=str, help='Error and Kill the Processes after runing for <run limit 300>  No Limit if not supplied' ) 
    parser.add_argument('-run'  ,'--run'            , nargs=1, type=str, help='Run the attached command string <python3 python3 workload1.py>' ) 


#    sys.argv.append('-file')
#    sys.argv.append('log/123_exec.log')
#    sys.argv.append('-lock')
#    sys.argv.append('log/123_lock.log')


 #   sys.argv.append('-v')
 #   sys.argv.append('INFO')
 #   sys.argv.append('-run')
 #   sys.argv.append('python3 workload1.py')

    args = parser.parse_args()
    exc.logger.info('Starting Workload with Parameters: ' + str(args.__dict__) )
    data = exc.main(args.__dict__) 
    
