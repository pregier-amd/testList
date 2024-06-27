from ast import Try
from lib2to3.pgen2.token import NAME
import re
import logging
from tokenize import Name
from xml.dom.minidom import CDATASection
import pandas as pd
import pyarrow.parquet as pq
from pyarrow.parquet import read_schema
from pyarrow.parquet import read_table
import numpy as np
import json
import os
import shutil 
import sys
import time
import pymssql  
from datetime import datetime, timedelta
from datetime import date
from subprocess import run
from pathlib import Path
import pathlib

import configparser

# sqlalchemy
import sqlalchemy 
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from sqlalchemy.orm import sessionmaker
# mysql COnnector
#import mysql.connector



class Log_Class(object):
    def __init__(self,logname="logger_out"):
        self.logname = logname

        filebase = self.logname + "_" + str(date.today())
        logging.basicConfig(
                    filemode='w',
#                    format='%(levelname)s-%(asctime)s-%(module)s:%(funcName)s: %(message)s',
                    format='%(levelname)s-%(asctime)s-%(funcName)s: %(message)s',
                    level=logging.INFO,
                    filename=filebase + ".log"
                   )
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
        self.logger = logging.getLogger()

class ExcelClass(object):
    def __init__(self):
        self.logger = logging.getLogger()
        pass
       
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


