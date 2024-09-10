from LogClass import LogClass
from util import util
import re
import os
from datetime import datetime
import argparse
import yaml
import sys 
from qTestAPI import QtestAPI

class User(object):

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
 
    def read_users(self,project="Diags-Venice"):
        if not project:
            self.logger.erro("Error: No Project Given for read_users:")
            return
        uri =  "/api/v3/search/"
        endpoint = "user?projectName=" + str(project) + "&pageSize=5000"
        self.qta
        data = self.qta.get(None,uri,None,endpoint,None)
        return data

    def extract_email(self,data):
        outdata = []
        for line in data.split(";"):
            m = re.search("<(.*)>", line)
            if m: 
                email = m[1]
                self.logger.debug("Email: " + str(email) )
                outdata.append(email)
        return outdata
    def main(self,args=None):
        self.logger.info(args)
        for key in args:
            match key:
                case 'email':
                    for file in args['email']:
                      data = self.util.read_file(file)
                      data = self.extract_email(data)
                      self.email_set = set(data)
                      self.logger.info("Email List has:" + str(len(self.email_set)) + " Unique Emails")
                      self.print_email(self.email_set)
                    
                case 'project':
                      for p in args['project']:
                          users= self.read_users(p)
                      if 'items' in users:
                         self.logger.info("Users asssinged to Project:")
                         self.users = []
                         for row in users['items']:
                              self.users.append(row['username'])
                      new = self.diff_lists(self.users,self.email_set)
                      remove_list = self.diff_lists(self.email_set,self.users)
                      self.logger.info("Users in Project: " + str( len(self.users) ) )
                      self.print_email(new)
                      self.logger.info("\nend of existing users\n")

                      self.logger.info("\nNew Entries needed: " + str( len(new) ) )
                      self.print_email(new)
                      self.util.write_txt("add_list.txt",new)
                      self.logger.info("\nend\n")

                      self.logger.info("\nExtra Users Not in Email List: " + str( len(remove_list) ) )
                      self.print_email(remove_list)
                      file = "remove_list.txt"
                      self.logger.info("Write File: " + file)
                      self.util.write_txt(file,remove_list)
                      self.logger.info("\nend\n")
    
    def diff_lists(self,existing=None,update=None):
        # Return the list of entries in update and not in existing
        new = []
        # loop through the New Entries
        # save the new entries not in the Existing List.
        for new_entry in update:
            if not new_entry in existing:
                new.append(str(new_entry) + '\n')
        return new

    def print_email(self,data):
        self.logger.info( str(data) )

if __name__ == "__main__":
    import logging
    # Class instance
    cl = User(None,"config.ini")
    logger = cl.logger
    logger.setLevel(logging.INFO)

    #filename = "./input/tr_list.xlsx"
    #data=wtr.util.read_excel_each_sheet(filename)

    parser = argparse.ArgumentParser("Execute Workload:")    
    parser.add_argument('-em','--email', nargs=1, type=str, help=' --em ./path/file.txt <project string> Email List from DL is <strings>  <first.last@amd.com> ; <strings> <email>;' ) 
    parser.add_argument('-prj','--project', nargs=1, type=str, help=' --prj <string> I.e. Diags-SWV' ) 

    sys.argv.append('-em')
    sys.argv.append('./input/email.txt' )
    sys.argv.append('-prj')
    sys.argv.append('Diags-SWV' )


    args = parser.parse_args()
    data = cl.main(args.__dict__) 



