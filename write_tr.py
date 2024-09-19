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

class write_tr(object):
   
    def __init__(self,logger = None, config_file =None ): 
        sys.tracebacklimit = 0

        if(not logger):
            # Create a logfile
            filename = 'log/' + os.path.basename(__file__) + '.log'
            self.lc = LogClass(logger,filename)
            self.logger = self.lc.logger
        else:
            self.logger = logger

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


        pass
 

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


    def process_row_queue(self, queue):
        while True:
            # Read the Queue using multile threads.
            command =  queue.get()
            msg = "Start Row:" + str( command['cnt']) + " Worker: " + str(threading.current_thread().name  ) 
#            self.logger.info(msg)
            self.update_tr_row(command)
            queue.task_done()



    def process_sheet(self,data=None):
        start_ts = time.time()
        cnt = 2
        for row in data:
            command = {'row':row,'cnt':cnt }
            # Write the Test Run
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

    def main(self,args=None):
        self.logger.info("Input Arguments: " + str(args) )
        self.project = None
        for key in args:
            if not args[key]:
                continue
            match key:
                case 'test_runs':
                    if not args['test_runs']:
                        continue
                    # 
                    if not args['project']:
                        self.logger.error("Error: No Project Given: use \" -prj <project name>\" ")
                        return
                    if not self.project:
                       # read the Projects and
#                       for p in args['project']:
                       self.set_project_id( args['project'])
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
                          self.process_sheet(data[sheet])
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

if __name__ == "__main__":
     import logging
     wtr = write_tr(None,"config.ini")
     logger = wtr.logger
#     logger.setLevel(logging.WARNING)

     #filename = "./input/tr_list.xlsx"
     #data=wtr.util.read_excel_each_sheet(filename)

     parser = argparse.ArgumentParser( ) 
     parser.add_argument('-t'  ,'--template' , nargs='?', type=str, const='template.xlsx' ,
                        help='Specify Filename for template file default:(%(const)s) Must Have Ext: <\"*.xlsx\"> , Date Format: yyyy-mm-ddThh:mm:ss+0000 e.g.2024-09-18T08:30:20-0500' )
     parser.add_argument('-tr' ,'--test_runs', nargs=1,   type=str, help='Include a Filename with Test Runs Exported from qTest.' ) 
     parser.add_argument('-prj','--project'  , nargs='?', type=str, const = 'DIAGS-Base Project', help='Name of Project. default:(%(const)s)'  ) 
       #'Writes \"template.xlsx\" Template with supported columns. Only Required Columns: id,status, Date time format:\%Y-\%m-\%dT\%H:\%M:\%S\%z e.g. 2024-09-17T14:45:52-0500') 


#     sys.argv.append('-t')  # Dump the template
#     sys.argv.append('-tr')
#     sys.argv.append('./input/template.xlsx')
#     sys.argv.append('-prj')
#     sys.argv.append('DIAGS-Base Project')
#     sys.argv.append('-h')

     args = parser.parse_args()
     data = wtr.main(args.__dict__) 



