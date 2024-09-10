import pandas as pd
from util import util
import os,sys
from LogClass import LogClass
#import random

class release_format(object):
    def __init__(self,filename=None ): 
        # Logger
        log = LogClass(None ,os.path.splitext(__file__)[0] + ".log",False)
        self.logger = log.logger
        self.logger.setLevel('INFO')
 
        self.util =  util(self.logger,'config.ini')
        self.map_file = "map_suite_sku_flow.yaml"
        # Read Map format Yaml data
        # Column:{'suite':['SLT'],'flow':['full'],'sku':['default']}
        self.map_data = self.util.read_file(self.map_file)
                # Append to the Suite,Sku,Flow Settings
        #map_data = {'SLT Coverage':{'suite':['SLT']},
        #               'Coverage: SLT default (general, full)':{'suite':['SLT'],'flow':['full'],'sku':['default']},
        #              'Coverage: SLTQ default (sltq, full)':{'suite':['SLTQ'],'flow':['full'],'sku':['default']},
        #              'BP Coverage':{'suite':['BP'],'sku':['default']},
        #              'Coverage: BP default (quickmfg)': {'suite':['BP'],'flow':['quickmfg'],'sku':['default']},
        #              'Coverage: BP default (extmfg)':{'suite':['BP'],'flow':['extmfg'],'sku':['default']},
        #              'Coverage: BP default (qualmfg)':{'suite':['BP'],'flow':['qualmfg'],'sku':['default']}             }
        self.remap_modules = False
        self.module_map = {
                      'GFX':'MD-132',
                      'MALL':'MD-135',
                      'PSP':'MD-133',
                      'UMC_GPU':'MD-134',
                      'MALL':'MD-135',
                      'USR_CP':'MD-136',
                      'USR_DP':'MD-137',
                      'CHPLT':'MD-138',
                      'MHUBs':'MD-139',
                      'nBIF_PCIe':'MD-140',
                      'OSS':'MD-141',
                      'VCN':'MD-142',
                      'XGMI_WAFL':'MD-143',
                      'DF':'MD-144',
                      'MULTI_IP':'MD-145',
                      'RAS':'MD-146',
                      'SRIOV':'MD-147',
                      'PMM':'MD-148',
            }
        self.one_language_map = { 
            'Bringup Ready': '03 SLT Bringup Ready',
            'Initial Charz Complete':'05 SLT Initial Charz Complete',
            'Performance Stability Binning':'06 SLT Performance Stability Binning',
            'Power Management Features Enabled':'07 SLT Power Management Features Enabled',
            'Platsi Boot Complete':'04 SLT Platsi Boot Complete',
            'All Content Binning':'08 SLT All Content Binning'

            }
        # Add Fields needed for Importing and Creating Test Cases. With Defaults
        self.required_fields = {'Status':'New','Type':'Manual','Total Variations':1}





    def poplate_suite(self,data=None):
        return data

    def poplate_skew(self,data=None):
        return data

    def poplate_flow(self,data=None):
        return data


    def main(self,filename=None):

        self.logger.info("Reading File: " + str(filename))
        outdata={}
        data = self.util.read_excel_each_sheet(filename,skip=[0])
        skip_none = 'Test Case ID'

        self.logger.info("Map Data:" + str(self.map_data) )
        
        # Default Values for Required Fields
        cnt = 1
        for row in data['Test List']:
            blk = ''
            if 'IP_BLK' in row:
                blk = row['IP_BLK']
            self.logger.warning(' IP Blk:' + str(blk) + "\tRow:" + str(cnt) )
            cnt += 1

            new_row={}
            # Skip zero Test Cases:
            testcase_name = row[skip_none]
            if not str(testcase_name).strip(): 
                continue

            # Put in Test Case Required Fields With Default Values
            for r  in self.required_fields:
                if not r in row:
                    row[r] = self.required_fields[r]

            # Change Names of Data in OL Default
            ol_col = 'Default OL Milestone'
            row[ol_col] = self.remap(row[ol_col],self.one_language_map,'03 SLT Bringup Ready')
            
            mapped = self.unpack_suite_flow_sku(row,self.map_data) 
            if mapped:
                new_row = {**new_row, **mapped}
            self.logger.info(new_row)

#            number = random.randint(1000,9999)
#            + '_' + str(number)
            row['test case name'] = row['Test Case ID'] 


            # Add Test Step
            step = self.add_test_step(row['Test Case ID'],row['Planned IP Specific Test Parameters / Command line'],1)
            new_row = {**new_row,**step}


            # Add the Module number to the IP Block.
            # ip_block = MALL  ->  'MD-8XX MALL'
            sheetKey = 'IP_BLK'
#            sheetkey = 'Default OL Milestone'

            if self.remap_modules:
                sheet = self.module_map[row[sheetKey]] + ' ' + str(row[sheetKey])
            else:
                sheet = str(row[sheetKey])


            if not sheet in outdata:
                outdata[sheet] = []
            outdata[sheet].append({**new_row,**row})
        

        date = self.util.time_gen(None,format_string='%Y_%m_%dT%H_%M_%S')
        fname ="log/" +  os.path.splitext(os.path.basename(__file__))[0] + "_" + str(date) + ".xlsx"
        self.util.write_excel_each_sheet(fname,outdata)

        return outdata

    def remap(self,key=None,map=None,default=None):
        # Remap the key to another value
        # map = {'Key': 'qtest value'}
        data = key
        if key in map:
            data = map[key]

        else:
            self.logger.warning(" Used Default value for \"Default OL Milestone\" Value:" + str(default) )
            data = default
        return data

    def add_test_step(self,testid=None,parameters=None,number=None):
        # 'Test Step #','Test Step Decription','Test Step Expected Result'
        desc=str(testid)
        desc = desc + ' ' + str(parameters)

        
        data ={'Test Step #': number,'Test Step Decription': str(desc).strip()}
        return data


    def unpack_suite_flow_sku(self,row=None,map=None):
        data = {}
        for col in map:
            col = col.replace('\\', '')
            if col in row:
                
                # If there is a 1 in the Column
                for field in map[col]:
                    # Initialize list in each field
                    if not field in data:
                        data[field] = [] 

                    # Found Data in Column
                    if row[col] == 1:
                        # Populate Fields
     
                        for value in map[col][field]:
                        # Don't Duplicate the values in the Field
                            if not value in data[field]:
                                 data[field].append(value)
        # Convert list to Comma seperated String.
        for field in data:
            data[field] = self.gen_comma_string(data[field])
        return data
    def gen_comma_string(self,data):
        if isinstance(data,list):
            str_list = ''
            #Loop through the list
            for entry in data:
                # Add Comma after last entry .
                if str_list:
                    str_list = str(str_list) + ','
                    str_list = str(str_list) + str(entry)
                else:
                    str_list = str(entry)
 
            self.logger.debug("Str List: " + str(str_list))
            return str_list

if __name__ == '__main__':            
    rf = release_format("release")   
    rf.main('ReleaseTrackerMi350.xlsx')