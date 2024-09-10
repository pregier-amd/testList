import os
from qTestAPI import QtestAPI
import logging
import configparser
from LogClass import LogClass

class lookup_data(object):
    def __init__(self,config_file='config.ini',logfname=None):
        if(config_file):
           self.config_file = config_file
        self.cfg = configparser.ConfigParser(interpolation=None)
        self.cfg.read(self.config_file)
        self.lc = LogClass(None,logfname)
        self.logger = self.lc.logger

        self.logger.info("Info Test Logger")

        self.qta = QtestAPI(self.config_file,self.logger)
        self.projects = [{'id':self.cfg['qtest']['project_id']}]

        self.lookup_fname =  "./"

   

    def lookup_data(self,obj_data=[],obj_type='test-cases',matchValue=None,parentid=None,matchKey='name'):

      # Pull all data qTest of specified type:
      results = {}

      if len(obj_data) == 0:
        # get_tc_all( name, body, self.tc,obj_type='test-cases')
        directory = os.path.dirname(self.lookup_fname)
        filename = directory + "/" + obj_type + ".yml"
        # Pull the data from the qTest SAAS instance , multipl threaded 
        obj_data = self.get_obj_all_queued( None, None, obj_data , obj_type)

      #  template for using filter list(filter(lambda d: d['type'] in keyValList, exampleSet))
      if not parentid:
          filt_obj = list(filter(lambda d: d[matchKey] == matchValue ,obj_data ))
      else: 
          # use parent ID 
          try:
              # init to No Parent..
              filt_obj = []
              if len(obj_data) > 0:
#              if 'parent_id' in obj_data[0]:
                parents = ['parent_id','parentId','parentid']
                for parent_name in parents:
                    # Diferent parent id names based on if hte Parent is root, cycle, Suite
                    if parent_name in obj_data[0]:
                        # search for match
                        filt_obj = list(filter(lambda d: int(d[parent_name]) == int(parentid) ,obj_data ))
                        if len(filt_obj) > 0:
                            # break
                            break
          except Exception as e:
              self.logger.error("Filter Error: " + str(e) )
              self.logger.error("Filter Error: " + str(obj_type) + " Parent ID: " + str(parentid) )
#              self.write_excel("Exception_debug.xlsx",obj_data)
              raise


      for ob in filt_obj:
         self.logger.debug("Filtered Dict:" + str(ob['name']) + " ID: " + str(ob['id']) )

      return filt_obj,obj_data

    def get_obj_all_queued(self,name=None, body=None,obj_data=[],obj_type='test-cases'):  
      #use Web AI and get dat from qTest.
      if not name:
          # pull in all Test Cases
          name = '%'  

      #'test_case_version_id'
      #'test_steps'
      fields = ['name','id','pid','parent_id','properties','parentId','parentType','links']
      fields = ['*']
      if not body:
          match obj_type:
              case 'test-cases':
                fields.append('version')
                fields.append('test_case_version_id')
                fields.append('description')
                fields.append('test_steps')

      body={
            "object_type": obj_type ,
            "fields": fields,
            "query": "'name' ~ " + str(name)
           }
      # on error return the data.
#     data = self.qt.search_body(body, obj_type='test-cases')

#      data = self.qt.search_body_all(body, obj_type)
       #           search_object   (tablename='requirements',object_type='requirements',lastmodified=None,fields=None
      tablename = obj_type.replace("-", "_")
          #tablename='requirements',object_type='requirements',lastmodified=None,fields=None,query=None
      data = self.qta.search_object(tablename,obj_type,None,body,body)

      # Loads data into obj_data. and checks for errors
      self.store_obj_data_queued(data,obj_data)
      self.logger.info("Get All " + str(obj_type) + " Cnt:" + str(len(obj_data)))
      return obj_data
#      return results


    def store_obj_data_queued(self,indata={},obj_data={}):
      results = None
      #Has Items ..
      if len(indata) != 0:
          #results = data['items']
          #Add results to  test Case List
          # tc is stores {xxx:{id:123,name:xxx},yyyy:{'name':yyyy},z{}}
          for i in indata:
            # Save the Data from qtest into variable
            #esults = self.tc['name']] = i
    #              results = obj_data[i['name']] = i
            results = obj_data.append(i)
            #logging.info("Return Obj: Data: " + str(i) )
            # On success returns last data type{'id':xxx,'name':xxx}
      else:
          self.error = indata 
          self.logger.info("store_object no data:")
          results = []
      return results   


if __name__ == "__main__":
    # instance the Class
    ld = lookup_data('config.ini','lookup.log')
    logger = ld.logger
    logger.setLevel('INFO')
    tc = []
    data = ld.lookup_data(tc,'test-cases',"HARV000.001",None,'name')


    logger.info('Found: ' + str(data) )
