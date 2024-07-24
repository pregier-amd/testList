#from qTestAPI import QtestAPI
from qTestAPI import QtestAPI
import configparser
import argparse
import os
import re
import sys
from sqlServer import Log_Class
import pandas as pd
import os.path
import json
from ListFilter import ListFilter

class test_list(object):
    def __init__(self,config_file=None):
            
        if(not config_file):
           config_file = 'config.ini'

        #Append the Local directory to the Filename
        config_file= os.path.dirname(__file__) + "/" + str(config_file)           
        self.config_file = config_file
        self.cfg = configparser.ConfigParser(interpolation=None)
        self.cfg.read(self.config_file)

        # setup the logger
        filename ='/TEMP/' +  os.path.splitext(os.path.basename(__file__))[0] + '.log' 
        self.log = Log_Class(filename)
        
        self.logger = self.log.logger
        self.logger.setLevel(self.cfg['logger']['level'])

        # qTest Utilities
        self.qta = QtestAPI(self.config_file)
        self.qta.logger =self.logger

        #List Filter
        self.lf = ListFilter(self.logger,"config.ini")


#    def search_for_container(self,args=None):
    def search_for_container(self,argsDict=None):

        # Set the Supported Containers to look into
        self.supported_obj = ['releases','test_cycles','test_suites','test_runs']
    

        if not args.project:
            # No Project Specified Return:
            self.logger.error("No Project Specified: Need parameter < -prj Diag Base Project>")
            return []

        #use the verbose argument and se the logger level.
        self.set_logger_level(argsDict)
        filename = self.filename_format(argsDict)

        # build up the data 
        self.outrow={}
        self.outrow = self.init_record(self.outrow,argsDict)

        
        # Set the Project
        for prj in args.project:
           prjid = self.set_project_id(prj)
           if not prjid:
              self.logger.error("No Project found for string: " + str(prj) )
              return
           else:
              self.logger.info("Found Project: " + str(prj) )
       
        
        # Target the specified containers
        # report hte test runs and test data.
        for object_type in argsDict:
            # supported containers, skip others
            # must have data.
            if not argsDict[object_type] or not object_type  in self.supported_obj:
