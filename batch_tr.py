from dataclasses import dataclass
import dataclasses
from LogClass import LogClass
from util import util
import re
import os
from datetime import datetime
import argparse
import yaml
import sys
import queue as Queue
from qTestAPI import QtestAPI
from threading import Thread
import threading
import json
from pathlib import Path
import time

import subprocess
from file_queue import FileQueue
import random

class Batch_TR(object):
   
    def __init__(self,logger = None, config_file =None ): 
        sys.tracebacklimit = 0

        if(not logger):
            # Create a logfile
            filename = 'log/' + os.path.basename(__file__) + '.log'
            self.lc = LogClass(logger,filename)
            self.logger = self.lc.logger
        else:
            self.logger = logger

        self.batch_queue = FileQueue('./batch/batchQueue.json')

        self.util =  util(self.logger,config_file)

        self.cfg = self.util.cfg

        self.logger.setLevel(getattr(logging, self.cfg.get('logger','level') ) )

        self.qta = QtestAPI('config.ini',self.logger)

        self.status_list = None
        # Que for Writing Test Runs in Parallel
        # Queue defaults to 30 Deep, but will run only the number of threads avaable
        self.queuesize  = self.cfg.getint('request_queue','maxqueuesize',fallback=300)   # Integer 1 to 1000
        self.maxthreads = self.cfg.getint('request_queue','maxthreads',fallback=20)

        self.row_queue = None
        self.row_queue = self.queue_init(self.row_queue,self.queuesize)
        # Where the tests are executed
        self.wd = '/home/pregier/conductor'
        # local config file relative path
        self.batch_path = './batch'
        # Coumn Names that contain the cmdline for Test Run.
        self.tr_cmd_col = ['Test Step Description','Test Case Planned IP Specific Test Parameters / Command line']
   

    def queue_init(self,queue=None,maxthreads=10,queue_size=30):
        queue = Queue.Queue(queue_size)

        # Start the Worker Threads.
        for i in range(maxthreads):
            worker = Thread(target = self.process_row_queue, args=(queue,) )
            worker.daemon=True
            worker.start()
        return queue
       

    def submit_row_queue(self,queue=None,indata=None):
        data = {}
        # In effect a Deep copy)
        data = indata.copy()

        # Put in Queue
        queue.put(data)

    def process_row_queue(self,queue):
        while True:
            # Read the Queue using multiple threads.
            command =  queue.get()
            if command['batch']:
                msg = "Start Row:" + str( command['cnt']) + " Worker: " + str(threading.current_thread().name  ) 
                self.logger.info(msg)
                # Que in Conductor.
                self.conductor_batch(command['row'])
            else:
                self.logger.info("Qtest Status Update:")
                msg = "Start Row:" + str( command['cnt']) + " Worker: " + str(threading.current_thread().name  ) 
                self.logger.info(msg)
                self.update_tr_row(command)
            queue.task_done()

    def process_batch_queue(self):
        while True:
            # Read the Queue using multiple threads.
            command =  self.batch_queue.dequeue()
            if not command['state'] == 'queued':
                msg = "Start qTest TR Update:" + str( command['cnt']) + " Worker: " + str(threading.current_thread().name  ) 
                self.logger.info(msg)
                # Update TR.
                # If no TR ID, thne use Auto Log 
                # If there is a TR ID update the Status, acutual Results, Link The Logs
                #                 
                self.update_tr_row(command)
                #Thread Done.. How??? 



    def get_results_from_queue(self,data):
        # Pull the TR Results from the conductor Batch.
        # if state is still Queued or Running put it back in the (wait a little) then re-Queue
        # Receives the Result from the Batch Que Process from Conductor.
 #       conduct list job --filter id=a39b3a5b-e315-42f2-bfaa-727be7c79077 --sort-direction="ascending" --json-output
