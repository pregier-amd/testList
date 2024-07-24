from ast import Return
from LogClass import LogClass
from util import util
import re
import os
from datetime import datetime

class ListFilter(object):
    pass

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
        pass

    def filt(self,indata=None,terms=None):

        fdata = indata
        # Find all the Or, AND terms
        orTerms = self.group_filt(terms,{'group':'or'})            
        andTerms = self.group_filt(terms,{'group':'and'})

        # process each Group fdata = filtered data.
        if orTerms:
            fdata = self.process_terms(indata,orTerms,andFlag=False)
        if andTerms:
            fdata = self.process_terms(fdata,andTerms,andFlag=True)

        return fdata
       
    def group_filt(self,indata=None,term=None):
        # return list that matches the 
        for k in term:
                data = list( filter( lambda row: row[k] == term[k] ,indata) )
        return data
        

    def process_terms(self,indata,terms,andFlag=False):
        outdata = []
        data = indata

        # Filer the Indata based on anding terms
        # If or Flag evaluate the entire Input Dat afor Each Term
        #  Else
        #     Evaluate the Filtered List for each term
        for term in terms:
            # filter the data based on term condistions
            fd = list( filter( lambda row: self.check(row,term) ,data) )
            if andFlag:
                # AND reuse the output data for hte next term
                # reload the original input list of data for "or" terms.
                # for "and" use the previously filtered list for the subsequent terms.
                data = fd
            else:
                # or term use the original list.
                data = indata
                # Save the Results of the term
                #incrementally save the or Term data.
                outdata.extend(fd)
        # Save the Multiple Term And terms
        if andFlag:
                outdata.extend(fd)

        return outdata

    def check(self,row=None,term=None):
        result = True
        if term['col'] in row:
            match term['op'].lower():
                case '=':
                    a= row[term['col']]
                    b= term['value']
                    if a != b:
                        result = False
                case '<>':
                    # Not equal
                    if row[term['col']] == term['value']:
                        result = False
                case 'contains':
                    # contains the string in a comma delimited row
                    for element in row[term['col']].split(','):
                        self.logger.debug("Contains check: row[" + str(element.strip()) + "] vs Term[" + term['value'] +"]"  )
                        pat = '.*(' + str(term['value'].lower()) + ').*'
                        m = re.match(pat,element.lower())
                        # Contains is an or function If any element matches mark as true nad exit
                        if not m:
                            self.logger.debug("False: Contains check: row[" + str(element) + "] vs Term[" + term['value'] +"]"  )
                            result = False
                        else:
                            self.logger.debug("True: Contains check: row[" + str(element) + "] vs Term[" + term['value'] +"]"  )
                            result = True
                            # Exit the Split. Found a match
                            break
                case '<':
                    # Row > Term[value]
                    a = row[term['col']]
                    b = term['value']
                    # if a date object
                    m = re.match('.*?(date).*?',term['col'].lower())
                    if m:
                        a = self.convert_date(row[term['col']])
                        b = self.convert_date(term['value'])
                    # Compares first input Not Less than Second input
                    result = self.compare_values(a,b,term['op'].lower(),result)
                    self.logger.info( 'id: ' + str(row['tr_id']) + ' Row[' + term['col'] + ']' + str(a) + ' ' + term['op'].lower() + ' ' + str(b)  + ' Result:' + str(result) )        

                case '>':
                    # Row > Term[value]
                    a = row[term['col']]
                    b = term['value']
                    # if a date object

                    #if term['col'] == 'tr_Planned_Start_Date' or term['col'] == 'tr_Planned_End_Date':
                    m = re.match('.*?(date).*?',term['col'].lower())
                    if m: 
                        a = self.convert_date(row[term['col']])
                        b = self.convert_date(term['value'])

                    # Compares first input Not Greater than Second input
                    result = self.compare_values(a,b,term['op'].lower(),result)
                    self.logger.info( 'id: ' + str(row['tr_id']) + ' Row[' + term['col'] + ']' + str(a) + ' ' + term['op'].lower() + ' ' + str(b)  + ' Result:' + str(result) )        

                case '_':
                    self.logger.error("Unsuported operation type: " + str(term['op']) )
                    return
        return result

    def compare_values(self, a=None,b=None, op='>',result=None):
        match op:
            case '<':
                if not a < b:
                    result = False
            case '>':
                if not a > b:
                    result = False
            case '_':
                result  = False
                self.info("Unsupported op:" + str(op) )

        return result

    def term(self,col='None',op=None,value=None,group='and'):
        term = {"col": col,"op": op, "value": value,"group": group}
        return term

    def convert_date(self,data=None,data_frmt='%Y-%m-%dT%H:%M:%S+00:00'):
        if not data:
            return 0
        # if the data input matches the data format: 2024-06-18T15:38:19+00:00
        date = datetime.strptime(data,data_frmt )
        return date

if __name__ == "__main__":
     import logging
     lf = ListFilter(None,"config.ini")
     logger = lf.logger
     logger.setLevel(logging.INFO)

     filename = "/Users/pregier/Documents/qTest/python/qTestAPI/output/outfile_2024_07_03T15_25_32.xlsx"
     data=lf.util.read_excel_each_sheet(filename)

     terms = []
     # Build Filter Terms col='None',value=None,op=None,group='and'
#     terms.append( lf.term('tc_Release_SKU','contains','XTW', 'or') )
#     terms.append( lf.term('tc_Release_SKU','contains','General', 'or') )
     terms.append( lf.term(col='tc_Release_Suite',op='contains',value='BP', group='and') )
#     terms.append( lf.term(col='tc_Release_Flow',op='contains',value='tng', group='and') )
     terms.append( lf.term(col='tr_Planned_End_Date',op='<',value='2024-06-18T15:38:19+00:00', group='and') )

     filtered = lf.filt(data['Sheet1'],terms)
     for row in filtered:
          log = ''
          for col in ['tr_id','tc_Ip','tc_Release_Suite','tc_Release_SKU','tc_Release_Flow','tc_OL_Milestones']:
            log = log + str('Row['+col+']:\t' + str(row[col]) ) + "\n"
          logger.info("Row:\n" + log)
     pass