#            if not argsDict[object_type] or object_type == 'project' or object_type == 'filename':
                # go to next container
                continue
            # format to qtest object type "-" not "_"
            objType = object_type.replace('_','-')
            data=[]
            for name in argsDict[object_type]:
               data =  self.get_object_list(objType,name)
               data = self.process_obj_data(objType,data)
        # Filter # [{col='tc_Release_Suite',op='contains',value='BP', group='and'},{},{}]

        #if there are Filter terms then decode them and process them
        if argsDict['fterms']:
            for terms in argsDict['fterms']:

                # covert from dictionary to specific Filter format.
                terms = self.set_filter(json.loads(terms) )

                # Use the Filter ter,s to filter list
                data = self.filter_list(data, terms)


        if 'filename':
            self.write_excel_each_sheet(filename,data)
        return data

    def filter_list(self,data=[],terms=None):
        if terms:
            self.logger.info("Filter Terms: " + json.dumps(terms) )
            data = self.lf.filt(data,self.set_filter(terms))
        return data

    def set_filter(self,indata=None):
        terms=[]
        if not isinstance(indata,list):
            # if not a list then create one.
            indata = []
            indata.append(indata)

        for term in indata:
            # col='tc_Release_Suite',op='contains',value='BP', group='and'
            filter_term = self.lf.term(term['col'],term['op'],term['value'],term['group'])
            terms.append(filter_term)
        return terms

    def set_logger_level(self,argsDict={}):
        if argsDict['verbose']:
            for level in argsDict['verbose']:                
                self.logger.setLevel( level.upper() )

    def set_project_id(self,name):
        projects = self.qta.get_endpoint('projects',None,None,name,None)
        data = list( filter( lambda k: k['name'] == name , projects) )
        prjid =None
        for row in data:
            self.logger.info("Set Project: " + str(row['name']) + ' ID: ' + str(row['id']))
            self.qta.project_id = row['id']
            prjid = row['id']
        return prjid

    def get_object_list(self,object_type=None,name=None):
        # Build Search Query basedon type.
        query = self.search_query(None,name,object_type,False)
        self.logger.info("Search query: " + str(query) )                               
        data = self.qta.search_object('generic',query['object_type'],None,None,query)
        return data

    def filename_format(self,args={},include=None):
        if not include:
            include = ['filename']
        filename = 'qTestList'
        fstring=''
        for i in include:
            if args[i]:
                if args[i]:
                    for data in args[i]:
                        match i:
                           case 'filename':
                             extension = os.path.splitext(data)[1]
                             filename = os.path.splitext(data)[0]
                           case '_':
                            #append terms to filename
                            fstring = fstring + '_' + data
                    # append the extension
                    if not extension == '.xlsx':
                        extension = '.xlsx'
                    date_time = self.qta.time_gen(None,'%Y_%m_%dT%H_%M_%S')
                    # create filename with date
                    filename = filename + fstring + '_' + str(date_time) + extension
        return filename

    def init_record(self,outrow=None,args=None):

        # make sure that all possible input types have a column.
        for k in self.supported_obj:
                outrow[k.replace('_','-')] = ''

        if 'project' in args:
            for p in args['project']:
                self.outrow['project']=p
        return outrow


    def process_obj_data(self,objType=None,object_data=[],outrow={},outdata=[]):

        # loop through each of objects 
        if isinstance(object_data,dict):
            object_data = [object_data]
        for row in object_data:

            self.logger.info("Obj: " + str(row['name']) )
            # Capture the Hierarchy     
            if 'name' in row:
                self.outrow[objType] = row['name']
              
            match objType:
                case 'releases':
                    for mapRl in [{'releases':'test-cycles'},{'releases':'test-suites'},{'test-cycles':'test-runs'}]:
                        # read from Object the next lower container data            
                        child,leafdata = self.get_child_container_data(objType,row,mapRl)
                        # recursive call get the data in lower containers of row.
                        self.process_obj_data(child,leafdata,self.outrow,outdata)
                    return outdata
                case 'test-cycles':
                    new_href= self.build_self_href('self',row['links'],'test-cycle',row['id'], objType)
                    # add in in the sametype link to see if 2 Levels of cycle -> Cycle Hierarchy is present.
                    row['links'].append({'rel':objType,'href':new_href})                    

                    # look for moree Cycle,Suites,Runs
                    for mapRl in [ {objType:objType},{'test-cycles':'test-suites'},{'test-cycles':'test-runs'}]:
                        # read from Object the next lower container data            
                        child,leafdata = self.get_child_container_data(objType,row,mapRl)
                        # recursive call get the data in lower containers of row.
                        self.process_obj_data(child,leafdata,self.outrow,outdata)
                    return outdata

                case 'test-runs':
                    self.tr_row = row
                case 'test-case':
                    self.tc_row = row
                    record = self.build_row(self.outrow,self.tr_row,self.tc_row)
                    outdata.append(record)
                    self.logger.debug("Test List Record: " + str(outdata) )
                    return outdata
                case '_':
                    pass
            # read from Object the next lower container data            
            child,leafdata = self.get_child_container_data(objType,row)

            #recursive call get the data in lower containers of row.
            self.process_obj_data(child,leafdata,self.outrow,outdata)

        return outdata

    def build_self_href(self,child='self',links=None,object_type=None,parentId=None, parentType=None):
        # Convert Self Href by removing the ID
        # build the link to check for object_type/
        # object_type
        # ?parentId=<parentId>&parentType=<object_type>
        href_f = list( filter( lambda k: k['rel'] == child , links) )
        for item in href_f:
            href = item['href']
            m = re.match( r'.*(\/[0-9]*).*$',href)
            href = href.replace(str(m.group(1)),'')
            params = '?' + 'parentId=' + str(parentId) + '&parentType=' + object_type
            href = href + params
            self.logger.debug("Build Href: " + href)
        return href

    def build_row(self,outrow={},tr_row={},tc_row={}):
        # Set the Column Names and Create Dict with all data
        data = {}        
        self.merge('',outrow,data)
        self.merge('tr_',tr_row,data)
        self.merge('tc_',tc_row,data)
        return data

    def merge(self,prefix=None,adata={},bdata={},jsonList=None):
        if not jsonList:
            jsonList = ['test_steps','description','Description','web_url','links','latest_test_log']
        outdata = {}
        for k in adata:
            if k in jsonList:
                bdata[prefix + k] = json.dumps(adata[k])
            else:
                bdata[prefix + k] = adata[k]
    def get_child_container_data(self,objType=None,indata=[],child_map=None):
        data = []
        # set the Next lower container,
        # use the presented map if needed 
        if not child_map:
            # Use filter function to find needed endpoint.
            child_map = { 'releases':'test-cycles','test-cycles':'test-suites','test-suites':'test-runs','test-runs':'test-case' }
        child = None
        if objType in  child_map:
            child = child_map[objType]
        if not child:
            return  [],data
        # lookup the link to the lower container
        if not 'links' in indata:
            self.logger.info("No links in object data:")
            return child,data
        # Filter the child link: links
        child_link = list( filter( lambda k: k['rel'] == child , indata['links']) )
        for row in child_link:
            endpoint  = re.match('.*\/(' + child + '.*)$',row['href']).group(1)
            if child == 'test-case':
                endpoint = endpoint + '&' + 'expand=teststep'
            if endpoint:
                data = self.qta.get_endpoint('generic',endpoint,None,None,None)
        return (child,data)

    def process_containers(self,pid=None,name=None,object_type=None,leaf=None):

        # pid is object type data:
        if 'pid' in row:

            pid = row['pid']
            object_type = self.pid_to_object_type(pid)

            match object_type:
                # Test Run Found Get the Test Cases and append the data
                case 'test-runs':
                    pass
                case 'test-cases':
                    pass
                # Get Lower Level Container
                case '_':
                    leaf = True
                    self.process_containers(self,pid=None,name=None,object_type=None,leaf=None)

        query = self.search_query(pid,name,object_type,leaf)
        self.logger.info("process_containers Search query: " + str(query) )                               
        data.extend( self.qta.search_object('generic',query['object_type'],None,None,query) )

    def pid_to_object_type(self,pid=None):
        typesDict = {'rl-':'cycles', 'cl-':'test-suites', 'ts-':'test-runs', 'tr-':'test-cases'}
        data = None
        for k in typesDict:
            m = re.match('.*' + k + '.*',pid)
            if m:
                data = typesDict[k]
        return data


    def search_query(self,pid=None,name=None,object_type=None,leaf=True,fields='*'):       
        data = {'fields': fields}
        data['object_type'] = object_type
        # look for PID format of the name
        m = re.match('^.*?-[0-9]*?$',name)
        if m:
            pid = name            
        # Pull the data from the level below the current one in hte Hierarchy
        if leaf:
            typesDict = {'releases':'cycles','test-cycles':'test-suites','test-suites':'test-suites','test-suites':'test-cases'}
            # Lookup the next object type
            data['object_type'] = typesDict[object_type]
            # Name query, Get all objects in next lower level.
            data['query'] = "'name' ~ " + '\'%\''
        else:            
            if pid:               
                # ID based Query
                data['query'] = "'id' = " + '\'' + str(pid) + '\'' 
            else:
                # Name query
                data['query'] = "'name' ~ " + '\'' + str(name) + '\''
        return data
    def write_excel_each_sheet(self,filename,data,same_sheet=False):
           if(len(data) == 0):
               self.logger.error("Can't Write File: " + filename + " No Data to Write.")
               return
           self.logger.info('Writing File: '+ os.path.abspath(filename) )
           with pd.ExcelWriter(filename) as writer:
                df = pd.DataFrame(data)
                df.to_excel(writer, sheet_name='Sheet1',index=False)