#{"id": "a39b3a5b-e315-42f2-bfaa-727be7c79077", "date_create": "2025-04-08T01:27:39.256189+00:00", "date_end": "2025-04-08T04:56:38.914868+00:00", "date_start": "2025-04-08T04:41:59.051127+00:00", "system_id": "715d138b-06da-47db-a10d-1c8a396a4fc6", "job_set_id": "432f94f2-70a6-47c2-89e3-ab0764f4be6a", "live_stdout_log_url": "aus-mw-vm-01.aus.dcgpu:80/job/log/raw?external_job_id=a39b3a5b-e315-42f2-bfaa-727be7c79077", "job_exec_runid": "aus-mw-vm-01.aus.dcgpu:80/job?id=2e5a8147-b75a-4857-8990-1f60cb3a26bd", "state": "DONE", "aborted": false, "aborting_user_id": null, "aborted_time_stamp": null, "abort_reason": null, "preempted": false, "result": "SUCCESS", "orc3db_scheduler_id": null, "date_state_change": "2025-04-08T04:56:38.914868+00:00", "artifact_url": "https://atscloud.blob.core.windows.net/jobartifacts/a39b3a5b-e315-42f2-bfaa-727be7c79077-2025-04-08T04_55_09+00_00-aus-onyx-7421.amd.com.tar.gz", "reservation_ids": null, "meta": {}, "result_meta": {}}

        batch_list_cmd=self.conductor_list_format(data,'setup.sh')

        # Send Conductor using Shell command
        # capture the data.
        result = self.exec_shell(batch_list_cmd)
        
        self.batch_queue.queue(data)

    def process_sheet(self,data=None,batch=False):
        start_ts = time.time()
        cnt = 2
        for row in data:
            # Update Qtest Only.
            command = {'row':row,'cnt':cnt, 'batch':batch }
            self.submit_row_queue(self.row_queue,command)

            # update the Counter
            cnt += 1
        
        # Wait for the Threads to finish
        self.row_queue.join()
        duration = time.time() - start_ts
        self.logger.info("Processed " + str(len(data)) + " Rows in: " + str(round(duration,3)) + ' sec' + ' Thread cnt: ' + str(self.cfg['request_queue']['maxthreads']) ) 

    def check_results(self,results=None):
        result = True
        if not isinstance(results,dict):
            m = re.match('.*20',str(results))
            if not m:
                self.logger.error("Request Failed: " + str(results.json()) )
                result = False
        return result

    def update_tr_row(self,command=None):
            start_ts = time.time()
            row = command['row']
            cnt = command['cnt']

            # Check Each Row for Valid Data:
            # Skip the Row if Status is un executed.
            status_unexec = 'Unexecuted'
            if 'Status' in row:
                if row['Status'] == status_unexec:
                    self.logger.info("Row:" + str(cnt) + " Nothing to Do for Status: " + str(status_unexec) ) 
                    return 
            self.logger.debug("Row:" + str(cnt) )
            self.logger.debug("Test Run:" + str(row))



            query = {"object_type": "test-runs","fields": ["*"],"query": "'Id' = '" + str(row['Id']) + "'" }
            tr = self.qta.search(None, None, 100, 1, 'asc',query)

            self.logger.debug("Test Run: " + str(tr))
            if 'items' in tr:
                if len(tr['items']) < 1:
                    self.logger.warning("Row:" + str(cnt) + " No Test Run Found for: " + str(row['Id']) )
                    return
                for tr_row in tr['items']:
                    endpoint = 'test-runs/'+str(tr_row['id']) + '/test-logs'
