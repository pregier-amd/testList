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
from qTestAPI import QtestAPI

class write_tr(object):
   
    def __init__(self,logger = None, config_file =None ): 
        if(not logger):
            # Create a logfile
            filename = 'log/' + os.path.basename(__file__) + '.log'
            self.lc = LogClass(logger,filename)
            self.logger = self.lc.logger
        else:
            self.logger = logger

        self.util =  util(self.logger,config_file)

        self.cfg = self.util.cfg

        self.qta = QtestAPI('config.ini',self.logger)

        self.status_list = None
        pass
    def process_sheet(self,data=None):
        cnt = 1
        for row in data:

            # Check Each Row for Valid Data:
            # Skip the row if invalid
            if not self.validate_create_tr_log(row,cnt):
                # Invalid data in Skip row
                continue
            self.logger.info("Row:" + str(cnt) )

            self.logger.debug("Test Run:" + str(row))
            query = {"object_type": "test-runs","fields": ["*"],"query": "'Id' = '" + str(row['Id']) + "'" }
            tr = self.qta.search(None, None, 100, 1, 'asc',query)

            self.logger.debug("Test Run: " + str(tr))
            if 'items' in tr:
                for tr_row in tr['items']:
                    endpoint = 'test-runs/'+str(tr_row['id']) + '/test-logs'
                    trl_data = self.qta.get(None,None,None, endpoint,None)
                    tr_log_body = self.format_runlog(tr_row,row)

            self.logger.info("New Test Run Log Body: " + str(tr_log_body))
            self.logger.debug('TR:' + str(tr))

            # Write test run log:
            result = self.write_test_run_log(tr_log_body,tr_row)
            # update the Counter
            cnt += 1

    def validate_create_tr_log(self,row=None,cnt=None):
        result = True
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
                    values= ['Passed','Failed','Blocked','Incomplete','Skipped']
                    if not row[each_val] in values:
                        self.logger.error('Row:' + str(cnt) + ' Error Illegal Value row[' + str(each_val) + ']:' + '\'' + str(row[each_val]) + '\'')
                        result = False
                case _:
                    pass
        return result

    def write_test_run_log(self,body=None,trl=None):
        endpoint = '/test-runs/' + str(trl['id']) + '/test-logs'
        parameters = {'testRunId': trl['id'] }
        result = self.qta.post(None, None, endpoint,parameters,body)
        self.logger.debug("Test Run Log Result: " + str(result))

        return result

    
    def format_runlog(self,tr=None,input_row=None):
        body = None
        # Grab the the Test Steps,
        # Extract the Status from the row, create the runlog body.
#        tr_step= tr[]
        body = self.create_runlog_body(tr,input_row,self.cfg['test run excel']['status']) 
        return body
              
    def create_runlog_body(self,tr_row,input_row,status_col="Status",note_col="Notes"):
        outbody = {"id": 1,}
        # If the excel Test Run Log Column for Exec Dates. Use them.
        # elese use "Now" for execution date.
        dates = [ self.cfg['test run excel']['start_date'], self.cfg['test run excel']['end_date'] ]
        for data_name in dates:
            outbody[data_name] = self.format_exec_date(input_row,data_name)

        if status_col in input_row:
            outbody['status'] = self.format_status(input_row[status_col])
            if 'name' in outbody['status']:
               self.logger.info('Status' + '\'' + str(outbody['status']['name'])+ '\'' )

        outbody['result_number'] = 0 

        return outbody

    def format_status(self,instatus=None):
        # Fetch the status values from the project.
        status= None
        if not self.status_list:
            data=self.qta.get_execution_status()
            if data: 
                self.status_list =  data
        status = list( filter( lambda row: row['name'].lower() == instatus.lower() , self.status_list ) )
        for s in status:
            status = s
        return status
    def format_exec_date(self,tr_row=None,date_name=None,informat='%Y-%m-%dT%H:%M:%S%z',outformat='%Y-%m-%dT%H:%M:%S%z'):
        # if the Date Column is in the Row. Use the date.
        date_time = None
        if date_name in tr_row:
            # Convert the Specified Date Time Format.
            date_time = self.qta.time_format(tr_row[date_name],informat,outformat)
        else:
            # No Column Use now:
            date_time = self.qta.time_gen(None,format_string='%Y-%m-%dT%H:%M:%S%z') 
        return date_time

    def main(self,args=None):
        self.logger.info(args)
        self.project = None
        for key in args:
            match key:
                case 'test_runs':
                    if not args['test_runs']:
                        continue
                    # 
                    if not self.project:
                       # read the Projects and
                       for p in args['project']:
                           self.set_project_id( p,None )
                       if not self.project:
                           self.logger.error("No Project Set Exit:")

                    for file in args['test_runs']:
                      data = self.util.read_excel_each_sheet(file)
                      for sheet in data:
                          self.logger.debug( str(file) + "[" + sheet + "] Row Cnt: " + str(len(data[sheet]) ) ) 
                          self.process_sheet(data[sheet])
                case 'project':
                    for name in args['project']:
                      data = self.get_project(name)
                      if data:
                          self.project = data
                          self.set_project_id( data['name'], data['id'])
                          pass
 
    def set_project_id(self,name=None,id=None):
         if not id:
             prj = self.get_project(name)
             if prj:
                self.qta.project_id = prj['id'] 
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
                    self.logger.info("Found Project: " + str(prj['name']) + " ID: " + str(prj['id']))
        return prj

if __name__ == "__main__":
     import logging
     wtr = write_tr(None,"config.ini")
     logger = wtr.logger
     logger.setLevel(logging.INFO)

     #filename = "./input/tr_list.xlsx"
     #data=wtr.util.read_excel_each_sheet(filename)

     parser = argparse.ArgumentParser("Execute Workload:")    
     parser.add_argument('-tr','--test_runs', nargs=1, type=str, help=' Include a Filename with Test Runs Exported from qTest' ) 
     parser.add_argument('-prj','--project', nargs=1, type=str, help='Name of Project' ) 

    # sys.argv.append('-tr')
    # sys.argv.append('./input/test_tr_update.xls')

    # sys.argv.append('-prj')
    # sys.argv.append('DIAGS-Base Project')


     args = parser.parse_args()
     data = wtr.main(args.__dict__) 