if __name__ == "__main__":
    
    from ListFilter import ListFilter


    # Command line Parser
    parser = argparse.ArgumentParser("Manage qTest Data:")
  
    # instance the Class
    #Path Added in constructor
    tl = test_list("config.ini")
    logger = tl.logger

    tlf = ListFilter(logger,"config.ini") 


    logger.info("Start:")
    
    start_ts = tl.qta.time_gen(True)
    parser.add_argument('-v','--verbose', nargs=1, type=str, help='<verbose [error]> Options are debug,info,warning,error Default is error'  ) 
    parser.add_argument('-f','--filename', nargs=1, type=str, help='<name of excel file>, .xlsx Output filename (.xlsx)' ) 
    parser.add_argument('-prj','--project', nargs=1, type=str, help='<name of project>, Specify the Project Name') 
    parser.add_argument('-rl', '--releases', nargs=1, type=str, help='<name of release or rl-xxx>, <[all]> Release hierarchy.') 
    parser.add_argument('-cl', '--test-cycles', nargs=1, type=str, help='<name of test-cycles or cl-xxx>, <[all]> specifying the test cycles hierarchy.') 
    parser.add_argument('-ts', '--test-suites', nargs=1, type=str, help='<name of test-suites or ts-xxx>, <[all]> specifying the test test suite hierarchy.')
    parser.add_argument('-fterms', '--fterms', nargs=1, type=str, help='List of Filter arrays Supported op "=/<>/contains", group="and/or" [{col:"<excel Column>",op:"contains",value:"tng", group:"and"},{},{}]')
    

    # Get the data from the rl->cycle->

