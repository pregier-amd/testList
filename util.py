import pandas as pd
import configparser
import os
import sys
from LogClass import LogClass
from datetime import datetime
import pytz
# pip install pyyaml:
import yaml

class util(object):
    def __init__(self,logger = None, config_file=None ): 
        if(not logger):
            # Create a logfile
            filename = __file__
            self.lc = LogClass(logger,filename)
            self.logger = self.lc.logger
        else:
            self.logger = logger

        #Configuration File Prosessing
        if config_file:
           self.config_file = config_file #'config.ini'
        else:
           self.logger.error("No Config File: Exiting")
           sys.exit()

        self.cfg = configparser.ConfigParser()
        self.cfg.read(self.config_file)
        pass

    def read_file(self,filename):
        
        if not os.path.isfile(filename):
            self.logger.warning("Error File does not exist: " + str(filename))
            # return None
            return None
        extension = os.path.splitext(filename)[1]
        match extension.replace('.',''):
            case 'txt':
                # Text File
                data = self.read_txt(filename)
            case 'yml'| 'yaml':
                # yaml format
                data = self.read_yaml(filename)
            case 'xlsx','xls','xlsm':
                # excel:
                self.read_excel_each_sheet(filename,skip=[])
        return data
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
    def read_txt(self,filename):
        if not os.path.isfile(filename):
            self.logger.warning("Error File does not exist: " + str(filename))
            return None
        with open(filename, 'r') as file:
            data = file.read()
        return data
    def read_yaml(self,filename):
        if not os.path.isfile(filename):
            self.logger.warning("Error File does not exist: " + str(filename))
            return None
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
        return data

    def write_txt(self,filename=None,data=None):
        
        if not data:
            self.logger.warning("Error No Data to Write" )
            return None

        # Open the File
        file = open(filename, "w")
        # Text version
        if isinstance(data,list):
            for row in data:
                file.write(row)
        else:
            # Not a List
            file.write(row)

        # Close the File
        file.close()

    def write_yaml(self,filename=None,data=None):
        
        if not data:
            self.logger.warning("Error No Data to Write" )
            return None

        # Open the File
        file = open(filename, "w")
        # Text version
        data = file.write(yaml.dump(data))

        # Close the File
        file.close()


    def write_excel_each_sheet(self,filename,data,same_sheet=False):
           if(len(data) == 0):
               self.logger.error("Can't Write File: " + filename + " No Data to Write.")
               return
           self.logger.info('Writing File: '+ os.path.abspath(filename) )
           with pd.ExcelWriter(filename) as writer:
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name='Sheet1',index=False)

    def read_excel_each_sheet(self,filename,skip=[]):
           xls = pd.ExcelFile(filename)
           data ={}
           for sheet in xls.sheet_names:
              if(sheet == 'Cover Page'):
                  continue
              data[sheet] = xls.parse(sheet_name=sheet,skiprows=skip,encoding='utf-8',charset='iso-8859-1').fillna(' ')
              data[sheet] = data[sheet].to_dict('records')
              self.logger.info("Read Sheet: " + sheet + " Records: " + str(len(data[sheet])) )
           return data

    def write_excel_each_sheet(self,filename,data,same_sheet=False):
           if(len(data) == 0):
               self.logger.error("Can't Write File: " + filename + " No Data to Write.")
               return
           self.logger.info('Writing File: '+ filename)
           total_data =[]
           with pd.ExcelWriter(filename) as writer:
             if(same_sheet != True):
                # Seperate sheets
                for sheet_name in data:
                    # Skip Empty Dictionary.
                    size = len(data[sheet_name])
                    if(size == 0):
                        continue
                    df = pd.DataFrame(data[sheet_name])
                    df.to_excel(writer, sheet_name=sheet_name,index=False)
             else:
                for sheet_name in data:
                   # Skip Empty Dictionary.
                   size = len(data[sheet_name])
                   if(size == 0):
                        continue
                   for r in data[sheet_name]:
                      total_data.append( r)
                # write _all of the data in one sheet
                if( len(total_data) != 0):
                    df = pd.DataFrame(total_data)
                    df.to_excel(writer, sheet_name='Sheet1',index=False)
if __name__ == "__main__":
    pass