#                    params = {'expand':'teststeplog.teststep'}
#                    params = {'expand':'teststeplog.teststep','appendTestSteps':True}                 
#                    tr_logs     = self.qta.get(None,None,None, endpoint,params)
                    # Error if Result is not 20x
 #                   if not self.check_results(tr_logs):
                        # Failed to get test Run
 #                       self.logger.error("Error Failed to get TR Log: " + str(tr_logs))
 #                       return 
                    tr_log_body = self.format_runlog(tr_row,row)
                    if not  tr_log_body:
                        self.logger.error("Row:" + str(cnt) + "Error Failed to Format Request Body to Create Test Run Row:" + str(cnt) )
                        # End Processing for the Row.
                        return None
            duration = time.time() - start_ts
            self.logger.info("Complete Row:" + str(cnt) + " Test Run Status: " + str(tr_log_body['status']['name']) + " Duration: " + str(round(duration,3)) + " sec")
            self.logger.debug("New Test Run Log Body: " + str(tr_log_body))
            self.logger.debug('TR:' + str(tr))

            # Write test run log:
            result = self.write_test_run_log(tr_log_body,tr_row)
            if not result:
                self.logger.error("Row:" + str(cnt) + " Error Failed to Write Test Log:" + " TR ID:" + str(tr_row['pid'])  + ' Request:' + str(json.dumps(tr_log_body)) )

    def validate_create_tr_log(self,data=None):
        # Load the Status List from Project. Print out valid values
        self.logger.info("\nValidate all rows of data.")
        self.format_status("Passed")
        cnt = 2
        result = True
        for row in data:

           # Check the Data. 
           if not self.validate(row,cnt):
               result = False

           # Update the Counter
           cnt += 1 
        return result

    def validate(self,row,cnt):        
        result = True
        start_date = self.cfg['test run excel']['start_date']
        end_date =  self.cfg['test run excel']['end_date']

        # Confirm: rows in [test run excel]
        for (each_key, each_val) in self.cfg['test run excel'].items():

            match each_key:
                case 'id': 
                    if not each_val in row:
                        self.logger.error('Row:' + str(cnt) + ' Error No Column ' + str(each_val))
                        result = False
                case 'status': 
                    if not each_val in row:
                        self.logger.error('Row:' + str(cnt) + ' Error No Column ' + str(each_val))
                        result = False

                    # Check Value for Status
                    if not row[each_val].lower() in self.status_name_list:
                        self.logger.error('Row:' + str(cnt) + ' Error Illegal Value row[' + str(each_val) + ']:' + '\'' + str(row[each_val]) + '\'')
                        result = False

                    if row[each_val].lower() == str("Waived").lower():
                        self.logger.warning('Remapped ' + str(row[each_val]) + " to " + str('Incomplete') ) 
                        row[each_val] = 'Incomplete'

            if re.match('.*date',each_key):
                # Check if Date Format Correct
                date_str, msg  = self.format_exec_date(row,each_val,'%Y-%m-%dT%H:%M:%S%z','%Y-%m-%dT%H:%M:%S%z')
                if not date_str:
                    self.logger.error('Row:' + str(cnt) + ' Error Illegal Value Column: ' + str(each_val) ) # + '\'' + str(row[each_val]) + '\'')
                    self.logger.error('Error: ' +  str(msg) )

                    result = False
                    
        return result

    def write_test_run_log(self,body=None,trl=None):
        endpoint = '/test-runs/' + str(trl['id']) + '/test-logs'
        # Get the Last Test Run and Expand the Test Step Info
        parameters = {'testRunId': trl['id']}
        result = self.qta.post(None, None, endpoint,parameters,body)
        self.logger.debug("Test Run Log Result: " + str(result))

        return result

    
    def format_runlog(self,tr=None,input_row=None):
        body = None
        # Grab the the Test Steps,
        # Extract the Status from the row, create the runlog body.
        tcstepid = None
        if not 'test_case' in tr:
            self.logger.error('Error format_runlog Key not Found:' + str('test_case') + ' in ' + str(tr))
            return None
        if not 'test_steps' in tr['test_case']:
            self.logger.error('Error format_runlog Key not Found:' + str('test_steps') + ' in ' + str(tr['test_case']))
            return None
        for step in  tr['test_case']['test_steps']:
            # Grab the First Step in test Case
            tcstepid = step['id']
            break

        if not tcstepid:
            self.logger.error('No Test Case Step Id found for test run:' + str(tr))
            return None


        body = self.create_runlog_body(tr,input_row,self.cfg.get('test run excel','status',fallback='Status'),tcstepid )
        self.logger.debug("Format Run Log Body: " + str(body))
        return body

    def create_test_step_log(self,input_row=None):
        # 
        status_col = self.cfg.get('test run excel','status',fallback='Status') 

        # Create the Dictionary of Step Log Fields
        step_fields ={}
        step_fields["status"] =  self.format_status(input_row[status_col])
        # if hte Excel has the Column add it to the Step Field
        for step_key in self.cfg['step keys']:
            col = self.cfg.get('step keys',step_key)
            if col in input_row:
                step_fields[col] = input_row[col]

        self.logger.debug("Step Data: " + str(step_fields) )
        return step_fields

              
    def create_runlog_body(self,tr_row,input_row,status_col="Status",tcstepid=None):
        outbody = {"id": 1,}
        # If the excel Test Run Log Column for Exec Dates. Use them.
        # elese use "Now" for execution date.
        dates = [ self.cfg['test run excel']['start_date'], self.cfg['test run excel']['end_date'] ]
        for data_name in dates:
            outbody[data_name],error = self.format_exec_date(input_row,data_name)
        if status_col in input_row:
            outbody['status'] = self.format_status(input_row[status_col])
            if 'name' in outbody['status']:
               self.logger.debug(' Create Runlog Body: Status:' + '  \'' + str(outbody['status']['name'])+ '\'' )
        # Add test Step Logs
        outbody['test_step_logs'] = []
        step_log = self.create_test_step_log(input_row)
        step_log['test_step_id'] = tcstepid
        step_log['test_step_log_id'] = 0
        outbody['test_step_logs'].append( step_log )

        outbody['result_number'] = 0 

        return outbody

    def format_status(self,instatus=None):
        remap_stat = {'waived':'Incomplete','skipped':'Blocked'}
        if instatus.lower() in remap_stat:
            self.logger.warning("Warning Remapped Status[" + instatus + "]=" + remap_stat[instatus.lower()])
            instatus = remap_stat[instatus.lower()]
        # Fetch the status values from the project.
        status= None
        if not self.status_list:
            data=self.qta.get_execution_status()
            if data: 
                self.status_list =  data
                self.status_name_list = []
                for row in  self.status_list:
                    self.status_name_list.append(row['name'].lower())
                self.logger.info("Supported Status Values: " + str(self.status_name_list) )

        status = list( filter( lambda row: row['name'].lower() == instatus.lower() , self.status_list ) )
        for s in status:
            status = s
        return status
    def format_exec_date(self,tr_row=None,date_name=None,informat='%Y-%m-%dT%H:%M:%S%z',outformat='%Y-%m-%dT%H:%M:%S%z'):
        # if the Date Column is in the Row. Use the date.
        date_time = None
        error = ''
        # If the Column is present
        indate_time = None
        if date_name in tr_row:
             # Check for Blank Dates's, and remove white space.
            indate_time = str(tr_row[date_name]).strip()

        if indate_time:
            # Convert the Specified Date Time Format.
            date_time,error = self.qta.time_format(str(tr_row[date_name]).strip(),informat,outformat)
        else:
            # No Date Specified:
            date_time = self.qta.time_gen(None,format_string='%Y-%m-%dT%H:%M:%S%z') 

        return date_time,error
    def update_test_config(self, data):
        self.project_key = 'qtest_prj'

        for f in data:
            self.test_config = self.util.read_yaml(f)
            self.logger.info("Conductor Test Config: ")# + str(self.test_config))
            for cmdline in self.test_config['tests']:
                self.logger.info('cmd:' + str(cmdline['args']['cmd']) )

            if self.test_config['globals']:
                if self.project_key in self.test_config['globals']:
                   self.set_project_id( self.test_config['globals'][self.project_key ])

    def main(self,args=None):
        self.logger.info("Input Arguments: " + str(args) )
        self.project = None
        for key in args:
            if not args[key]:
                continue
            match key:
                case 'test_conf':
                     self.update_test_config(args['test_conf'])


                case 'test_runs':
                    if not args['test_runs']:
                        continue
                    # 
                    if not self.test_config:
                        if args['test_conf']:
                            self.update_test_config(args['test_conf'])

                    if not self.test_config['globals'][self.project_key]:
                        self.logger.error("Error: No Project Given: use \" Add " + str(self.project_key) + " in global variables in config>\" ")
                        return
                    for file in args['test_runs']:
                      data = self.util.read_excel_each_sheet(file)
                      if not data:
                          return
                      for sheet in data:
                          self.logger.info( str(file) + "[" + sheet + "] Row Cnt: " + str(len(data[sheet]) ) ) 
                          # Validate the Input: Exit on Error
                          if not self.validate_create_tr_log(data[sheet]):
                              # Invalid data in Skip row
                              self.logger.error("Failed to Validate input Excel File. Fix Errors then retry.")
                              return 
                          # Valid input File. 
                          batch=True
                          self.process_sheet(data[sheet],batch)
                    return

                case 'project':
                    if not self.project:
                       # read the Projects and
                       self.set_project_id( args['project'])
                case 'template':
                    print('Template Process')
                    # Dump out Templae if true
                    filename = args['template']
                    ext = Path(filename).suffix
                    if not ext == '.xlsx':
                        supported = '.xlsx'
                        filename = filename.replace(ext,supported)
                        self.logger.warning("Replaced Extension: " + str(ext) + " with  " + str(supported) )
                    print("Filename: " + str(filename) )
                    if not filename:
                        print("No Filename")
                        return
                    self.logger.info("Writing Template of Supported Columns to file:" + str(filename) )
                    data = {}
                    status = 'passed,failed,incomplete,blocked,skipped,waived,unexecuted,  \nwaived is remapped to \"incomplete\", \nskipped is remapped to \"Blocked\" '
                    date_format= '%Y-%m-%dT%H:%M:%S%z e.g. 2024-09-17T14:45:52-0500 '

                    for col in self.cfg['test run excel']:
                        if col == 'status':
                            data[self.cfg['test run excel'][col] ] = status
                        else:
                            
                            if re.match('.*date',col):
                                data[self.cfg['test run excel'][col] ] = date_format
                            else:
                                data[self.cfg['test run excel'][col] ] =''

                    for col in self.cfg['step keys']:
                        data[ self.cfg['step keys'][col] ] =''
                    outdata = {}
                    outdata['Sheet1'] = []
                    outdata['Sheet1'].append(data)
                    self.util.write_excel_each_sheet(filename,outdata)
                    # Stop processing Arguments
                    return

 
    def set_project_id(self,name=None,id=None):
         if not id:
             prj = self.get_project(name)
             if prj:
                 if 'id' in prj:
                    self.qta.project_id = prj['id'] 
                 else:
                     self.logger.error("Did not Find Project: " + str(name))
                     sys.exit()
             else:
                 self.logger.error("No Project found with Name: " + str(name))
                 raise

    def get_project(self,name=None):
        if not 'name':
            return None

        # Read the Projects from qTest, Pull the Id that matches tjhe 
        prj = {'name':name}
        
        data = self.qta.get_endpoint('projects',None,None,None,None,None)
        project = list( filter( lambda row: row['name'] == name , data ) )
        if project:
            for p in project:
                if 'id' in p:
                    prj['id'] = p['id']
                    self.logger.info("Found Project: \"" + str(prj['name']) + "\" ID: \"" + str(prj['id']) + "\"")
        return prj
    def escape(self,data,esc_val='\''):
        data = esc_val + str(data) + esc_val
        return data

    def conductor_batch(self,data):
        self.logger.info('Conductor Batch: ' + str(data) )

        # Data From Queued Test Run (Tr-xxxx)
        data['local_config'] = self.create_local_config(data)
        self.system = 'aus-onyx-7421'
        data['system'] = self.system
        batch_que_cmd=self.conductor_submit_format(data,'setup.sh')

        # Send to Conductor execute the SHell command