#    sys.argv.append('-v')
#    sys.argv.append('info')
    
 #   sys.argv.append('-ts')
 #   sys.argv.append('ts-379')
    # sys.argv.append('-fterms')

   # terms = [ 
   #           {'col':'tc_Release_Suite','op':'contains','value':'BQ', 'group':'and'},
   #           {'col':'tc_Release_SKU','op':'contains','value':'default', 'group':'and'},
   #           {'col':'tr_Planned_End_Date','op':'<','value':'2024-06-19T15:38:19+00:00', 'group':'and'}
   #         ]
   #  sys.argv.append( json.dumps(terms) )

#    sys.argv.append('RL-70')

#    sys.argv.append('-ts')
#    sys.argv.append('TS-174')

 #   sys.argv.append('-cl')
 #   sys.argv.append('Test List - MI350')    
#    sys.argv.append('CL-269')

 #   sys.argv.append('-f')
 #   sys.argv.append('output/outfile.xlsx')
 #   sys.argv.append('-prj')
 #   sys.argv.append('Diags-Breithorn')


    args = parser.parse_args()
    # Convert the Args to a Dictionary
    data = tl.search_for_container(args.__dict__) 



    logger.info("Script Duration: " + str(tl.qta.calc_duration(start_ts)) + "Secs"  + "Rows: " + str(len(data)))
    logger.info(__file__ + " Complete")
    cnt = 1
    max = 5
    for row in data:
          log = ''
          for col in ['tr_id','tc_Ip','tc_Release_Suite','tc_Release_SKU','tc_Release_Flow','tc_OL_Milestones']:
            log = log + str('Row['+col+']:\t' + str(row[col]) ) + "\n"
          logger.info("Row:\n" + log)
          cnt += 1
          if cnt > max:
              logger.info("Exit after Max Cnt:" + str(max))
              break
    pass


    sys.exit(0)