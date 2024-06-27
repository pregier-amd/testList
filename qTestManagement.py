import re
from sqlServer import Log_Class
from sqlServer import SqlServ
from qTestAPI import QtestAPI

from os import truncate
import os
import ssl
import configparser
import pandas as pd
import logging

import re

# Manage the qTest DB 
class QtestManagement(object):
    def __init__(self,config_file='config.ini'):
        if(config_file):
           self.config_file = config_file
        self.cfg = configparser.ConfigParser()
        self.cfg.read(self.config_file)

        # setup the logger
        self.log = Log_Class(os.path.basename(__file__))
        self.logger = self.log.logger
        self.logger.setLevel(self.cfg['logger']['level'])
 
        #pull in the Configuration File
        self.cfg = configparser.ConfigParser()
        self.cfg.read(self.config_file)

        # qTest Utilities
        self.qta = QtestAPI(self.config_file)
        self.qta.logger =self.logger

        # ssql Utilities
        self.sqla = SqlServ(self.config_file)
        self.sqla.logger = self.logger
    def update_table_queue_init(self):

    def get_projects(self,filter='Diags-'):
        # access the Project, 
        # renme keys as defined in schema Excel            
        apidata = self.qta.projects()
        data=[]
        for row in apidata:
            if(filter):
                pattern = filter
                m = re.search(pattern, row['name']) 
                self.logger.info(row['name'])
                if(m):
                   data.append(row)
                   self.logger.info('Found Project: ' + row['name'])

        # upsert the data and create a new one if needed.
        table_name = 'projects' + self.cfg['ssql']['suffix']
        self.populate_table(table_name,data,'u')

        # project data       
        return data
    def populate_table(self,table_name,indata,operation='u'):
        
        cnt = self.sqla.populate_table(table_name,indata,operation)
        self.logger.info("Table: " + str(table_name))
        return cnt



if __name__ == "__main__":
    # instance the Class
    qtm = QtestManagement('./config.ini')
    logger = qtm.logger
    logger.info('Hello World')

    data = qtm.get_projects('Diags-')
    for p in data:
        logger.info("p: " + str(p['name']) )
    qtm.populate_table(table_name,engine,schema_dict,indata,operation='u')