#        result = self.exec_shell(batch_que_cmd)
        result = {'id':'tr-123','returncode':0,
                  'stdout': json.dumps( {'id':'tr-123','returncode':0,'state':'Queued'} )
                 }
        if result['returncode'] == 0:
            # Success Queing the Batch Job
            self.batch_queue.enqueue(result['stdout'])
        else:
            self.logger.error("Failed to Queue TR: " + str(data['id']) )
            self.logger.error("Result: " + str(result.stderror) )

    def create_local_config(self,data):
        # Read config Template
        # replace cmd arg with:
        # cmdline = str(data['Test Step Description']) + str('Test Case Planned IP Specific Test Parameters / Command line'] )
        for i in self.tr_cmd_col:
            # Create the test 
            command=''
            if i in data:
                command = command + str(data[i])

            # Add the Commandline to Config
            for cmdline in self.test_config['tests']:
                cmdline['args']['cmd'] = command
                self.logger.info('commandline:' + str(cmdline['args']['cmd']) )

            # Save Configfile
            # use "id" as File name
            # self.batch_path
            fname = self.create_config_fname(data,self.batch_path)
            self.util.write_yaml(fname,self.test_config)


    def create_config_fname(self,data=None,path=None):
        # 
        self.local_config_suffix = '_local_config.yml'
        if id in data:
            name = str(data['id']) + self.local_config_suffix 
        else:
            name = 'rnd-' + str( random.randint(1000, 9999) )    
            self.logger.info("No TR Use Random Name: " + str(name))

        # Assemble the Name with Path
        tr_name = path + '/' + str(name) + self.local_config_suffix 
        self.logger.info("TR Filename: " + tr_name)
        return tr_name

    def conductor_submit_format(self,item={},env_script='setup.sh'):
        # Submit the Test
        # submit.sh <system> <cmdline.json>
        # conduct run standard "$NAME"  diags --system=aus-onyx-7421 --local_config=./test_conf100.yml --json-output
        cmd_dict = {}

        # wd
        cmd_dict['wd'] = 'cd ' + self.wd + ' && '
    
        # Source Environment 
        if env_script:
            cmd_dict['env'] = './setup.sh' + ' && '

        # app:
        cmd_dict['app'] ='conduct run standard'

        # System
        cmd_dict['system'] = '--system=' + self.escape(item['system'])

        # config:
        cmd_dict['local_config'] = '--local_config='
        cmd_dict['local_config'] = cmd_dict['local_config'] + ' ' + self.escape(item['local_config'])

        # Test Name
        cmd_dict['name'] =  self.escape(item['Name'])

        # out format
        cmd_dict['outf'] = '--json-output'

        # team
        cmd_dict['team'] = 'diags'

        # Assemble the Command LIne.
        cmd = ''
        for i in ['wd','env','app','name','team','system','local_config','outf']:
            cmd = cmd + str(cmd_dict[i]) + ' '
            self.logger.debug(str(cmd) )
            
        self.logger.info("Batch Submit Cmd: " + str(cmd))
        return cmd

    def exec_shell(self,cmd):
            # Execute a command
            self.logger.info('Cmd: ' + str(cmd))
            result = subprocess.run(cmd, capture_output=True,shell=True, text=True)
            self.logger.info("Result: " + str(result))
            # Check the return code
            self.logger.info(f"Return Code: {result.returncode}")

            # Print the output
            self.logger.info(f"Output:\n{result.stdout}")
            mseg=''
            if result.stdout:
                mseg = f"Output:{result.stdout}"
            if result.stderr:
                mseg = mseg + f"Errors:{result.stderr}"

            # Print the errors, if any
            self.logger.error(f"Errors:{result.stderr}")
            # Save the data. convert form Json to Python data.
            self.parse_exec_shell_result(result)
            return result

    def parse_exec_shell_result(self,result):
        # Read the data from the queued data.
        # Save the Data into self.queued_list
        self.batch_queue.enqueue( json.dumps(result) )
        