class SqlServ(object):
    def __init__(self,config_file='config.ini'):
        if(config_file):
           self.config_file = config_file
        self.cfg = configparser.ConfigParser()
        self.cfg.read(self.config_file)

        # Setup the Logger.
        self.filebase = os.path.splitext(sys.argv[0])[0]
        self.logger = self.logger = logging.getLogger()


         # Get the Excel Class
        self.exc = ExcelClass()

        self.script_path    = os.path.dirname(os.path.realpath(__file__))
        self.sch_filename   = self.script_path + '\\' + self.cfg['schema']['filename']           
        # if the schema file exists read the data.
        if(os.path.isfile(self.sch_filename) ):
            self.schema_data = self.get_schema(self.sch_filename)
        else:
            self.logger.error('No Schema File: ' + str(self.sch_filename))

        # Create Connection to SSQL Server
        self.connection_session()

    def get_schema(self,filename=None):
        self.schema_data    = self.exc.read_excel_each_sheet(self.sch_filename)
        return self.schema_data

    def connection_session(self):
        # Check if the Sengine and Session have been created.
        
        if( not hasattr(self, 'engine') ):
            conn_string = str(self.cfg['ssql']['conn_string'])

            self.logger.info("Connection String: " + conn_string)
            self.engine = create_engine("mssql+pymssql://ATLSQLPRDDBV07/qTest_API?charset=utf8;Integrated Security=SSPI",echo=False)
            self.Session = sessionmaker(self.engine)

            conn = self.engine.begin()
            pass

    def adapt_array(self,arr):
        """
        http://stackoverflow.com/a/31312102/190597 (SoulNibbler)
        """
        out = io.BytesIO()
        np.save(out, arr)
        out.seek(0)
        return sqlite3.Binary(out.read())

    def format_column_pandas_schema(self,data,field='field_name',type='pandas_type',sep=','):
        data =  str(data[field]) + " " + data[type] + sep
        return data


    def create_table_sql(self,data,table_name = "DEFAULT"):
        query = 'CREATE TABLE ' + table_name + "(" 
        max_len = len(data)
        for count, item in enumerate(data, start=1):
             if (count < max_len ):
                sep =","
             else:
                 sep =''
             self.logger.debug("Item: "+str(item))
             query = query + str(self.format_column_pandas_schema(item,'fields','sqlalchemy',sep))
        query = query + ")"
    
        return query


    def create_table_primary_key(self,df,table_name,schema_tables=[],temp_table=None,con=None):
        if(temp_table):
            self.logger.info("Create Table Primary key: " + temp_table)
            # use the schema from the Targeted table_name
            query = self.create_table_sql( schema_tables[table_name],temp_table)
        else:
            # not a temp table
            self.logger.info("Create Table Primary key: " + table_name)
            query = self.create_table_sql( schema_tables[table_name],table_name)
     
        self.logger.debug("Create Table Query: " + str(query))
        if(con):
           mesg = con.execute(text(query) )
        else:
           with self.engine.begin() as con:
               mesg = con.execute(text(query) )
        if(mesg):
            self.logger.info(mesg)
        return mesg
     


    def create_table(self,filename,table_name):
        #  Needs Schema
        schema = read_schema(filename)
        create_query = self.create_table_sql( schema.pandas_metadata['columns'],table_name)
        query = text(create_query)
    
        mesg = self.engine.connect().execute(query)
        if(mesg):
            self.logger.info(mesg)
        return mesg

    def set_data_type(self,df=None,type_spec=None,col_list=['pathids','pathpids']):
       df_cols =  df.columns
       for i in col_list:
           if i in df_cols:
              if(type_spec == 'str'):
                 df[i] = df[i].apply(str)

    def check_table(self,df,table_name,primary_key = 'id'):
       # Is the Table Present

       with self.engine.begin() as con:
          query = text('SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = N\'' + table_name + '\' ;')
          rows = con.execute(query).fetchall()
          self.logger.info("Table Exists Rows Read:" + str( len(rows) ) )
       return rows

    def add_primary_key(self,df,table_name):
       for index, row in df.iterrows():
         primary_key = row.first_valid_index()
     
       # add Primary Key = 'id' 
       with self.engine.begin() as con:
          query = text('ALTER TABLE `' + table_name +'` ADD PRIMARY KEY (`' + primary_key + '`);')
          result = con.execute(query)
          logger.info("Add Primary Key: " + str(primary_key) )
       return result
    def filter_df(self,df,string = 'u'):
         data = df[df.operation==string]
         return data

    def populate_table(self,table_name,indata,operation='u'):

       # Convert to DF
       df = pd.DataFrame(indata)

       # if the Table first row has values, exists.
       table_exists = self.check_table(df,table_name)
       if(not table_exists ):
          # read the excel file with schema definitions per table (tab)
          # schema_dict = pd.read_excel("schema_2023-10-06.xlsx").to_dict('records')
          # Record the DF data n the DB. With Primary Key
          cnt = self.create_table_primary_key(df,table_name,self.schema_dict)

       if(operation == 'u'):
           #upsert:
           self.logger.info( "df_up length: " + str( len(df.to_dict('records')) ) ) 
           # upsert data
           up_result = self.upsert_table(df,table_name,schema_dict)
           if(isinstance(up_result,int) ):
              cnt = up_result
           else:
              cnt = int(up_result.rowcount)

       if(operation =='d'): 
           # delete the rows market as operation=d from the table.
           operation = 'd'
           df_delete = df
           self.logger.info("File: " + table_name + " Number of Rows to Delete: " + str(len(df_delete)) )
           # if the DF_Delete has rows.. then remove them  

           # Set Primary key only once on the First Creation of the table   
           # Delete Data
           if(not df_delete.empty):
              # remove the Operation and Time Stamp miliseconds.
              # df_delete = df_delete.drop(['operation', 'ts_ms'], axis=1)
              prikey = self.get_primarykey(schema_dict[table_name])
              self.logger.info("Deleting Rows for table: " + table_name + " Primary Key: " + prikey )
              del_result = self.delete_rows_table(df_delete,table_name,prikey)
              self.logger.info("Delete Row Counts: " + str(del_result.rowcount) )
              cnt += del_result.rowcount 

       # return the total number of rows affected by update / delete
       return cnt


    def read_parquet_populate_table(self,filename,table_name,schema_dict):
       # Read the Table and Populate it.
       paraquet_data = pq.read_table(filename)

       # Convert to DF
       df = self.paraquet_to_df(paraquet_data)

       self.logger.info("DF of file: " + filename )
    #   for row in df.to_dict('records'):
    #       logger.info("Row: "  + str(row) )

       # Split DF into Upsert, Delete Lists.
       # order by ts_ms lowest to highes (oldest to newest)
       # order the DF using ts_ms  smallest to largest (oldest to newest)
       df = df.sort_values(by=['ts_ms'], ascending=True)

       operation = 'u'
       df_up = self.filter_df(df,operation)
       self.logger.info( "df_up length: " + str( len(df_up.to_dict('records')) ) ) 

    #   for row in df_up.to_dict('records'):
    #       logger.info("DF UP Row: "  + str(row) )


       # remove the Operation and Time Stamp miliseconds.
    #   df_up = df_up.drop(['operation', 'ts_ms'], axis=1)

       # delete the rows market as operation=d from the table.
       operation = 'd'
       df_delete = self.filter_df(df,operation)
       self.logger.info("File: " + filename + " Number of Rows to Delete: " + str(len(df_delete)) )
       # if the DF_Delete has rows.. then remove them  


       # if the Table first row has values, exists.
       table_exists = self.check_table(df,table_name)
       if(not table_exists ):
          # read the excel file with schema definitions per table (tab)
          # schema_dict = pd.read_excel("schema_2023-10-06.xlsx").to_dict('records')
          # Record the DF data n the DB. With Primary Key
          cnt = create_table_primary_key(df,table_name,schema_dict)
      
          # Set Primary key only once on the First Creation ofhte table

       # upsert data
       up_result = self.upsert_table(df_up,table_name,schema_dict)
       if(isinstance(up_result,int) ):
          cnt = up_result
       else:
          cnt = int(up_result.rowcount)

       # Delete Data
       if(not df_delete.empty):
          # remove the Operation and Time Stamp miliseconds.
          # df_delete = df_delete.drop(['operation', 'ts_ms'], axis=1)
          prikey = self.get_primarykey(schema_dict[table_name])
          self.logger.info("Deleting Rows for table: " + table_name + " Primary Key: " + prikey )
          del_result = self.delete_rows_table(df_delete,table_name,prikey)
          self.logger.info("Delete Row Counts: " + str(del_result.rowcount) )
          cnt += del_result.rowcount 
       # return the total number of rows affected by update / delete
       return cnt

    def get_primarykey(self,schema_dict):
        # loop through the schema file and return the column with 'PRIMARY KEY'
        for row in schema_dict:
            m = re.match('.*PRIMARY KEY.*',row['sqlalchemy'])
            if(m):
              prikey = row['fields']
              break
        return prikey

    def paraquet_to_df(self,data):
          df = data.to_pandas()
          return(df)

    def delete_rows_table(self,df,table_name,prikey):
        if( df.empty):
            self.logger.info("Tried to remove rows using empty DF Table:" + table_name)
            return

        # delete rows
        end = len(df)  
        rm = ''
        cnt = 1
        for idx,row in df.iterrows():
           rm = rm + str(row[prikey])
           if(cnt < end):
               rm = rm + ","
           cnt += 1

        with self.engine.begin() as conn:
            query = "DELETE FROM " + table_name + " WHERE " + prikey + " IN (" + rm + ");"
            self.logger.info("Delete Entries Query: " + query)
            result = conn.exec_driver_sql(query)
        return result


    def upsert_table(self,df,table_name,schema_dict):
        self.logger.info("upsert_table Table Name: " + table_name )
        with self.engine.begin() as conn:


            # step 1 - upload DataFrame to temporary table
            # create the Temp Table 
            temp_t_name = 'temp_table'
            query = text('SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = N\'' + temp_t_name + '\' ;')
            table_exists = conn.execute(query).fetchall()

        if(table_exists ):
            # drop the temp table if it exists.
            with self.engine.begin() as conn:
                self.logger.info("Drop Table: " + temp_t_name)
                conn.exec_driver_sql("DROP TABLE IF EXISTS " + temp_t_name)

        with self.engine.begin() as conn:
            # pass in temp table name and connection
            self.create_table_primary_key(df,table_name,schema_dict,temp_t_name,conn)


        # step 2 - merge temp_table into main_table

        match table_name:
            case 'report_lookup_config':
                # insert ONly no unique Primary Key
                self.logger.info("insert into table: " + table_name )
                #with engine.begin() as conn:
                # insert the data temp_t_name
                result = df.to_sql(name=table_name,
                    con=self.engine,
                    method='multi',
                    index=False,
                    if_exists='append',
                    chunksize=800
                 )

            case _:
              # Tables to be merged
              self.logger.info("Populate Temp Table from parquet file, Table Name: " + temp_t_name )
              #with engine.begin() as conn:
              # insert the data temp_t_name
              result = df.to_sql(name=temp_t_name,
                  con=self.engine,
                  method='multi',
                  index=False,
                  if_exists='append',
                  chunksize=800
                 )

              # Merge the data from the Temp Table to final table.
              query =  self.create_merge_sql(df,table_name,temp_t_name)
              self.logger.info("Merge Temp Table: " + temp_t_name + " Destination Table: " + table_name )
              with self.engine.begin() as conn:
                  result = conn.exec_driver_sql(query)

        with self.engine.begin() as conn:
            # cleanup and remove the temp_table
            conn.exec_driver_sql("DROP TABLE IF EXISTS " + temp_t_name)

        return result

    def update_set(self,df):
        end = len(df.columns) -2
        sql = "UPDATE SET " 

        # create string  col1 = temp.col1,col2 = temp.col2
        for index, col in enumerate(df.columns[1:]):
            sql = sql + col + "=temp." + col 
            if(index < end):
                sql = sql + ","
        return sql

    def insert(self,df):
        end = len(df.columns) -1

        sql = "INSERT (" 
        collist =""
        values=""
        # create string  col1 = temp.col1,col2 = temp.col2
        for index, col in enumerate(df.columns):
            collist = collist + col 
            values  = values  + " temp." + col 
            if(index < end):
                collist = collist + ","
                values  = values + ","
        sql = sql + collist + ") VALUES (" + values + ")"

        return sql
        
    def insert_sql(self,df,table_name):
         sql =  self.insert(df).replace('INSERT','INSERT INTO ' + table_name)
         return sql

    def create_merge_sql(self,df,table_name,temp_tbl="temp_table", prikey='id'):
            # merge:
            sql =       "MERGE " + table_name + " AS main\n"
            sql = sql + "USING (SELECT * FROM " + temp_tbl + ") AS temp\n"
            sql = sql + "ON (main."+prikey+ "= temp."+prikey+")\n"
            sql = sql + "WHEN MATCHED THEN\n"
            sql = sql + self.update_set(df) + "\n"
            sql = sql + "WHEN NOT MATCHED THEN \n"
            sql = sql + self.insert(df)
            sql = sql + ";"
            self.logger.debug("Create Merge SQL:\n" + sql)
            return sql


    def create_insert_table(self,df,table_name):
        # Input: Data Frame from Pandas
        # Table name of DB Table
        # DB Engine with COnnection etc.
       start_time = time.time()


       # Check for a table that has Data Type Not Storable.
       # Change the Column Data Type to Specified value I.e to string
       #table_col_change=[
       #                  {'project_module_hier':{'cols':['pathids','pathpids'],'type_spec':'str' }},
       #                  {'test_cycle_hier':{'cols':['pathids','pathpids'],'type_spec':'str' }}
       #                 ]
       #for t_list in table_col_change:
       #    for t in t_list:
       #       if( t == table_name ):
       #          set_data_type(df,t_list[t]['type_spec'],  t_list[t]['cols'] )
       rows_affected = df.to_sql(name=table_name,
                     con=self.engine,
                     method='multi',
                     index=False,
                     if_exists='append',
                     chunksize=500
                     )
       self.logger.info("--- %s seconds ---" % (time.time() - start_time) + 'Table: ' + table_name + ' Inserted: ' + str( rows_affected) + ' Rows')
    
       return  rows_affected

    def check_process_file(self,data={}, session='', table_name='file_record'):
        # Check if Filename is in the qTest_processed
        query='SELECT file_name FROM ' + table_name +  ' WHERE '
        sep =' AND '
        max_len = len(data)
        for count, k in enumerate(data, start=1):
           if (count >=  max_len ):
              sep = ""
           self.logger.debug("Collumn: " + str(k) )
           query = query + k + " = " + "\'"+data[k]+"\'" + " " + sep + " "
    #     result = engine.connect().execute(text(query))
        self.connection_session()
        result = session.execute(text(query))
        return result.fetchall()

    def get_latest_file_date(self, table_name='file_record',query=''):
        # Get Latest Processed File Date
        if( not query):
             query='SELECT max(download_date) FROM ' + table_name      
    
        result = self.engine.connect().execute(text(query))
        return list(result.fetchall() )

    def create_download_date_range(self, table_name='file_record'):
         # Get the Latest File Date Downloaded
         date_list = get_latest_file_date(table_name)
         today = datetime.today()
         for d in date_list:
             for s in d:
                last_date = datetime.strptime(str(s),'%Y-%m-%d')
                start_date = last_date + timedelta(days=1)
         if(start_date > today ):
             # Todays files have been downloaded.
             date_range =''
         else:
             # send the <start>:<today> range
            date_range = str(datetime.strftime(start_date,'%Y-%m-%d') ) + ":" + str(datetime.strftime(today,'%Y-%m-%d') )
         logger.info("Last Date: " + str(last_date) + " Start Download Date: " + str(start_date) )
     
         # Add 1 Day. 
         # "<start date> : <today>"
         return date_range

    def download_delta_files(self,script,api_token,bearer_token):
         # Read the max date of processed files add 1 day as start date, then pull in to today.
         download_date_range = create_download_date_range('file_record')
         if(not download_date_range):
             logger.info("Delta Files up to date. No new Files downloaded.")
             return
         self.logger.info("Date Range: " + str(download_date_range) )
         # download the Files
         cmd = 'python' + ' ' + script  + ' ' + download_date_range + ' ' + api_token + ' ' + bearer_token
         self.logger.info("Download Command: " + cmd)

         # result = os.system("REM Download Command " + cmd )
         result = run_subprocess(cmd)
     
         return result

    def run_subprocess(self,cmd):
         # run the shell command.
         result = run(cmd, capture_output=True, shell=True)
         # Output the resultign info
         output = result.stdout.splitlines()
         if(output):
            for line in output:
                logger.info(line)

         errors = result.stderr.splitlines()
         if(errors):
            output = result.stderr.splitlines()
            for line in output:
                logger.error(line)
         return result

    def archive_directory(self,source,destination):
          logger.info("Archiving: " + source + " to " + destination)
          try:
             result = shutil.move(source, destination,copy_function = shutil.copytree) 
           # For permission related errors
          except: 
             self.logger.info("Archive Operation not permitted. Source Deleted.")
             result=shutil.rmtree(source)
          return result

    def record_schema(self,filename,table_name):
        # Read the Table and Populate it.
        paraquet_data = pq.read_table(filename)

        # Convert to DF
        df = self.paraquet_to_df(paraquet_data)
        dtypes = df.dtypes
        columns = df.columns
        # [
        #    {fields,schema,sqlalchemy}
        #    (col1,type),
        #    (col2,type2),
        #    (ColN,typeN)
        # ]
        schema = []
        row ={}
        for index,c in enumerate(columns):
            row = {}
            row['fields'] = str(c) 
            row['schema'] = str(dtypes[index])
            if( c == 'id'): # or  (table_name == 'report_lookup_config' and c == 'clientid') ):
                d = 'primary key'
            else:
                d = dtypes[index]
            # map the paraquet data type to sequel server data type 
            row['sqlalchemy'] = self.ssqltype_map(d,c,table_name)
            row['table'] = table_name
            schema.append(row)
        self.logger.debug('Schema:' + str(schema) )
        return schema
  
    def ssqltype_map(self,datatype,name,table):
            data=''
            # integration_projects tables Conflicts in Column definitions 
            match datatype:
                case 'primary key':
                    data = 'INTEGER PRIMARY KEY'
                case 'int64':
                    data = 'BIGINT'
                case 'float64':
                        data  ='BIGINT'
                case 'int32':
                    data  ='SMALLINT'
                case 'object':
                    match name:
                        case 'date':
                            data = 'DATE'
                        case 'description' | 'note' | 'value' | 'releasedescription' | 'actualresult'\
                            | 'classid' | 'classidhashcode'\
                            | 'requirement'\
                            | 'customfieldvalues' \
                            | 'toscanodepath'\
                            | 'precondition' \
                            | 'expectedresult':
                            data  = 'NVARCHAR(max)'
                        case 'operation':
                            data  = 'NVARCHAR(1)'
                        case 'tzcountryid' | 'quartername':
                            data  = 'NVARCHAR(2)'
                        case 'dateabbr' | 'monthabbr' | 'dayabbr':
                            data  = 'NVARCHAR(3)' 
                        case 'yearquarternumber':
                            data  = 'NVARCHAR(6)'
                        case 'yearweeknumber' | 'yearmonthnumber' | 'yearquarterabbr':
                            data  = 'NVARCHAR(7)'
                        case 'yearmonthabbr':
                            data  = 'NVARCHAR(8)'
                        case 'dateshort' | 'dayname'| 'monthname':
                            data  = 'NVARCHAR(12)'
                        case 'datemedium':
                            data  = 'NVARCHAR(16)'
                        case 'datelong':
                            data  = 'NVARCHAR(24)'
                        case 'datelong':
                            data  = 'NVARCHAR(24)'
                        case 'authtype' | 'datelong' | 'datefull':
                            data  = 'NVARCHAR(32)'

                        case 'toscauniqueID':
                            match table:
                                case 'test_case_run':
                                    data = 'NVARCHAR(40)'
                                case 'test_cycles':
                                    data = 'BIGINT'
                                case _:
                                    data = 'DEFAULT OBJECT'
                        case 'toscarooteventid':
                            match table:
                                case 'test_case_run':
                                    data = 'NVARCHAR(40)'
                                case 'test_cycles':
                                    data = 'NVARCHAR(128)'
                                case _:
                                    data = 'DEFAULT OBJECT'
                        case 'toscaurl':
                            data = 'NVARCHAR(512)'
                        case 'salt':
                            data  = 'NVARCHAR(45)'
                        case 'externaluserid'  | 'externalissuetype':
                            data  = 'NVARCHAR(50)'

                        case 'externalissueid':
                            match table:
                                case 'integration_issue_requirement_maps':
                                    data = 'NVARCHAR(200)'
                                case 'defects' |  'test_case_result_defects':
                                    data = 'NVARCHAR(50)'
                                case _:
                                    data = 'DEFAULT OBJECT'
                        case 'defaultexectool':
                            data = 'NVARCHAR(60)'
                        case 'mappedldapid':
                            data = 'NVARCHAR(80)'
                        case 'password' | 'firstname' | 'lastname' | 'attribute' \
                            | 'modifieddate' | 'indexmodifieddate' \
                            | 'url' \
                            |'lookupvalue'\
                            | 'customfieldname' | 'lookupfieldname' | 'reportfieldname' |'indexmodifieddatebk':
                            data  = 'NVARCHAR(100)'
                        case 'name':
                            match table:
                                case 'project_modules' | 'project_module_hier' | 'test_cycle_hier'\
                                   | 'requirements' | 'test_cycles' | 'test_suites' | 'test_cases':
                                    data  = 'NVARCHAR(500)'
                                case 'configurations':
                                    data  = 'NVARCHAR(255)'
                                case 'test_beds':
                                    data  = 'NVARCHAR(210)'
                                case 'defect_tracking_project' | 'test_case_run' | 'test_Cases':
                                    data  = 'NVARCHAR(max)'
                                case _:
                                    data  = 'NVARCHAR(100)'
                        case 'toscaobjecttype':
                            data  = 'NVARCHAR(128)'

                        case 'type':
                            data = 'NVARCHAR(245)'
                        case 'authenticatorid' | 'uuid' | 'settings' | 'systemfield' | 'searchkey' | 'externalissueuniqueid' | 'externalissueresolution':
                            data = 'NVARCHAR(255)'
                        case 'path':
                            data = 'NVVARCHAR(400)'
                        case 'sha3password' | 'buildname' | 'externalissuestatus' | 'releasename' | 'calledtestcasename' \
                            :
                            data = 'NVARCHAR(500)'
                        case 'activationcode' | 'createddatebk' | 'summary' |'externalissueurl' | 'buildnumber' | 'buildurl' \
                            | 'veraapprovalroute' | 'veraid'| 'verarejectionreason' | 'tdspathid' | 'originsystem' | 'submittedby'\
                            | 'verasignatures' | 'verapendingtasks' | 'deletedtoscaobjecttype' \
                            | 'linkedrequirementids'\
                            | 'tdsstepid':
                            data = 'NVARCHAR(512)'
                        case 'externalissuesummary':                       
                            match table:
                                case 'defects' | 'test_case_result_defects':
                                    data = 'NVARCHAR(2000)'
                                case _:
                                    data = 'DEFAULT OBJECT'
                        case 'targetdatebk' | 'closeddatebk' | 'targetdatebk' | 'completedatebk' | 'modifieddate'\
                            | 'executionstartdatebk' \
                            | 'executionenddatebk' \
                            :
                            data = 'DATETIME'
                        case 'lastmodifieddatebk' | 'plannedstartdatebk' | 'plannedenddatebk' \
                            | 'startdatebk' |'enddatebk' | 'toscauniqueid'\
                            :      
                            match table:
                                case 'test_case_run' | 'test_cycles':
                                   data = 'NVARCHAR(512)'
                                case _:
                                   data = 'DATETIME'

                        case 'ts_ms' | 'datebk' | 'activateddatebk' \
                                | 'passwordmodifieddatebk' \
                                | 'passwordexpirationdatebk' \
                                | 'lastlogintimebk'\
                                | 'isrootuser' \
                                | 'enddatebk'\
                                | 'passwordneedschangingdatebk'\
                                | 'tdsflowid' \
                                | 'indexmodifieddate' \
                                :
                                data = 'BIGINT'
                        case 'externalprojectid':
                            match table:
                                case 'integration_projects' |'test_case_result_defects' :
                                    data = 'NVARCHAR(2000)'
                                case 'defects':
                                    data = 'NVARCHAR(500)'                 
                                case _:
                                    data = 'DEFAULT OBJECT'
                        case 'internally' | 'indexingstatus' \
                            | 'autopopulatecloseddate' \
                            | 'enforcerequiredtestexecutionfields'\
                            | 'automation' \
                            | 'isinsightssu'\
                            :
                            data = 'BIT'
                        case 'toscauniqueid':
                            match table:
                                case 'test_case_run':
                                    data = 'NVARCHAR(40)'
                                case 'test_cycles':
                                    data = 'BIGINT'
                                case _:
                                    data = 'DEFAULT OBJECT'
                    
                        case 'pathids' | 'pathpids' | 'pathnames':
                             # requested as arrays but strings will have to do. Not sure how to support this in ssql
                            data = 'NVARCHAR(2000)'
                        case  'edited' | 'locked' | 'isapprovedbefore' | 'istemplatetosca' | 'stepdescriptionflag' | 'expectedresultsflag' | 'addnew':
                            data = 'BIT'
                        case _:
                            data = 'DEFAULT OBJECT'
                case 'bool':
                    data  = 'BIT'
                case 'boolean':
                    data  = 'BIT'
                case _:
                    data = 'DEFAULT'
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
    def add_date(self,fname,prefix=''):
        fname = os.path.splitext(fname)
        d = date.today().strftime('%Y-%m-%d')
        if(prefix):
            # add unique name and extension
            outf = prefix + "_" + fname[0] + "_" + d + fname[1]
        else:
            outf = fname[0] + "_" + d + fname[1]
        return outf        
    def init_schema(self,):
        data ={}
        data['file_record']=[
             {'fields': 'id','schema':None,'sqlalchemy':'INT IDENTITY(1,1) PRIMARY KEY','table':'file_record'},
             {'fields': 'download_date','schema':None,'sqlalchemy':'DATE','table':'file_record'},
             {'fields': 'table_dir','schema':None,'sqlalchemy':'NVARCHAR(512)','table':'file_record'},
             {'fields': 'file_name','schema':None,'sqlalchemy':'NVARCHAR(512)','table':'file_record'},
             {'fields': 'datetime','schema':None,'sqlalchemy':'DATETIME','table':'file_record'},
             {'fields': 'added_rows','schema':None,'sqlalchemy':'BIGINT','table':'file_record'}
        ]
        return data

    def test_upsert(self,download_date,table_dir,file_name):
        # Read the paraquet file and upsert the data as needed.
        # skip the File if already in table as being processed.
        file_record={'download_date':download_date,'table_dir': table_dir,'file_name':file_name}
        # file_record['datetime']=datetime.now()
        # df = pd.DataFrame([file_record])
        # create_insert_table(df,'file_record',engine)
    #    with Session.begin() as session:
     #       check_file = check_process_file(file_record, session,'file_record')
     #   if(check_file):
     #       logger.info(str(check_file) + ' already processed, continue with next file' )
     #       continue
      #  else:
      #      logger.info('Processing ' + str(file_record) )
        try:
            pathFilename = file_name
            row_cnt = self.read_parquet_populate_table(pathFilename,table_dir,schema_dict)
            self.logger.info("Table: " + table_dir + "\tAdded Rows: " + str(row_cnt) + " " + str("pathFilename:" + pathFilename))
            processed_file={'table':table_dir,'added_rows':row_cnt,'filename':pathFilename}
            file_record['added_rows'] = row_cnt
            file_record['datetime']= datetime.now()
            df = pd.DataFrame([file_record])
            self.logger.info("File Record: " + str(file_record) )

            # Record the Number of records changed for this file
            # create_insert_table(df,'file_record',engine)

        except Exception as e:
            self.logger.error('Error Failed to process:' + str(pathFilename) + ' Exception ' + str(e))
            raise


   
if __name__ == "__main__":
    # Instance the SQL Server Class
    sqls = SqlServ("Test_Log_Name")

    # Set the Logger.
    logger = sqls.logger
    logger.info('Hello World from SqlServer')


