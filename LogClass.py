import logging
import sys
from datetime import datetime
import os

class LogClass(object):

    def __init__(self,logger = None, filename=None, dateFlag=True ):
        if(not logger):
            if filename:
                if(dateFlag):
                    filename= os.path.splitext(filename)[0]  
                    nowstr = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
                    filename = filename + "_" + nowstr + '.log'
                self.logger = self.log(filename)
        else:
            return logger

    def log(self,outfile=None): 
        logging.basicConfig(
                    filemode='w',
                    format='%(levelname)s - %(asctime)s - %(message)s',
                    level=logging.INFO,
                    filename=outfile
                    )
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
        #logging.info("Logging to File: " + outfile)
        logging.getLogger().setLevel(logging.WARNING)
        return logging.getLogger('logger')