if __name__ == "__main__":
     import tempfile
     import logging
     batch = Batch_TR(None,"config.ini")
     logger = batch.logger
#     logger.setLevel(logging.WARNING)

     #filename = "./input/tr_list.xlsx"
     #data=wtr.util.read_excel_each_sheet(filename)
#     data = {}
#     data['name'] = 'Fake 1'
#     data['system'] = 'aus-onyx-7421'
#     data['local_config'] = './test_conf100.yml'
#     d = batch.create_local_config(data)
#     print(d)
#     cmd = batch.conductor_submit_format(data)
     # TEst Shell Command
#     cmd = 'echo2 Hello'

#     d = batch.exec_shell(cmd)
#     print( str(d) )


     parser = argparse.ArgumentParser( ) 
     parser.add_argument('-c' ,'--test_conf', nargs=1,   type=str, help='conductor test config to use as a templae . Replace "cmd:xxxx" with test step..' ) 
     parser.add_argument('-tr' ,'--test_runs', nargs=1,   type=str, help='Include a Filename with Test Runs Exported from qTest.' ) 

#     parser.add_argument('-optyml' ,'--options_yml', nargs=1,   type=str, help='Pass in the System Name, Project, Conductor Credentials Etc.  ' ) 
     

     sys.argv.append('-c')  # Read Test config
     sys.argv.append('./test_config.yml')  # Read Test config

     sys.argv.append('-tr')
     sys.argv.append('./runs/Diags-Base-Test Run-20250408.xlsx')
#     sys.argv.append('-prj')
#     sys.argv.append('DIAGS-Base Project')
#     sys.argv.append('-h')

     args = parser.parse_args()
     data = batch.main(args.__dict__) 



