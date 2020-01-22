#!/Library/Frameworks/Python.framework/Versions/3.7/bin/python3

from flask import Flask, render_template, request,  flash, redirect, url_for, session, send_file, jsonify
from flask_mysqldb import MySQL
from flask_migrate import Migrate
from flask_login import UserMixin, login_user, logout_user, current_user, login_required, LoginManager
from wtforms import Form, BooleanField, TextField, PasswordField, validators
import hashlib
from MySQLdb import escape_string as thwart
import gc, json, time
import os, glob, binascii
from flask_mail import Message, Mail
from forms import LoginForm, RegistrationForm, EntryForm, EnterDataForm, DatabaseForm
from config import Config
app = Flask(__name__)

'''
    Website script written by H. Denise (Cambridge Uni) 27/11/2019
    Script for the Darwin/VGP database
'''
#initialisation of connection
config_file_path=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+'/config/Darwin_dbV1.json'
configSettings = json.load(open(config_file_path, 'r'))
app.config.from_object(Config)
app.config['MYSQL_HOST'] = configSettings["MySQL_host"]
app.config['MYSQL_USER'] = configSettings["MySQL_usr"]
app.config['MYSQL_PASSWORD'] = configSettings["MySQL_pswd"]
app.config['MYSQL_DB'] = configSettings["MySQL_db"]
mail_settings = {
    "MAIL_SERVER": configSettings["Mail_server"],
    "MAIL_PORT": configSettings["Mail_port"],
    "MAIL_USE_TLS": configSettings["Mail_TLS"],
    "MAIL_USE_SSL": configSettings["Mail_SSL"],
    "MAIL_USERNAME": configSettings["Mail_usrn"],
    "MAIL_PASSWORD": configSettings["Mail_pswd"]
}
mysql = MySQL(app)
login = LoginManager(app)
app.config.update(mail_settings)
mail = Mail(app)
login.login_view = 'login'
mail.init_app(app)
session={}
session['logged_in']=0
db='darwin'
today=time.strftime("%Y-%m-%d")
################### DATA PROCESSING FUNCTIONS ##################################
def add_individual_data_info(col, data):
    """adding individual_data information if available to 'individual' display"""
    '''
    input col: field headers for individual (now including project and sample fields) (tuple)
    input data: data for the individual (see add_sample_info) (tuple)
    return new_col: field headers with individual_data fields added (tuple)
    return new_data: data for the individual with individual_data info added, if present, in the database (tuple)
    '''
    new_col=col
    new_data=data
    curs=mysql.connection.cursor()
    if len(data) > 0:
        try:
            curs.execute("SELECT distinct * from individual_data where latest=1 and individual_id = '{indi}';". format(indi=data[0]))
            id_results=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch individual_data information")
        if len(id_results) > 0:
            #to cope with case when there is more than one individual_data associated with the individual
            for id_result in id_results:
                new_col+=tuple(["cv_id","value","unit", "comment"])
                new_data+=tuple(list(id_result[2:6]))
    curs.close()
    return new_col, new_data

def add_project_info(col, data):
    """adding project information, if available, to 'individual' vertical display"""
    '''
    input col: field headers for individual including project field (tuple)
    input data: data for the individual (see get_individual_per_individual_id) (list of tuple, [(131, 131, '86', 'TaeMac1',..., 'ERP002088', '2430')])
    return new_col: field headers with project fields added (tuple)
    return new_data: data for the individual with project info relocated (tuple)
    '''
    results=[]
    all_results=[]
    new_col=col
    #go through the data
    for index in range(0, len(data)):
        if index == 0:
            #add project_info and update column accordingly
            new_data=tuple(data[index][1:7])+tuple(data[index][16:20])
            new_col+=tuple(["project_name","project_alias","project_accession", "project_ssid"])
        else:
            #this means that there are more than one project associated with the individual_id, add field/data accordingly
            if len(data[index]) > 0:
                new_col+=tuple(["project_name","project_alias","project_accession", "project_ssid"])
                new_data+=data[index][16:20]
    return new_col, tuple(new_data,)

def add_sample_info(col, data):
    """adding sample information if available to 'individual' display"""
    '''
    input col: field headers for individual (now including project fields) (tuple)
    input data: data for the individual (see add_project_info) (tuple)
    return new_col: field headers with sample fields added (tuple)
    return new_data: data for the individual with sample info added, if present, in the database (tuple)
    '''
    new_col=()
    s_results=()
    new_col=col
    new_data=data
    curs=mysql.connection.cursor()
    if len(data) > 0:
        try:
            curs.execute("SELECT distinct s.* from sample s left join material m on m.material_id=s.material_id where s.latest=1 and m.individual_id = '{indi}';". format(indi=data[0]))
            s_results=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch sample information")
        if len(s_results) > 0:
            #to cope with case when there is more than one sample associated with the individual
            for s_result in s_results:
                new_col+=tuple(["sample_name","sample_accession","sample_ssid"])
                new_data+=tuple([s_result[5], s_result[3], s_result[4]])
    curs.close()
    return new_col, new_data

def change_for_display(col, data, ext_flag):
    """ 1) change the table_ids in column names by the corresponding names/attributes for display
        2) change the table_id values in data by the corresponding name values for display
        3) deal when multicolumns of a table have to be displayed and call function to display all individual_data
        4) add thumbnail for display,
        5) call function to re-order when multiple entries are available"""
    '''
    input col: header for the data (list of tuple)
    input data: data for the entries (list of tuple)
    return tuple(list_new_columns): header for the data reformatted for display as a list
    return tuple(list_new_data): data reformatted for display as a list
    '''
    table_name_dic={}
    list_old_data=[]
    list_new_data=[]
    list_new_columns=[]
    #dictionary with 'table' name as key and name/attribute(s) values
    table_dic={'assembly':'name', 'cv':'attribute, comment', 'developmental_stage':'name', 'family':'name', 'file':'name',
    'image':'filename', 'individual':'name', 'lane':'name', 'library':'ssid', 'library_type':'name',
    'location':'country_of_origin, location, sub_location, latitude, longitude', 'material':'name', 'ontology':'name', 'organism_part':'name',
    'pipeline':'name', 'project':'name', 'provider':'provider_name', 'sample':'name', 'seq_centre':'name',
     'seq_tech':'name', 'species':'name, common_name', 'tax_order':'name'}
    #ensure that the length of col equate length of data (length col is one when whole table is queried, equal at data when more than one entry is returned by the original function)
    if len(col) ==1:
        col=col*len(data)
    #process each entry in columns
    for index in range(0, len(col)):
        table_name_dic={}
        column=list(col[index])
        #function to relabel the column names
        for field_index in range(1, len(column)):
            primary_table=""
            if column[field_index].endswith("_id"):
                table=column[field_index][:-3]
                #the mother and father table_id are in fact individual_id so rename accordingly
                if table=='mother' or table=='father':
                    primary_table=table
                    table='individual'
                #special case for taxon_id as not linked to table so not to be 'translated'
                if table != 'taxon':
                    table_name_dic[field_index]=table
                    if primary_table in ('mother', 'father'):
                        column[field_index]=primary_table+"_name"
                    else:
                        #special case for cv: no name but attribute
                        if table == "cv":
                            column[field_index]= table+"_attribute"
                        else:
                            #special case for location as no name and 3 fields
                            if table == 'location':
                                column[field_index]= 'location'
                            elif table=='individual':
                                column[field_index]= 'supplier_name'
                            else:
                                column[field_index]= table+"_name"
        #special case for species: 2 fields will be returned so need to be inserted
        if 'species_name' in column:
            column.insert(column.index('species_name')+1, 'common_name')
        #special case for location: 5 fields will be returned so need to be inserted
        if 'location' in column and column[0]=='individual_id':
            column.insert(column.index('location'), 'country_of_origin')
            column.insert(column.index('location')+1, 'sub_location')
            column.insert(column.index('location')+2, 'latitude')
            column.insert(column.index('location')+3, 'longitude')
        #special case for cv table as two fields will be returned so need to be inserted
        #find position of all 'cv_attribute' in column:
        cv_attrib_list=[i for i, x in enumerate(column) if x == "cv_attribute"]
        #insert cv_comment field at all positions using the extracted index
        cv_attrib_list.reverse()
        for insert_index in cv_attrib_list:
            column.insert(insert_index+1, 'cv_comment')
        #function to replace the 'table_id' values by the name or attribute values (<table>_name or <table>_attribute)
        row = list(data[index])
        #go through the dictionary with field index as keys and table as values
        for dic_index in table_name_dic:
            if row[dic_index] != None:
                curs = mysql.connection.cursor()
                try:
                    if table_name_dic[dic_index] in ('project', 'location', 'organism_part', 'developmental_stage', 'seq_tech', 'seq_centre', 'cv'):
                        curs.execute("SELECT "+table_dic[table_name_dic[dic_index]]+ " FROM "+table_name_dic[dic_index]+" WHERE "+table_name_dic[dic_index]+"_id = '{id}';". format(id=row[dic_index]))
                    else:
                        curs.execute("SELECT "+table_dic[table_name_dic[dic_index]]+ " FROM "+table_name_dic[dic_index]+" WHERE latest=1 and "+table_name_dic[dic_index]+"_id = '{id}';". format(id=row[dic_index]))
                    results=curs.fetchall()
                    #location and cv queries returned several fields, the other tables will return a single field
                    if len(results)>0:
                        if table_name_dic[dic_index] in ('location', 'cv', 'species'):
                            row[dic_index]=results[0]
                        else:
                            row[dic_index]=results[0][0]
                except:
                    if ext_flag=='json':
                        return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
                    else:
                        flash ("Error: unable to fetch items: "+"SELECT "+table_dic[table_name_dic[dic_index]]+ " FROM "+table_name_dic[dic_index]+" WHERE "+table_name_dic[dic_index]+"_id = '{id}';". format(id=row[dic_index]))
                curs.close()
        #section to add data in correct field when several fields are returned

        #if species field (species_name) in column:
        if 'species_name' in column:
            if row[column.index('species_name')] is None:
                for idx in range(1,2):
                    row.insert(column.index('species_name')+idx, '')
            else:
                for idx in range(1,2):
                    row.insert(column.index('species_name')+idx, str(row[column.index('species_name')][idx]))
                row[column.index('species_name')]= str(row[column.index('species_name')][0])
        #if location field (country of origin) in column:
        if 'country_of_origin' in column:
            if row[column.index('country_of_origin')] is None:
                for idx in range(1,5):
                    row.insert(column.index('country_of_origin')+idx, '')
            else:
                for idx in range(1,5):
                    row.insert(column.index('country_of_origin')+idx, str(row[column.index('country_of_origin')][idx]))
                row[column.index('country_of_origin')]= str(row[column.index('country_of_origin')][0])
        if 'cv_attribute' in column:
            if row[column.index('cv_attribute')] is None:
                row.insert(column.index('cv_attribute')+1, '')
                row[column.index('cv_attribute')]=''
            else:
                row.insert(column.index('cv_attribute')+1, str(row[column.index('cv_attribute')][1]))
                row[column.index('cv_attribute')]=str(row[column.index('cv_attribute')][0])
        #reformat number of reads and length data
        if 'nber_reads' in column and row[column.index('nber_reads')] is not None:
            row[column.index('nber_reads')]= str(format(row[column.index('nber_reads')],"*>3,d"))
        if 'total_length' in column and row[column.index('total_length')] is not None:
            row[column.index('total_length')]= str(format(row[column.index('total_length')],"*>3,d"))
        #replace the None label with blank for display
        row=['' if x is None else x for x in row]
        #get the image details
        if column[0]=='individual_id':
            column[1]="supplier_name"
            curs = mysql.connection.cursor()
            curs.execute("SELECT filepath, filename FROM image WHERE individual_id= '{id}';". format(id=row[0]))
            image_results=curs.fetchall()
            curs.close()
            if 'thumbnail' not in column:
                column.append('thumbnail')
            if image_results and 'samples' not in column:
                for image_index in range(0, len(image_results)):
                    #create path to image file
                    row.append("/".join(list(image_results[image_index])))
                    #required to match column and data length
                    if image_index > 0:
                        column.append('thumbnail')
            else:
                row.append('')
        #get the updated columns and data in a list
        list_new_data.append(row)
        list_new_columns.append(column)
        #if there is more than one entry for an individual, order by latest and reverse date
        if column[0]=='individual_id' and len(column) > 13:
            list_new_data = reorder_for_vertical_display(list_new_data)
    return tuple(list_new_columns), tuple(list_new_data)

def ensure_thumbnails_display(results):
    '''add empty data field to match the column length'''
    '''
    input results: dictionary of reformatted data to display with table as key and column and table data  as value (dic) (see generate_json_for_display)
    return results: same dictionary with length of individual data identical to length of individual column
    '''
    col_length=len(results['individual']['column'])
    for entry_index in range(0, len(results['individual']['data'])):
        if len(results['individual']['data'][entry_index]) < col_length:
            results['individual']['data'][entry_index]=results['individual']['data'][entry_index]+(col_length-len(results['individual']['data'][entry_index]))*[""]
    return results

def generate_json_for_display(res_dic, col_dic, ext_flag, identifier):
    '''reformat data as json for the web display and also to download as json '''
    '''
    input res_dic: dictionary of data to reformat with identifier as key and table data as value (dic)
    input col_dic: dictionary of column to reformat with table as key and table data as value (dic))
    input ext_flag: suffix for the data (web for web display, json to download) (str)
    input identifier: name of the primary identifier to use for the records in the download (str)
    return web_results: dictionary of reformatted data to display with table as key and column and table data  as value (dic)
    return json_results: dictionary of reformatted data to download with identifier & identifier_id as key and list of column and table data as value (dic)
    '''
    json_results={}
    web_results={}
    table_name=['project', 'individual', 'material', 'sample', 'file']
    #go through the identifier dictionaries
    for id in res_dic:
        json_results[identifier+":"+str(id)]={}
        complete_results=[]
        table_dic=res_dic[id]
        col=[]
        res=[]
        #gp through the tables
        for table in table_name:
            complete_results=[]
            if len(table_dic[table]) == 0:
                col.append([table, table])
                res.append([[table] + ['no data available for this table']])
            else:
                if table in ('project'):
                    new_columns, display_results= change_for_display([col_dic[table]],table_dic[table], ext_flag)
                else:
                    new_columns, display_results= change_for_display([col_dic[table][1:]], remove_column(table_dic[table],1), ext_flag)
                complete_columns=[table]+list(new_columns[0])
                for entry in display_results:
                    complete_results.append([table] +entry)
                col.append(complete_columns)
                res.append(complete_results)
            #if there is already data for the given table
            if table in web_results:
                previous_data=web_results[table]['data']
                new_data=res[table_name.index(table)]
                if previous_data != new_data:
                    #deal with cases where there is no data available in the database
                    if 'no data available for this table' in previous_data[0]:
                        web_results[table]['data']=new_data
                        web_results[table]['column']=col[table_name.index(table)]
                    elif not 'no data available for this table' in new_data[0]:
                        web_results[table]['data']=previous_data+new_data
                        #ensure appropriate display when more than 1 thumbnail is present
                        old_col_length=len(web_results[table]['column'])
                        new_col_length=len(col[table_name.index(table)])
                        if new_col_length > old_col_length:
                            web_results[table]['column']=col[table_name.index(table)]
            else:
                web_results[table]={'column':col[table_name.index(table)], 'data':res[table_name.index(table)]}
            json_results[identifier+":"+str(id)][table]={'column':tuple(col[table_name.index(table)]), 'data':tuple(res[table_name.index(table)])}
    complete_web_results=ensure_thumbnails_display(web_results)
    return json_results, complete_web_results

def get_columns_from_table(table_name):
    """extract the name of fields for a given table extracted from the information schema of the database"""
    '''
    input table_name: name of table queried (str)
    return tuple(col): column headers for the table (tuple)
    '''
    col=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS where table_schema=  '"+configSettings['MySQL_db'] +"' and table_name='%s' ORDER BY ORDINAL_POSITION;" %table_name)
        columns=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch column names")
    curs.close()
    #transforming the returned tuples [(('location_id',), ('country_of_origin',),...)] into a list that can be then changed into one tuple
    for col_name in columns:
        col.append(col_name[0])
    return tuple(col)

def remove_column(original_tuple, column_idx):
    """remove column from all elements from tuple according to index input"""
    '''
    input original_tuple: tuple where column should be removed (tuple of tuple)
    input column_idx: index or letter corresponding to column to remove (int or str)
    return new_list: data reformatted without the provided column (tuple)
    '''
    if column_idx == '1':
        new_list=[x[1:] for x in list(original_tuple)]
    #use 'L' as length of elements is not always known (Last), otherwise could provide this value to remove the last column
    elif column_idx == "L" :
        new_list=[x[:-1] for x in list(original_tuple)]
    else:
        new_list=[x[:column_idx -1]+x[column_idx:] for x in list(original_tuple)]
    return tuple(new_list)

def reorder_for_vertical_display(data):
    """re-order the entries according to their uniqueness, latest field and changed date"""
    '''
    input data: data for each individual to be displayed (list of list, [[131, '86', 'TaeMac1', ... , datetime.date(2019, 3, 11), 1, ''], [249, '131', 'OtoLit1',..., datetime.date(2019, 3, 11), 1, '']])
    return new_data: reordered data for each individual (list of list, similar structure than 'data')
    '''
    id_dic={}
    new_dic=[]
    index=-1
    new_data=[]
    #create dictionary with individual_id as key and index(es) in data as value
    for entry in data:
        index+=1
        if entry[1] not in id_dic:
            id_dic[entry[1]]=[index]
        else:
            id_dic[entry[1]].append(index)
    #extract the individual_id with more than one index
    multiple_dic={ k:v for k,v in id_dic.items() if len(v)>1 }
    #extract the individual_id with only one index, they don't need to be ordered
    single_dic={ k:v for k,v in id_dic.items() if len(v)==1 }
    for key in single_dic:
        new_data.append(data[id_dic[key][0]])
    for key in multiple_dic:
        #reorder the ones with more than one index
        new_dic={}
        for idx in range(0, len(id_dic[key])):
            #get the value of latest field for this multiple_dic key (individual_id)
            latest=data[id_dic[key][idx]][-2]
            #get the value of changed field for this multiple_dic key (individual_id)
            changed=data[id_dic[key][idx]][-3]
            #create dictionary with latest as key and tuple(s) as value(s) if latest=0
            if latest ==1:
                new_data.append(data[id_dic[key][idx]])
            else:
                new_dic[changed]=data[id_dic[key][idx]]
        #rearrange to sort according to changed date
        for key in reversed(sorted(new_dic)):
            new_data.append(new_dic[key])
    return new_data

def transpose_table(col, data):
    """transpose data from horizontal display to vertical one"""
    '''
    input col: field headers for individual(s) (list of tuple)
    input data: data for the individual(s) (list of tuple, [(4, '215F', ..., 1), (14, '2C9B', ..., 1)])
    return vertical_data: list of 'field, data_row1, data_row2' for each field  (list of list)
    return blank_position_list: list of fields before which blank lines have to be added (note that fields can be repeated)(list)
    '''
    vertical_data=[]
    index_blank_column=[]
    col_count_dic={}
    col_dic={}
    insert_col={}
    all_indiv_columns=['individual_id', 'supplier_name', 'alias', 'species_name', 'sex', 'accession', 'project_name', \
      'project_alias', 'project_accession', 'project_ssid', 'sample_name', 'sample_accession', 'sample_ssid', \
      'cv_attribute', 'cv_comment', 'value', 'unit', 'comment', 'country_of_origin', 'location', 'sub_location', \
      'latitude', 'longitude', 'provider_name', 'date_collected', 'collection_method', 'collection_details', 'father_name', \
      'mother_name', 'changed', 'latest', 'thumbnail']
    all_file_columns=['file_id', 'name', 'lane_name', 'format', 'accession', 'file_type', 'md5', 'nber_reads', \
      'total_length', 'average_length', 'location', 'changed', 'latest']
    new_columns=all_indiv_columns
    if col[0][0]=='file_id':
        new_columns=all_file_columns
    new_data=list(data)
    #dictionary of field_name as key and number of fields follow
    additional_columns={'project_name':4, 'sample_name':3, 'cv_attribute':5, 'country_of_origin' : 5, 'date_collected':3, 'father_name' :2}
    #create only one header column for display
    #create dictionary with col (and data) index as key and values are dictionaries with field_names as key and occurence in data[index] as value
    for row in col:
        col_count_dic[col.index(row)]={x:row.count(x) for x in row if x in list(additional_columns.keys()) and row.count(x) > 1}
    for row_key in col_count_dic:
        #field are the field names present for this individual
        for field in col_count_dic[row_key]:
            #count of occurence to add (-1 as already present once in headers)
            count=col_count_dic[row_key][field]-1
            for i in range(0, count):
                new_columns.insert(new_columns.index(field)+additional_columns[field], field)
                #special case for project_name, sample_name and cv_attribute as several fields have to be added
                if field=='project_name':
                    new_columns.insert(new_columns.index(field)+additional_columns[field]+1, 'project_alias')
                    new_columns.insert(new_columns.index(field)+additional_columns[field]+2, 'project_accession')
                    new_columns.insert(new_columns.index(field)+additional_columns[field]+3, 'project_ssid')
                elif field=='sample_name':
                    new_columns.insert(new_columns.index(field)+additional_columns[field]+1, 'sample_accession')
                    new_columns.insert(new_columns.index(field)+additional_columns[field]+2, 'sample_ssid')
                elif field=='cv_attribute':
                    new_columns.insert(new_columns.index(field)+additional_columns[field]+1, 'cv_comment')
                    new_columns.insert(new_columns.index(field)+additional_columns[field]+2, 'value')
                    new_columns.insert(new_columns.index(field)+additional_columns[field]+3, 'unit')
                    new_columns.insert(new_columns.index(field)+additional_columns[field]+4, 'comment')
    #if fields have been added to the headers, ensure that the number of field in new_columns is reflected in the data for each row
    for index in range(0, len(new_columns)):
        for row_key in range(0, len(data)):
            if col[row_key][index] != new_columns[index]:
                new_data[row_key].insert(index,'')
                col[row_key].insert(index,'')
    #create list for each field with header, data 1st row, data 2nd row etc ...
    for index in range(0, len(new_columns)):
        transpose_data=[new_columns[index]]
        for row in new_data:
            if index < len(row):
                transpose_data.append(row[index])
        #only display transposed data id there is value for at least one of the individual/file
        if transpose_data.count('') != len(transpose_data) -1:
            vertical_data.append(transpose_data)
    #function to add blank line separation in the vertical display
    for index in range(0, len(new_columns)):
        if new_columns[0]=='individual_id':
            if new_columns[index] in ('project_name', 'sample_name', 'country_of_origin', 'provider_name', 'date_collected', 'father_name', 'changed', 'thumbnail', 'cv_attribute'):
                index_blank_column.append(index)
        elif new_columns[0]=='file_id':
            if new_columns[index] in ('file_type', 'md5', 'location', 'changed'):
                index_blank_column.append(index)
    #extract the field corresponding to the index before which blank lines have to be added for display
    blank_position_list=[new_columns[x] for x in index_blank_column]
    return vertical_data, blank_position_list

def tuple_to_dic(col, data, json_header):
    final_dic={}
    final_dic[json_header]={}
    for entry in data:
        identifier=json_header[:-1]
        if json_header=='species':
            identifier=json_header
        final_dic[json_header][identifier+"_id="+str(entry[0])]={}
        final_dic[json_header][identifier+"_id="+str(entry[0])]['column']=('col','col')+tuple(col)
        final_dic[json_header][identifier+"_id="+str(entry[0])]['data']=[('data', 'data',) + tuple(entry)]
    return final_dic

def webresults_to_dic(results):
    """ function to transform data for display into subdictionaries to generate downloadable json"""
    '''
    input results: dictionary of reformatted data to download with identifier & identifier_id as key and list of column and table data as value (dic)
    return return_dic: dictionary of data with identifier as key and sub-dictionaries of table with field as key and corresponding data as value
    '''
    return_dic={}
    #create entries with id_dic as key (id_idc is "table : table_id")
    for id_dic in results:
        return_list=[]
        data_dic={}
        #1st subdictionary has table as key
        for table in results[id_dic]:
            new_list=[]
            col=results[id_dic][table]['column']
            res=results[id_dic][table]['data']
            #2nd subdictionary has field as key and corresponding data as value
            for entry in res:
                new_dic={}
                for index in range(1, len(entry)):
                    new_dic[col[index]]=entry[index]
                new_list.append(new_dic)
            data_dic[table]=new_list
        return_dic[id_dic]=data_dic
        return_list=[]
    return return_dic

################### PASSWORD FUNCTIONS #########################################
def hash_password(password):
    """Hash a password for storing."""
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'),
                                salt, 100000)
    pwdhash = binascii.hexlify(pwdhash)
    return (salt + pwdhash).decode('ascii')

def load_user(id):
    return query.get(int(id))

def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    salt = stored_password[:64]
    stored_password = stored_password[64:]
    pwdhash = hashlib.pbkdf2_hmac('sha512',
                                  provided_password.encode('utf-8'),
                                  salt.encode('ascii'),
                                  100000)
    pwdhash = binascii.hexlify(pwdhash).decode('ascii')
    return pwdhash == stored_password

################### WEB APP FUNCTIONS ##########################################
#@app.route('/')
#@app.route('/index')
@app.route('/index', methods=['GET', 'POST'])
def index():
    """main function for the main page where user can choose the way to interrogate the database"""
    individual_name=""
    list_proj=[]
    list_loc =[]
    db='darwin'
    ext_flag="web"
    if 'usrname' not in session:
        session['usrname']=""
        session['logged_in']=0
    session['name']=""
    session['criteria']=""
    status=0
    if session['logged_in']: status=1
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT accession, name FROM project")
        prows=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch projects")
    try:
        curs.execute("SELECT distinct location FROM location where location is not NULL")
        lrows=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location information")
    curs.close()
    #define menus to display to users
    for proj in prows:
        list_proj.append(proj[0]+" - " +proj[1])
    for loc in sorted(lrows):
        list_loc.append(loc[0])
    list_proj.append("  select a project")
    list_loc.append("  and / or select a location")
    form=EntryForm()
    if form.validate_on_submit():
        details=request.form
        project_acc=""
        individual_name=""
        species_name = ""
        flag=""
        loc_region=""
        accession=""
        sample_name=""
        sample_accession=""
        if not details['proj_choice'].startswith("  select"):
            project_acc=details['proj_choice']
            flag='A'
        if details['name']:
            individual_name=details['name']
            flag+="I"
        if details['spname']:
            species_name=details['spname']
            flag+="S"
        if details['sname']:
            sample_name=details['sname']
            flag+="X"
        if not details['loc_choice'].startswith("  and / or"):
            loc_region=details['loc_choice']
            flag+='L'
        if len(flag)==0:
            flash('Please enter your selection')
            return redirect(url_for('index'))
        if flag in ("AIS", "AISL") : flag='AI'
        if flag in ("AIL", "ISL") : flag='IL'
        if flag=="ASL": flag='AL'
        if flag in ('AISXL', 'AISX', 'AIXL', 'ASXL','ASX', 'AXL'): flag='AX'
        if flag in ('ISXL', 'ISX', 'IXL'): flag='IX'
        if flag in ('SXL', 'SX'): flag='SX'
        url_dic={'A':'get_project_per_accession', 'I': 'get_individual_per_individual_name', 'S': 'get_species_per_name',
        'AI':'get_individual_per_project_accession_and_name', 'AS': 'get_individual_per_project_accession_and_species',
        'AL':'get_project_per_accession_and_location', 'IL':'get_individual_per_name_and_per_location',
         'SL': 'get_species_per_name_and_per_location', 'L': 'get_individual_per_location', 'IS': 'get_individual_per_name_and_species_name',
         'X': 'get_samples_by_name', 'SX' : 'get_samples_by_sample_name_and_species', 'AX':'get_samples_by_sample_name_and_project',
         'IX' : 'get_samples_by_sample_name_and_individual_name', 'XL': 'get_samples_by_sample_name_and_location'}
        arg_dic={'A':project_acc.split(" - ")[0], 'I': individual_name, 'S': species_name,
        'AI': [project_acc.split(" - ")[0], individual_name], 'AS': [project_acc.split(" - ")[0], species_name]
        ,'L': loc_region, 'AL': [project_acc.split(" - ")[0], loc_region], 'IL' : [individual_name, loc_region],
        'SL': [species_name,loc_region], 'IS':[individual_name, species_name], 'X': sample_name,
        'SX':[sample_name, species_name], 'AX':[sample_name, project_acc.split(" - ")[0]],
        'IX' : [sample_name, individual_name], 'XL' : [sample_name, loc_region]}
        if flag == 'A':
            return redirect(url_for(url_dic[flag], accession=arg_dic[flag], ext_flag=ext_flag))
        elif flag == 'AI':
            return redirect(url_for(url_dic[flag], accession=arg_dic[flag][0], ind_name=arg_dic[flag][1],  ext_flag=ext_flag))
        elif flag == 'AS':
                return redirect(url_for(url_dic[flag], accession=arg_dic[flag][0], sp_name=arg_dic[flag][1],  ext_flag=ext_flag))
        elif flag=='I':
            return redirect(url_for(url_dic[flag], ind_name= individual_name,  ext_flag=ext_flag))
        elif flag=='IS':
            return redirect(url_for(url_dic[flag], ind_name= individual_name, sp_name=arg_dic[flag][1],  ext_flag=ext_flag))
        elif flag=='S':
            return redirect(url_for(url_dic[flag], sp_name=species_name,  ext_flag=ext_flag))
        elif flag =='L':
            return redirect(url_for(url_dic[flag], location=loc_region,  ext_flag=ext_flag))
        elif flag =='SL':
            return redirect(url_for(url_dic[flag], location=arg_dic[flag][1], sp_name=arg_dic[flag][0],  ext_flag=ext_flag))
        elif flag =='IL':
            return redirect(url_for(url_dic[flag], location=arg_dic[flag][1], ind_name=arg_dic[flag][0],  ext_flag=ext_flag))
        elif flag =='AL':
            return redirect(url_for(url_dic[flag], location=arg_dic[flag][1], accession=arg_dic[flag][0],  ext_flag=ext_flag))
        elif flag =='X':
            return redirect(url_for(url_dic[flag], sname=sample_name,  ext_flag=ext_flag))
        elif flag =='XL':
            return redirect(url_for(url_dic[flag], sname=sample_name, location=loc_region,  ext_flag=ext_flag))
        elif flag =='IX':
            return redirect(url_for(url_dic[flag], sname=sample_name, ind_name=individual_name,  ext_flag=ext_flag))
        elif flag =='SX':
            return redirect(url_for(url_dic[flag], sname=sample_name, sp_name=species_name,  ext_flag=ext_flag))
        elif flag =='AX':
            return redirect(url_for(url_dic[flag], sname=sample_name, accession=arg_dic[flag][-1],  ext_flag=ext_flag))
        else:
            return redirect(url_for('index'))
            flash("Please enter valid criteria")
    return render_template("entry.html", title='Query was: returnall', form=form, project_list=tuple(list_proj), loc_list=tuple(list_loc), db=db, ext_flag=ext_flag, log=status, usrname=session.get('usrname', None))

@app.route('/dashboard/')
def dashboard():
    return render_template("tab.html")

@app.route('/api/1.1/entry', methods=['GET', 'POST'])
def enter_data():
    """function for the entry page where user can update, overwrite or enter new data in the database"""
    usrname=session.get('usrname', None)
    form = EnterDataForm(request.form)
    provider_list=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct provider_name FROM provider")
        provider_res=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch provider names")
    curs.close()
    provider_list.append("-choose providers-")
    for prov in provider_res:
        provider_list.append(prov[0])
    #provider_list.append("-choose providers-")
    if request.method == "POST" and form.validate():
        results=request.form
        session['usrname']=usrname
        if 'Download' in results:
            return redirect(url_for('download'))
        elif 'Upload' in results:
            return redirect(url_for('upload', file = results['Upload']))
        else:
            flash("your data have been submitted successfully")
            return redirect(url_for('enter_data'))
    return render_template('enter_data.html', usrname=usrname, form=form, prov_list=tuple(provider_list), db=db, session=session)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """function to ensure that only authorized people can log in"""
    rows=""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        details=request.form
        curs = mysql.connection.cursor()
        try:
            curs.execute("SELECT * FROM users where username ='%s';" % details['username'])
            rows=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch items")
        curs.close()
        if len(rows) == 0:#if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        else :
            compare = verify_password(rows[0][3], details['password'])
            if compare:
                session['usrname']=rows[0][1]
                session['logged_in']=1
                return redirect(url_for('enter_data'))
            else:
                flash('Invalid password provided')
                return redirect(url_for('login'))
    return render_template('login.html', title='Sign In', form=form, db=db)

@app.route('/logout')
def logout():
    """function to logout"""
    logout_user()
    session['usrname']=""
    session['logged_in']=0
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """function for the main page where user can choose the way to interrogate the database"""
    try:
        form = RegistrationForm(request.form)
        if request.method == "POST" and form.validate():
            username  = form.username.data
            email = form.email.data
            password=form.password.data
            password2=form.password2.data
            email_list=('had38@cam.ac.uk','sam68@cam.ac.uk','sm15@sanger.ac.uk','hd2@sanger.ac.uk', 'mara@sanger.ac.uk', 'kj2@sanger.ac.uk', 'rd@sanger.ac.uk', 'rd109@cam.ac.uk')
            if password ==  password2:
                password = hash_password(form.password.data)
                curs = mysql.connection.cursor()
                x = curs.execute("SELECT * FROM users WHERE username = '{user}';".format(user=username))
                if int(x) > 0:
                    flash("That username is already taken, please choose another")
                    return render_template('register.html', form=form, db=db)
                else:
                    curs.execute("INSERT INTO users (username, password, email) VALUES ('{user}', '{psw}', '{eml}')".
                              format(user=username, psw=password, eml=email))
                    if email in email_list :
                        curs.execute("commit")
                        flash("Thanks for registering!")
                        return redirect(url_for('login'))
                    else:
                        msg = Message(body='username: '+username+'\nemail: '+email+'\npassword: '+password, subject = 'New registration', sender ='had38@cam.ac.uk', recipients = ['had38@cam.ac.uk'])
                        mail.send(msg)
                        return redirect(url_for('index'))
                        flash("Thanks for registering: your registration is now pending approval")
                    curs.close()
            else:
                flash("The passwords did not match, please try again")
                return render_template('register.html', form=form, db=db)
    except Exception as e:
        return("Issue: "+str(e))
    return render_template('register.html', title='Register', form=form, db=db)

@app.route('/api/1.1/download', methods=['GET', 'POST'])
def download():
    """function to provide the csv template to enter data"""
    return send_file("entry.tsv",
        mimetype="text/tsv",
        attachment_filename='entry.tsv',
                     as_attachment=True)

@app.route('/api/1.1/upload/<file>', methods=['GET', 'POST'])
def upload(file):
    """function to reupload the filled csv template to add, update or overwrite the database"""
    f = open(file, 'r')
    usrname=session.get('usrname', None)
    suffix=""
    #only keep lines with data
    File = [line for line in f if len(line.split(",")[0]) > 0]
    #check if file already exists for today to ensure to not overwrite if multiple upload on the same day by same submitter
    dir_content=glob.glob("upload_"+today+"*.tsv")
    if len(dir_content) > 0:
        existing_suffixes=[file.split("_")[2] for file in dir_content if len(file.split("_"))==4]
        if len(existing_suffixes) > 0:
            suffix="_"+str(int(max(existing_suffixes))+1)
        else:
            suffix="_1"
    flash ('file uploaded successfully')
    #save File as a tab-separated file
    with open("upload_"+today+suffix+"_"+usrname+".tsv", "w") as File_output:
        for line in File:
            File_output.write(line)
    return redirect(url_for('enter_data'))

@app.route('/api/1.1/info', methods=['GET', 'POST'])
def info():
    """function to display the about page"""
    proj=[]
    if db=='cichlid':
        proj.append(['East-African cichlid','The research involves studying evolutionary and population genetics in cichlid fishes via whole genome sequences and associated phenotypic variation.'])
        proj.append('This website and much of the data in it are funded by Wellcome grant WT207492.')
        proj.append('We thank our collaborators George Turner (Bangor University), Martin Genner (University of Bristol), Hannes Svardal (University of Antwerp), Eric Miska (Gurdon Institute, Cambridge), Emilia Santos (Dept. of Zoology, Cambridge) and members of their teams, and Milan Malinsky (University of Basel) for contributing samples and data.')
        proj.append([['https://www.ncbi.nlm.nih.gov/pubmed/30455444', 'Whole-genome sequences of Malawi cichlids reveal multiple radiations interconnected by gene flow.'],['Malinsky M, Svardal H, Tyers AM, Miska EA, Genner MJ, Turner GF, Durbin R', 'Nat Ecol Evol. 2018 Dec;2(12):1940-1955','doi: 10.1038/s41559-018-0717-x.']])
    elif db=='darwin':
        proj.append(['Darwin Tree of Life','This project aims at sequencing all species of animal and plant in the United Kingdom.'])
        proj.append('Richard Durbin')
        proj.append('names of people involve (TBC)')
        proj.append([['https://www.sanger.ac.uk/news/view/genetic-code-60000-uk-species-be-sequenced', 'Genetic code of 60,000 UK species to be sequenced'], ['Wellcome Sanger Institute']])
    return render_template("about.html", db=db, log=session['logged_in'], proj=proj, usrname=session.get('usrname', None))

@app.route('/api/1.1/faq', methods=['GET', 'POST'])
def faq():
    """function to display the faq page"""
    proj=[]
    if db=='cichlid':
        proj.append('East-African cichlid')
        proj.append('D01-A03')
        proj.append('Liwonde')
    elif db=='darwin':
        proj.append('Darwin')
        proj.append('fMasArm1')
        proj.append('Sumatra')
    return render_template("faq.html", db=db, log=session['logged_in'], proj=proj, usrname=session.get('usrname', None))

################### API RELATED FUNCTIONS ######################################
@app.route('/api/1.1/file/<f_id>/<ext_flag>', methods=['GET'])
def get_file_per_file_id(f_id, ext_flag):
    pcolumns=get_columns_from_table('project')
    icolumns=['row_id', 'individual_id', 'name', 'alias', 'species_id', 'sex', 'location_id']
    mcolumns=['row_id', 'material_id', 'individual_id', 'name', 'date_received', 'type', 'developmental_stage_id', 'organism_part_id']
    scolumns=['row_id', 'sample_id', 'material_id', 'accession', 'ssid', 'name']
    fcolumns=['row_id', 'file_id', 'lane_id', 'name', 'format', 'type', 'md5', 'nber_reads', 'total_length', 'average_length']
    file_results={}
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id left join \
        individual i on i.individual_id=a.individual_id left join material m on m.individual_id = i.individual_id left join \
        sample s on s.material_id=m.material_id left join lane l on l.sample_id = s.sample_id left join file f on \
        f.lane_id =l.lane_id where f.file_id = '%s'" % f_id)
        presults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch project data")
    try:
        curs.execute("select distinct i.row_id, i.individual_id, i.name, i.alias, i.species_id, i.sex, i.location_id FROM individual i \
        join material m on m.individual_id = i.individual_id left join sample s on s.material_id=m.material_id \
        left join lane l on l.sample_id = s.sample_id left join file f on f.lane_id = l.lane_id where \
        i.latest=1 and f.file_id ='%s'" % f_id)
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individual data")
    try:
        curs.execute("select distinct m.row_id, m.material_id, m.individual_id, m.name, m.date_received, m.type, \
        m.developmental_stage_id, m.organism_part_id FROM material m left join sample s \
        on s.material_id=m.material_id left join lane l on l.sample_id = s.sample_id left join \
        file f on f.lane_id = l.lane_id where m.latest = 1 and f.file_id ='%s'" %f_id)
        mresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch material data")
    try:
        curs.execute("select distinct s.row_id, s.sample_id, s.material_id, s.accession, s.ssid, s.name  FROM sample s \
        left join lane l on l.sample_id = s.sample_id left join file f on f.lane_id = l.lane_id where s.latest=1 \
        and f.file_id  ='%s'" % f_id)
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch sample data")
    try:
        curs.execute("select distinct f.row_id, f.file_id, f.lane_id, f.name, f.format, f.type, f.md5, f.nber_reads, \
        f.total_length, f.average_length FROM file f where f.latest =1 and f.file_id ='%s'" % f_id)
        fresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch file data")
    curs.close()
    table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
    file_results[f_id]=table_dic
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(file_results, col_dic, ext_flag, "file")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        if len(session['criteria']) > 0:
            for_display=session['criteria']
        else:
            for_display="file name (file_id)= '"+fresults[0][3]+"' ("+str(f_id)+")"
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['file',  0, '/web' ], results=web_results, plus=['/api/1.1/file/'+f_id+'/all/web','yes'],db=db, log=session['logged_in'], usrname=session.get('usrname', None), first_display='file')

@app.route('/api/1.1/file/<f_id>/all/<ext_flag>', methods=['GET'])
def get_file_per_file_id_all(f_id, ext_flag):
    pcolumns=get_columns_from_table('project')
    icolumns=get_columns_from_table('individual')
    mcolumns=get_columns_from_table('material')
    scolumns=get_columns_from_table('sample')
    fcolumns=get_columns_from_table('file')
    file_results={}
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id left join \
        individual i on i.individual_id=a.individual_id left join material m on m.individual_id = i.individual_id left join \
        sample s on s.material_id=m.material_id left join lane l on l.sample_id = s.sample_id left join file f on \
        f.lane_id =l.lane_id where f.file_id = '%s'" % f_id)
        presults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch project data")
    try:
        curs.execute("select distinct i.* FROM individual i join material m on m.individual_id = i.individual_id \
        left join sample s on s.material_id=m.material_id left join lane l on l.sample_id = s.sample_id left \
         join file f on f.lane_id = l.lane_id where i.latest=1 and f.file_id ='%s'" % f_id)
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individual data")
    try:
        curs.execute("select distinct m.* FROM material m left join sample s \
        on s.material_id=m.material_id left join lane l on l.sample_id = s.sample_id left join \
        file f on f.lane_id = l.lane_id where m.latest = 1 and f.file_id ='%s'" %f_id)
        mresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch material data")
    try:
        curs.execute("select distinct s.*  FROM sample s left join lane l on l.sample_id = s.sample_id \
        left join file f on f.lane_id = l.lane_id where s.latest=1 and f.file_id  ='%s'" % f_id)
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch sample data")
    try:
        curs.execute("select distinct f.* FROM file f where f.latest =1 and f.file_id ='%s'" % f_id)
        fresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch file data")
    curs.close()
    table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
    file_results[f_id]=table_dic
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(file_results, col_dic, ext_flag, "file")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        if len(session['criteria']) > 0:
            for_display=session['criteria']
        else:
            for_display="file name (file_id)= '"+fresults[0][3]+"' ("+str(f_id)+")"
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['file',  0, '/web' ], results=web_results, plus=['/api/1.1/file/'+f_id+'/web','no'],db=db, log=session['logged_in'], usrname=session.get('usrname', None), first_display='file')

@app.route('/api/1.1/image/<im_id>/<ext_flag>', methods=['GET'])
def get_image_per_image_id(im_id, ext_flag):
    results=[]
    columns=get_columns_from_table('image')
    col=[columns[0]]+[columns[2]]+[columns[1]]+['thumbnail']+list(columns[3:])
    columns=tuple(col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT individual_id, filename FROM image where latest=1 and image_id = '%s';" % im_id)
        img_results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch images")
    curs.close()
    if len(img_results)==0:
        if ext_flag=='json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
    else:
        if img_results[0][0] is None:
            flash ("There was no individual associated with this image")
            return redirect(url_for('get_images', ext_flag=ext_flag))
        else:
            session['criteria']="image name (image_id)= "+str(img_results[0][-1]) +" ("+str(im_id)+")"
            return redirect(url_for('get_individual_per_individual_id', i_id="("+str(img_results[0][0])+")", ext_flag=ext_flag))

@app.route('/api/1.1/image/<ext_flag>', methods=['GET'])
def get_images(ext_flag):
    results=[]
    columns=get_columns_from_table('image')
    col=[columns[0]]+[columns[1]]+[columns[2]]+['thumbnail']+[columns[4]]
    columns=tuple(col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT i.* FROM image i left join individual ind on i.individual_id=ind.individual_id where i.latest=1 order by i.individual_id")
        img_results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch images")
    curs.close()
    if len(img_results) == 0:
        if ext_flag=='json':
            return jsonify({"Data error":"no image data available in the database '"+db+"'"})
        else:
            flash ("Error: no image data available in the database '"+db+"'")
            return redirect(url_for('index'))
    for row in img_results:
        i_results=[row[0]]+[row[1]]+[row[2]]+list([row[3]+"/"+row[2]])+[row[4]]
        results.append(tuple(i_results))
    new_column, display_results= change_for_display([columns], results, ext_flag)
    if ext_flag=='json':
        json_results=tuple_to_dic(new_column[0],display_results, "images")
        return jsonify(webresults_to_dic(json_results))
    else:
        #for image display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), plus ([0] to create link , [1] select if '+' or '-' is displayed)crumbs (to display navigation history))
        return render_template("image2.html", title='Query was: all images', url_param=['image', 0, '/web'], results=[new_column[0],display_results], plus=['all/web', 'yes'], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/image/all/<ext_flag>', methods=['GET'])
def get_images_all(ext_flag):
    results=[]
    columns=get_columns_from_table('image')
    col=[columns[0]]+[columns[1]]+[columns[2]]+['thumbnail']+list(columns[3:])
    columns=tuple(col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT i.* FROM image i left join individual ind on i.individual_id=ind.individual_id where i.latest=1 order by i.individual_id")
        img_results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch images")
    curs.close()
    if len(img_results)==0:
        if ext_flag=='json':
            return jsonify({"Data error":"no image data available in the database '"+db+"'"})
        else:
            flash ("Error: no image data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        for row in img_results:
            i_results=[row[0]]+[row[1]]+[row[2]]+list([row[3]+"/"+row[2]])+list(row[3:])
            results.append(tuple(i_results))
        new_column, display_results= change_for_display([columns], results, ext_flag)
        if ext_flag=='json':
            json_results=tuple_to_dic(new_column[0],display_results, "images")
            return jsonify(webresults_to_dic(json_results))
        else:
            #for image display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), plus ([0] to create link , [1] select if '+' or '-' is displayed), crumbs (to display navigation history))
            return render_template("image2.html", title='Query was: all images', url_param=['image', 0, '/web'], results=[new_column[0],display_results], plus=['/api/1.1/image/web', 'no'], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/individual/<i_id>/<ext_flag>', methods=['GET'])
def get_individual_per_individual_id(i_id, ext_flag):
    pcolumns=list(get_columns_from_table('project'))
    icolumns=['row_id', 'individual_id', 'name', 'alias', 'species_id', 'sex', 'location_id']
    mcolumns=['row_id', 'material_id', 'individual_id', 'name', 'date_received', 'type', 'developmental_stage_id', 'organism_part_id', 'sample(s)']
    scolumns=['row_id', 'sample_id', 'material_id', 'accession', 'ssid', 'name']
    fcolumns=['row_id', 'file_id', 'lane_id', 'name', 'format', 'type', 'md5', 'nber_reads', 'total_length', 'average_length']
    individual_results={}
    curs = mysql.connection.cursor()
    i_id=i_id.replace('None,','')
    if "(" in i_id or '%28' in i_id:
        i_id=i_id[1:-1]
        space_i_id=i_id.replace(",",", ")
    else:
        session['criteria']=""
        space_i_id=i_id.replace(",",", ")
    list_i_id=i_id.split(',')
    list_i_name=[]
    for individual_id in list_i_id:
        try:
            curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id left join \
            individual i on i.individual_id=a.individual_id where i.latest=1 and i.individual_id = %s" % individual_id)
            presults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch project data")
        try:
            curs.execute("select distinct i.row_id, i.individual_id, i.name, i.alias, i.species_id, i.sex, i.location_id FROM individual i \
            where i.latest=1 and i.individual_id = %s" % individual_id)
            iresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch individual data")
        if len(iresults) > 0: list_i_name.append(iresults[0][2])
        try:
            curs.execute("select distinct m.row_id, m.material_id, m.individual_id, m.name, m.date_received, m.type, \
            m.developmental_stage_id, m.organism_part_id , (select count(s.sample_id) FROM sample s join material m on m.material_id=s.material_id \
            where m.latest=1 and s.latest =1 and m.individual_id = {individual_id}) \
            from material m where m.individual_id = {individual_id}" .format(individual_id = individual_id))
            mresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch material data")
        try:
            curs.execute("select distinct s.row_id, s.sample_id, s.material_id, s.accession, s.ssid, s.name  FROM sample s join material m \
            on m.material_id = s.material_id where s.latest=1 and m.latest=1 and m.individual_id  = %s" % individual_id)
            sresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch sample data")
        try:
            curs.execute("select distinct f.row_id, f.file_id, f.lane_id, f.name, f.format, f.type, f.md5, f.nber_reads, \
            f.total_length, f.average_length FROM file f left join lane l on l.lane_id=f.lane_id left join sample s on \
            s.sample_id =l.sample_id left join material m on m.material_id = s.material_id where \
            m.latest=1 and s.latest=1 and l.latest=1 and f.latest =1 and m.individual_id = %s" % individual_id)
            fresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch file data")
        table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
        individual_results[individual_id]=table_dic
    curs.close()
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(individual_results, col_dic, ext_flag, "individual")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        if len(session['criteria']) > 0:
            for_display=session['criteria']
        else:
            for_display="individual name (individual_id)= "+", ".join(list_i_name)+" ("+space_i_id+")"
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['individual',  0, '/web' ], results=web_results, plus=['/api/1.1/individual/('+i_id+')/all/web','yes'],db=db, log=session['logged_in'], usrname=session.get('usrname', None), first_display='individual')

@app.route('/api/1.1/individual/<i_id>/all/<ext_flag>', methods=['GET'])
def get_individual_per_individual_id_all(i_id, ext_flag):
    pcolumns=get_columns_from_table('project')
    ind_columns=get_columns_from_table('individual')
    ind_id_columns=get_columns_from_table('individual_data')
    icolumns=ind_columns[:12]+ind_id_columns[2:6]+ind_columns[12:]
    mcolumns=get_columns_from_table('material')
    scolumns=get_columns_from_table('sample')
    fcolumns=get_columns_from_table('file')
    individual_results={}
    curs = mysql.connection.cursor()
    if "(" in i_id or '%28' in i_id:
        i_id=i_id[1:-1]
        space_i_id=i_id.replace(",", ", ")
    else:
        session['criteria']=""
        space_i_id=i_id.replace(",", ", ")
    list_i_id=i_id.split(',')
    list_i_name=[]
    for individual_id in list_i_id:
        try:
            curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id left join \
            individual i on i.individual_id=a.individual_id where i.latest=1 and i.individual_id =  %s" % individual_id)
            presults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch project data")
        try:
            curs.execute("select distinct i.row_id, i.individual_id, i.name, i.alias, i.species_id, i.sex, \
            i.accession, i.location_id, i.provider_id, i.date_collected, i.collection_method, i.collection_details, \
            id.cv_id, id.value, id.unit, id.comment, i.father_id, i.mother_id, i.changed, i.latest FROM individual i \
            left join individual_data id on i.individual_id=id.individual_id \
            where i.latest=1 and i.individual_id = %s" % individual_id)
            iresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch individual data")
        if len(iresults) > 0: list_i_name.append(iresults[0][2])
        try:
            curs.execute("select distinct m.* FROM material m where m.latest=1 and m.individual_id = %s" % individual_id)
            mresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch material data")
        try:
            curs.execute("select distinct s.*  FROM sample s join material m \
            on m.material_id = s.material_id where s.latest=1 and m.latest=1 and m.individual_id  = %s" % individual_id)
            sresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch sample data")
        try:
            curs.execute("select distinct f.* FROM file f left join lane l on l.lane_id=f.lane_id left join sample s on \
            s.sample_id =l.sample_id left join material m on m.material_id = s.material_id where \
            m.latest=1 and s.latest=1 and l.latest=1 and f.latest =1 and m.individual_id = %s" % individual_id)
            fresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch file data")
        table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
        individual_results[individual_id]=table_dic
    curs.close()
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(individual_results, col_dic, ext_flag, "individual")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        if len(session['criteria']) > 0:
            for_display=session['criteria']
        else:
            for_display="individual name (individual_id)= "+", ".join(list_i_name)+" ("+space_i_id+")"
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['individual',  0, '/web' ], results=web_results, plus=['/api/1.1/individual/('+i_id+')/web','no'],db=db, log=session['logged_in'], usrname=session.get('usrname', None), first_display='individual')

@app.route('/api/1.1/individual/name/<ind_name>/<ext_flag>', methods=['GET'])
def get_individual_per_individual_name(ind_name, ext_flag):
    ind_list=ind_name.replace(" ","").replace(",", "','")
    results=""
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.individual_id, im.image_id FROM individual i left join image im on i.individual_id=im.individual_id where i.latest=1 and i.name in ('{identif}') or i.alias in ('{identif}') ". format(identif=ind_list))
        i_results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
    curs.close()
    if len(i_results)== 0:
        if ext_flag=='json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('index'))
    else:
        for row in i_results:
            if str(row[0]) not in results:
                results+=","+str(row[0])
        if ext_flag=='json':
            return get_individual_per_individual_id(i_id=results[1:], ext_flag=ext_flag)
        else:
            return(redirect(url_for('get_individual_per_individual_id', i_id=results[1:], db=db, ext_flag=ext_flag)))

@app.route('/api/1.1/individual/<ext_flag>', methods=['GET'])
def get_individuals(ext_flag):
    icolumns=get_columns_from_table('individual')
    columns=list(icolumns[1:8]+tuple(['samples']))
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct i.individual_id, i.name, i.alias, i.species_id, i.sex, i.accession, i.location_id, \
        count(distinct s.sample_id) from individual i left join material m on m.individual_id=i.individual_id \
        left join sample s on s.material_id=m.material_id where i.latest=1 group by i.individual_id, i.name, \
        i.alias, i.species_id, i.sex, i.accession, i.location_id")
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
    curs.close()
    if len(iresults)==0:
        if ext_flag=='json':
            return jsonify({"Data error":"no individual data available in the database '"+db+"'"})
        else:
            flash ("Error: no individual data available in the database '"+db+"'")
    else:
        new_columns, results= change_for_display(list([tuple(columns)]), list(iresults), ext_flag)
        display_results=remove_column(remove_column(results, -3), -2)
        columns=new_columns[0][:-4]+new_columns[0][-2:-1]
        if ext_flag=='json':
            json_results=tuple_to_dic(columns, remove_column(display_results, 'L'), "individuals")
            return jsonify(webresults_to_dic(json_results))
        else:
            if session.get('html', None) =='image':
                return redirect(url_for('get_images', ext_flag=ext_flag))
            else:
                #for image display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), plus ([0] to create link , [1] select if '+' or '-' is displayed), crumbs (to display navigation history))
                return render_template("mysql.html", title='Query was: all individuals', url_param=['individual', 0, '/web'], results=[columns, remove_column(display_results, 'L')], plus=['/api/1.1/individual/all/web', 'yes'], db=db, ext_flag=ext_flag,  log=session['logged_in'], usrname=session.get('usrname', None), first_display='individual')

@app.route('/api/1.1/individual/all/<ext_flag>', methods=['GET'])
def get_individuals_all(ext_flag):
    ind_columns=get_columns_from_table('individual')
    ind_id_columns=get_columns_from_table('individual_data')
    icolumns=ind_columns[:12]+ind_id_columns[2:6]+ind_columns[12:]
    columns=list(icolumns[1:]+tuple(['samples']))
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct i.individual_id, i.name, i.alias, i.species_id, i.sex, i.accession, i.location_id, i.provider_id, \
        i.date_collected, i.collection_method, i.collection_details,  id.cv_id, id.value, id.unit, id.comment, i.father_id, i.mother_id, i.changed, i.latest, count(distinct s.sample_id) \
        from individual i left join individual_data id on id.individual_id=i.individual_id left join material m on m.individual_id=i.individual_id left join sample s on s.material_id=m.material_id where i.latest=1 and \
        s.latest=1 group by i.individual_id, i.name, i.alias, i.species_id, i.sex, i.accession, i.location_id, i.provider_id,  \
        i.date_collected, i.collection_method, i.collection_details,  id.cv_id, id.value, id.unit, id.comment, i.father_id, i.mother_id, i.changed, i.latest")
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
    curs.close()
    if len(iresults)==0:
        if ext_flag=='json':
            return jsonify({"Data error":"no individual data available in the database '"+db+"'"})
        else:
            flash ("Error: no individual data available in the database '"+db+"'")
    else:
        new_columns, display_results= change_for_display(list([tuple(columns)]), list(iresults), ext_flag)
        if ext_flag=='json':
            json_results=tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L'), "individuals")
            return jsonify(webresults_to_dic(json_results))
        else:
            if session.get('html', None) =='image':
                return redirect(url_for('get_images', ext_flag=ext_flag))
            else:
                #for classical display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), plus ([0] to create link , [1] select if '+' or '-' is displayed), crumbs (to display navigation history))
                return render_template("mysql.html", title='Query was: all individuals', url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['/api/1.1/individual/web', 'no'],db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/lane/<l_id>/<ext_flag>', methods=['GET'])
def get_lane_per_lane_id(l_id, ext_flag):
    results=[]
    lane_acc_dic={}
    lcolumns=get_columns_from_table('lane')
    columns=tuple([lcolumns[1]]+[lcolumns[7]]+[lcolumns[6]]+list(lcolumns[3:6])+list(lcolumns[8:]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct f.file_id, l.accession FROM file f join lane l on l.lane_id=f.file_id where f.latest=1 and f.lane_id = '%s';" % l_id)
        lresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch lanes")
    curs.close()
    if len(lresults)==0:
        if ext_flag=='json':
            return jsonify({"Data error":"no lane associated with criteria provided"})
        else:
            flash ("Error: no lane associated with criteria provided")
    else:
        session['criteria']="lane accession (lane_id)= "+str(lresults[0][-1]) +" ("+str(l_id)+")"
        return redirect(url_for('get_file_per_file_id', f_id=lresults[0][0], ext_flag=ext_flag))

@app.route('/api/1.1/lane/<ext_flag>', methods=['GET'])
def get_lanes(ext_flag):
    lcolumns=get_columns_from_table('lane')
    columns=tuple([lcolumns[1]])+tuple([lcolumns[6]])+tuple([lcolumns[2]])+tuple([lcolumns[3]]) +tuple([lcolumns[6]]) +tuple([lcolumns[7]]) + tuple(["files"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct l.lane_id,l.name,l.sample_id, l.seq_tech_id, l.library_id, l.accession, \
        count(distinct f.file_id) from lane l join file f on f.lane_id=l.lane_id where l.latest=1 and f.latest=1 group by \
        l.lane_id,l.name,l.sample_id, l.seq_tech_id, l.library_id, l.accession")
        lresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch lanes")
    curs.close()
    if len(lresults)==0:
        if ext_flag=='json':
            return jsonify({"Data error":"no lane data available in the database '"+db+"'"})
        else:
            flash ("Error: no lane data available in the database '"+db+"'")
    else:
        new_column, display_results= change_for_display([columns], list(lresults), ext_flag)
        if ext_flag=='json':
            json_results=tuple_to_dic(new_column[0], display_results, "lanes")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all lanes', url_param=['lane', 0, '/web'], results=[new_column[0], display_results], plus =['all/web','yes'], db=db, log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/lane/all/<ext_flag>', methods=['GET'])
def get_lanes_all(ext_flag):
    lcolumns=get_columns_from_table('lane')
    columns=[lcolumns[1]]+[lcolumns[6]]+list(lcolumns[2:6]) + list(lcolumns[7:] +tuple(["files"]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct l.lane_id,l.name,l.sample_id, l.seq_tech_id, l.seq_centre_id, l.library_id, l.accession, l.ss_qc_status, l.auto_qc_status, l.manually_withdrawn, l.run_date, l.changed, l.latest, \
        count(distinct f.file_id) from lane l join file f on f.lane_id=l.lane_id where l.latest=1 and f.latest=1 group by l.lane_id,l.name,l.sample_id, l.seq_tech_id, \
        l.seq_centre_id, l.library_id, l.accession,l.ss_qc_status, l.auto_qc_status, l.manually_withdrawn, l.run_date, l.changed, l.latest")
        lresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch lanes")
    curs.close()
    if len(lresults)==0:
        if ext_flag=='json':
            return jsonify({"Data error":"no lane data available in the database '"+db+"'"})
        else:
            flash ("Error: no lane data available in the database '"+db+"'")
    else:
        new_column, display_results= change_for_display([columns], lresults, ext_flag)
        if ext_flag=='json':
            json_results=tuple_to_dic(new_column[0], display_results, "lanes")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all lanes', url_param=['lane', 0, '/web'], results=[new_column[0], display_results], plus=['/api/1.1/lane/web','no'], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/location/<loc_id>/<ext_flag>', methods=['GET'])
def get_individual_per_location_id(loc_id, ext_flag):
    columns=get_columns_from_table('individual')[1:]
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.individual_id, l.location FROM individual i join location l on l.location_id=i.location_id \
        where i.location_id = %s and i.latest=1;" % loc_id)
        res=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
    curs.close()
    if len(res)==0:
        if ext_flag=='json':
            return jsonify({"Data error":"no location associated with criteria provided"})
        else:
            flash ("Error: no location associated with criteria provided")
    else:
        list_individual_id=",".join([str(x[0]) for x in res])
        session['criteria']="location name (location_id)= "+res[0][-1] +" ("+str(loc_id)+")"
        return redirect(url_for('get_individual_per_individual_id', i_id="("+list_individual_id+")", ext_flag=ext_flag))

@app.route('/api/1.1/location/<loc_id>/individual/<ind_id>/<ext_flag>', methods=['GET'])
def get_individual_per_id_and_per_location_id(loc_id, ind_id, ext_flag):
    list_loc_id ="("+loc_id+")"
    loc_columns=get_columns_from_table('individual')
    columns=loc_columns[1:8]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct I.*, L.location FROM individual I join location L on L.location_id = I.location_id \
        join species S on S.species_id = I.species_id where I.latest=1 and L.location_id in {reg} and I.individual_id = '{indl}' ;". format(reg=list_loc_id, indl=ind_id))
        lresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location and / or individual")
    curs.close
    if len(lresults) > 0:
        results="("+",".join([str(x[0]) for x in lresults])+")"
        return(redirect(url_for('get_individual_per_individual_id', i_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'location_id=' +str(loc_id)+' and individual_id='+str(ind_id):'No data available'})
        else:
            flash ("no location associated with the name provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/location/name/<location>/<ext_flag>', methods=['GET'])
def get_individual_per_location(location, ext_flag):
    loc_columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.individual_id, l.location_id from location l join individual i on \
        l.location_id = i.location_id where i.latest=1 and l.location = '{loc}' or sub_location = '{loc}';". format(loc=location))
        lresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location")
    curs.close()
    if len(lresults) > 0:
        results="("+",".join([str(x[0]) for x in lresults])+")"
        session['criteria']="location name (location_id)= "+location+" ("+str(lresults[0][-1])+")"
        return(redirect(url_for('get_individual_per_individual_id', i_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'location name=' +location:'No data available'})
        else:
            flash ("no location associated with the name provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/location/name/<location>/individual/name/<ind_name>/<ext_flag>', methods=['GET'])
def get_individual_per_name_and_per_location(location, ind_name, ext_flag):
    ind_list=ind_name.replace(" ","").replace(",", "','")
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.individual_id FROM individual i join location l on l.location_id = i.location_id \
        join species s on s.species_id = i.species_id where i.latest=1 and l.location = '{reg}' and (i.name in ('{indl}') \
        or i.alias in ('{indl}')) ;". format(reg=location, indl=ind_list))
        lresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location and / or individual")
    curs.close()
    if len(lresults) > 0:
        results="("+",".join([str(x[0]) for x in lresults])+")"
        return(redirect(url_for('get_individual_per_individual_id', i_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'location name=' +location+' and individual name='+ind_name:'No data available'})
        else:
            flash ("no individual associated with the criteria provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/location/name/<location>/sample/name/<sname>/<ext_flag>', methods=['GET'])
def get_samples_by_sample_name_and_location(sname, location, ext_flag):
    s_list="('"+sname.replace(" ","").replace(",", "','")+"')"
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.sample_id from sample s join material m on m.material_id = s.material_id join individual i \
        on i.individual_id=m.individual_id left join location l on l.location_id=i.location_id where s.latest=1 \
        and (s.accession in {s_list} or s.name in {s_list}) and l.location='{loc}';".format(loc=location, s_list=s_list))
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples with these criteria")
    curs.close()
    if len(sresults) > 0:
        results="("+",".join([str(x[0]) for x in sresults])+")"
        return(redirect(url_for('get_sample_per_sample_id', s_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'location name=' +location+' and sample name='+sname:'No data available'})
        else:
            flash ("no sample associated with the criteria provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/location/name/<location>/species/name/<sp_name>/<ext_flag>', methods=['GET'])
def get_species_per_name_and_per_location(location, sp_name, ext_flag):
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.individual_id FROM individual i join location l on l.location_id = l.location_id \
        join species s on s.species_id = i.species_id where i.latest=1 and l.location = '{reg}' and \
        (s.name like '%%{spn}%%' or s.common_name like '%%{spn}%%');". format(reg=location, spn=sp_name))
        spresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location and / or species")
    curs.close()
    if len(spresults) > 0:
        results="("+",".join([str(x[0]) for x in spresults])+")"
        return(redirect(url_for('get_individual_per_individual_id', i_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'location name=' +location+' and species name='+sp_name:'No data available'})
        else:
            flash ("no individual associated with the criteria provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/location/<ext_flag>', methods=['GET'])
def get_location(ext_flag):
    loc_columns=get_columns_from_table('location')
    columns=list(loc_columns)+["species", "individuals"]
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct l.location_id, l.country_of_origin, l.location, l.sub_location, l.latitude, l.longitude, \
        count(distinct i.species_id) , count(distinct i.individual_id) from location l join individual i on l.location_id = i.location_id \
        where  i.latest = 1 group by l.location_id, l.country_of_origin, l.location, l.sub_location, l.latitude, l.longitude")
        l_results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch locations")
    curs.close()
    if len(l_results) == 0:
        if ext_flag=='json':
            return jsonify({"Data error":"no location data available in the database '"+db+"'"})
        else:
            flash ("Error: no location data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        for row in l_results:
            row=['' if x is None else x for x in row]
            row[4]=str(row[4])
            row[5]=str(row[5])
            results.append(row)
        if ext_flag=='json':
            json_results=tuple_to_dic(columns, results, "locations")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all locations', url_param=['location',0, '/web'], results=[columns,results], plus =['.',''], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/material/<m_id>/<ext_flag>', methods=['GET'])
def get_material_per_material_id(m_id, ext_flag):
    pcolumns=get_columns_from_table('project')
    icolumns=['row_id', 'individual_id', 'name', 'alias', 'species_id', 'sex', 'location_id']
    mcolumns=['row_id', 'material_id', 'individual_id', 'name', 'date_received', 'type', 'developmental_stage_id', 'organism_part_id']
    scolumns=['row_id', 'sample_id', 'material_id', 'accession', 'ssid', 'name']
    fcolumns=['row_id', 'file_id', 'lane_id', 'name', 'format', 'type', 'md5', 'nber_reads', 'total_length', 'average_length']
    material_results={}
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id left join \
        individual i on i.individual_id=a.individual_id left join material m on m.individual_id = i.individual_id where \
        m.material_id = '%s'" % m_id)
        presults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch project data")
    try:
        curs.execute("select distinct i.row_id, i.individual_id, i.name, i.alias, i.species_id, i.sex, i.location_id FROM individual i \
        join material m on m.individual_id = i.individual_id where i.latest=1 and m.material_id ='%s'" % m_id)
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individual data")
    try:
        curs.execute("select distinct m.row_id, m.material_id, m.individual_id, m.name, m.date_received, m.type, \
        m.developmental_stage_id, m.organism_part_id FROM material m where m.latest=1 and m.material_id ='%s'" %m_id)
        mresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch material data")
    try:
        curs.execute("select distinct s.row_id, s.sample_id, s.material_id, s.accession, s.ssid, s.name  FROM sample s join material m \
        on m.material_id = s.material_id where s.latest=1 and m.material_id  ='%s'" % m_id)
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch sample data")
    try:
        curs.execute("select distinct f.row_id, f.file_id, f.lane_id, f.name, f.format, f.type, f.md5, f.nber_reads, \
        f.total_length, f.average_length FROM file f left join lane l on l.lane_id=f.lane_id left join sample s on \
        s.sample_id =l.sample_id left join material m on m.material_id = s.material_id where \
        m.latest=1 and s.latest=1 and l.latest=1 and f.latest =1 and m.material_id ='%s'" % m_id)
        fresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch file data")
    curs.close()
    table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
    material_results[m_id]=table_dic
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(material_results, col_dic, ext_flag, "material")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        for_display="material name (material_id)= "+mresults[0][3]+" ("+str(m_id)+")"
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['material',  0, '/web' ], results=web_results, plus=['/api/1.1/material/'+m_id+'/all/web','yes'],db=db, ext_flag=ext_flag, log=session['logged_in'], usrname=session.get('usrname', None), first_display='material')

@app.route('/api/1.1/material/<m_id>/all/<ext_flag>', methods=['GET'])
def get_material_per_material_id_all(m_id, ext_flag):
    pcolumns=get_columns_from_table('project')
    icolumns=get_columns_from_table('individual')
    mcolumns=get_columns_from_table('material')
    scolumns=get_columns_from_table('sample')
    fcolumns=get_columns_from_table('file')
    material_results={}
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id left join \
        individual i on i.individual_id=a.individual_id left join material m on m.individual_id = i.individual_id where \
        m.material_id = '%s'" % m_id)
        presults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch project data")
    try:
        curs.execute("select distinct i.* FROM individual i join material m on m.individual_id = i.individual_id \
        where i.latest=1 and m.material_id ='%s'" % m_id)
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individual data")
    try:
        curs.execute("select distinct m.* FROM material m where m.latest=1 and m.material_id ='%s'" %m_id)
        mresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch material data")
    try:
        curs.execute("select distinct s.*  FROM sample s join material m \
        on m.material_id = s.material_id where s.latest=1 and m.material_id  ='%s'" % m_id)
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch sample data")
    try:
        curs.execute("select distinct f.* FROM file f left join lane l on l.lane_id=f.lane_id left join sample s on \
        s.sample_id =l.sample_id left join material m on m.material_id = s.material_id where \
        m.latest=1 and s.latest=1 and l.latest=1 and f.latest =1 and m.material_id ='%s'" % m_id)
        fresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch file data")
    curs.close()
    table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
    material_results[m_id]=table_dic
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(material_results, col_dic, ext_flag, "material")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        for_display="material name (material_id)= "+mresults[0][4]+" ("+str(m_id)+")"
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['material',  0, '/web' ], results=web_results, plus=['/api/1.1/material/'+m_id+'/web','no'],db=db, ext_flag=ext_flag, log=session['logged_in'], usrname=session.get('usrname', None), first_display='material')

@app.route('/api/1.1/material/<ext_flag>', methods=['GET'])
def get_material(ext_flag):
    scolumns=get_columns_from_table('material')
    columns=tuple([scolumns[1]])+tuple([scolumns[4]])+scolumns[2:4]+tuple([scolumns[9]])+tuple([scolumns[12]])+scolumns[13:14]+tuple(["samples"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct m.material_id, m.name, m.individual_id, m.accession, m.type, m.developmental_stage_id, \
        m.organism_part_id, count(distinct s.sample_id) FROM material m join sample s on s.material_id=m.material_id \
        where m.latest=1 and s.latest=1 group by m.material_id, m.name, m.individual_id, m.accession, m.developmental_stage_id, \
        m.type, m.organism_part_id")
        results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch materials")
    curs.close
    if len(results) == 0 :
        if ext_flag=='json':
            return jsonify({"Data error":"no material data available in the database '"+db+"'"})
        else:
            flash ("Error: no material data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        new_columns, display_results= change_for_display([columns], list(results), ext_flag)
        if ext_flag=='json':
            json_results=tuple_to_dic(new_columns[0], display_results, "materials")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all materials', url_param=['material',0, '/web'], results=[new_columns[0], display_results], plus=['all/web', 'yes'], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/material/all/<ext_flag>', methods=['GET'])
def get_material_all(ext_flag):
    scolumns=get_columns_from_table('material')
    columns=tuple([scolumns[1]])+tuple([scolumns[4]])+scolumns[2:4]+tuple([scolumns[12]])+scolumns[5:12]+scolumns[13:]+tuple(["samples"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct m.material_id, m.name, m.individual_id, m.accession, m.developmental_stage_id, m.provider_id, m.date_received, \
        m.storage_condition, m.storage_location, m.type, m.volume, m.concentration, m.organism_part_id, m.changed, m.latest, \
        count(distinct s.sample_id) FROM material m join sample s on s.material_id=m.material_id where s.latest=1 and m.latest=1 group by m.material_id, \
        m.name, m.individual_id, m.accession, m.developmental_stage_id, m.provider_id, m.date_received, m.storage_condition, m.storage_location, \
        m.type, m.volume, m.concentration, m.organism_part_id, m.changed, m.latest")
        results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch materials")
    curs.close
    if len(results) == 0 :
        if ext_flag=='json':
            return jsonify({"Data error":"no material data available in the database '"+db+"'"})
        else:
            flash ("Error: no material data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        new_columns, display_results= change_for_display([columns], list(results), ext_flag)
        if ext_flag=='json':
            json_results=tuple_to_dic(new_columns[0], display_results, "materials")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all materials', url_param=['material',0, '/web'], results=[new_columns[0], display_results], plus=['/api/1.1/material/web','no'], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/project/<p_id>/<ext_flag>', methods=['GET'])
def get_project_per_project_id(p_id, ext_flag):
    pcolumns=get_columns_from_table('project')
    icolumns=['row_id', 'individual_id', 'name', 'alias', 'species_id', 'sex', 'location_id']
    mcolumns=['row_id', 'material_id', 'individual_id', 'name', 'date_received', 'type', 'developmental_stage_id', 'organism_part_id', 'sample(s)']
    scolumns=['row_id', 'sample_id', 'material_id', 'accession', 'ssid', 'name','file(s)']
    fcolumns=['row_id', 'file_id', 'lane_id', 'name', 'format', 'type', 'md5', 'nber_reads', 'total_length', 'average_length']
    curs = mysql.connection.cursor()
    project_results={}
    try:
        curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id \
        where p.project_id ='%s'" % p_id)
        presults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch project data")
    try:
        curs.execute("select distinct i.row_id, i.individual_id, i.name, i.alias, i.species_id, i.sex, i.location_id FROM individual i left join allocation a on a.individual_id=i.individual_id \
        left join project p on a.project_id=p.project_id where i.latest=1 and p.project_id ='%s'" % p_id)
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individual data")
    try:
        curs.execute("select distinct m.row_id, m.material_id, m.individual_id, m.name, m.date_received, m.type, \
        m.developmental_stage_id, m.organism_part_id, count(s.sample_id) FROM material m left join sample s on m.material_id=s.material_id \
        where m.latest=1 and m.individual_id in (select i.individual_id from individual i left join allocation a on \
        a.individual_id=i.individual_id left join project p on a.project_id=p.project_id where m.latest=1 and i.latest=1 \
        and p.project_id ='%s') group by m.row_id, m.material_id, m.individual_id, m.name, m.date_received, m.type, \
        m.developmental_stage_id, m.organism_part_id" % p_id)
        mresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch material data")
    try:
        curs.execute("select distinct s.row_id, s.sample_id, s.material_id, s.accession, s.ssid, s.name, count(f.file_id)  \
        FROM sample s join material m on m.material_id = s.material_id left join lane l on l.sample_id=s.sample_id left \
        join file f on f.lane_id = l.lane_id where m.individual_id in (select i.individual_id from individual i left \
        join allocation a on a.individual_id=i.individual_id left join project p on a.project_id=p.project_id where \
        m.latest=1 and s.latest=1 and i.latest=1 and p.project_id ='%s') group by s.row_id, s.sample_id, s.material_id, \
        s.accession, s.ssid, s.name" % p_id)
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch sample data")
    try:
        curs.execute("select distinct f.row_id, f.file_id, f.lane_id, f.name, f.format, f.type, f.md5, f.nber_reads, \
        f.total_length, f.average_length FROM file f left join lane l on l.lane_id=f.lane_id left join sample s on \
        s.sample_id =l.sample_id left join material m on m.material_id = s.material_id where \
        m.individual_id in (select i.individual_id from individual i left join allocation a on a.individual_id=i.individual_id \
        left join project p on a.project_id=p.project_id where i.latest=1 and m.latest=1 and s.latest=1 and l.latest=1 and f.latest=1 and p.project_id ='%s')" % p_id)
        fresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch file data")
    curs.close()
    table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
    project_results[p_id]=table_dic
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(project_results, col_dic, ext_flag, "project")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        for_display="project name (project_id)= "+presults[0][1]+" ("+p_id+")"
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['project',  0, '/web' ], results=web_results, plus=['/api/1.1/project/'+p_id+'/all/web','yes'], db=db, ext_flag=ext_flag, log=session['logged_in'], usrname=session.get('usrname', None), first_display='project')

@app.route('/api/1.1/project/<p_id>/all/<ext_flag>', methods=['GET'])
def get_project_per_project_id_all(p_id, ext_flag):
    pcolumns=get_columns_from_table('project')
    icolumns=get_columns_from_table('individual')
    mcolumns=get_columns_from_table('material')+tuple(['sample(s)'])
    scolumns=get_columns_from_table('sample') +tuple(['file(s)'])
    fcolumns=get_columns_from_table('file')
    curs = mysql.connection.cursor()
    project_results={}
    try:
        curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id \
        where p.project_id ='%s'" % p_id)
        presults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch project data")
    try:
        curs.execute("select distinct i.* FROM individual i left join allocation a on a.individual_id=i.individual_id \
        left join project p on a.project_id=p.project_id where i.latest=1 and p.project_id ='%s'" % p_id)
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individual data")
    try:
        curs.execute("select distinct m.*, count(s.sample_id) FROM material m left join sample s on s.material_id=m.material_id \
        where m.latest=1 and m.individual_id in (select i.individual_id from individual i left join allocation a on \
        a.individual_id=i.individual_id left join project p on a.project_id=p.project_id where i.latest=1 and p.project_id ='%s') \
        group by m.row_id" % p_id)
        mresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch material data")
    try:
        curs.execute("select distinct s.*, count(f.file_id) FROM sample s join material m on m.material_id = s.material_id left join lane l on l.sample_id=s.sample_id left join file f on f.lane_id=l.lane_id where s.latest=1 and \
        m.individual_id in (select i.individual_id from individual i left join allocation a on a.individual_id=i.individual_id \
        left join project p on a.project_id=p.project_id where i.latest=1 and p.project_id ='%s') group by s.row_id" % p_id)
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch sample data")
    try:
        curs.execute("select distinct f.* FROM file f left join lane l on l.lane_id=f.lane_id left join sample s on \
        s.sample_id =l.sample_id left join material m on m.material_id = s.material_id where m.latest=1 and s.latest=1 and l.latest=1 and f.latest=1 and \
        m.individual_id in (select i.individual_id from individual i left join allocation a on a.individual_id=i.individual_id \
        left join project p on a.project_id=p.project_id where i.latest=1 and p.project_id ='%s')" % p_id)
        fresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch file data")
    curs.close()
    table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
    project_results[p_id]=table_dic
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(project_results, col_dic, ext_flag, "project")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        for_display="project name (project_id)= "+presults[0][1]+" ("+p_id+")"
        session['criteria']=for_display
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['project',  0, '/web' ], results=web_results, plus=['/api/1.1/project/'+p_id+'/web','no'], db=db, log=session['logged_in'], usrname=session.get('usrname', None), first_display='project')

@app.route('/api/1.1/project/name/<accession>/<ext_flag>', methods=['GET'])
def get_project_per_accession(accession, ext_flag):
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct project_id FROM project WHERE accession = '%s';" % accession)
        results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(results) == 0:
        if ext_flag=='json':
            return jsonify({"Data error":"no project associated with criteria provided"})
        else:
            flash ("Error: no project associated with criteria provided")
            return redirect(url_for('index'))
    else:
        if ext_flag=='json':
            return get_project_per_project_id(p_id=results[0][0], ext_flag=ext_flag)
        else:
            return(redirect(url_for('get_project_per_project_id', p_id=results[0][0], ext_flag=ext_flag)))

@app.route('/api/1.1/project/name/<accession>/individual/name/<ind_name>/<ext_flag>', methods=['GET'])
def get_individual_per_project_accession_and_name(accession, ind_name, ext_flag):
    result=[]
    ind_list=ind_name.replace(" ","").replace(",", "','")
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        query=("SELECT individual_id FROM individual WHERE individual_id in (select individual_id from allocation a join project p \
        where p.project_id  = a.project_id and p.accession = '{acc}') and (individual.name in ('{i_list}') or individual.alias in ('{i_list}')) and latest=1;". format(acc=accession, i_list=ind_list))
        curs.execute(query)
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(iresults) > 0:
        results="("+",".join([str(x[0]) for x in iresults])+")"
        return(redirect(url_for('get_individual_per_individual_id', i_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'project accession=' +accession+' and individual name='+ind_name:'No data available'})
        else:
            flash ("no individual associated with the criteria provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/project/name/<accession>/location/name/<location>/<ext_flag>', methods=['GET'])
def get_project_per_accession_and_location(accession, location, ext_flag):
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.individual_id FROM individual i join location l on l.location_id = i.location_id \
        join species s on s.species_id = i.species_id \
        left outer join allocation a on a.individual_id=i.individual_id \
        left outer join project p on p.project_id=a.project_id \
        where i.latest=1 and l.location = '{reg}' and p.accession = '{acc}'". format(reg=location, acc=accession))
        presults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location and / or project accession")
    curs.close()
    if len(presults) > 0:
        results="("+",".join([str(x[0]) for x in presults])+")"
        return(redirect(url_for('get_individual_per_individual_id', i_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'project accession=' +accession+' and location name='+location:'No data available'})
        else:
            flash ("no individual associated with the criteria provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/project/name/<accession>/sample/name/<sname>/<ext_flag>', methods=['GET'])
def get_samples_by_sample_name_and_project(sname, accession, ext_flag):
    s_list="('"+sname.replace(" ","").replace(",", "','")+"')"
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.sample_id from sample s join material m on m.material_id = s.material_id join individual i \
    on i.individual_id=m.individual_id left join allocation a on a.individual_id=i.individual_id join project p \
    on p.project_id=a.project_id where s.latest=1 and (s.accession in {s_list} or s.name in {s_list}) \
    and p.accession='{acc}';".format(acc=accession, s_list=s_list))
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples with these criteria")
    curs.close()
    if len(sresults) > 0:
        results="("+",".join([str(x[0]) for x in sresults])+")"
        return(redirect(url_for('get_sample_per_sample_id', s_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'project accession=' +accession+' and sample name='+sname:'No data available'})
        else:
            flash ("no project associated with the criteria provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/project/name/<accession>/species/name/<sp_name>/<ext_flag>', methods=['GET'])
def get_individual_per_project_accession_and_species(accession, sp_name, ext_flag):
    results=()
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct individual_id FROM individual WHERE individual_id in (select individual_id from allocation a join project p \
        where p.project_id  = a.project_id and p.accession = '{acc}') and species_id in (select species_id from species where \
         name like '%%{spn}%%' or common_name like '%%{spn}%%') and latest=1;". format(acc=accession, spn=sp_name))
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(iresults) > 0:
        results="("+",".join([str(x[0]) for x in iresults])+")"
        return(redirect(url_for('get_individual_per_individual_id', i_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'project accession=' +accession+' and species name='+sp_name:'No data available'})
        else:
            flash ("no project associated with the criteria provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/project/<ext_flag>', methods=['GET'])
def get_projects(ext_flag):
    columns=get_columns_from_table('project')
    curs = mysql.connection.cursor()
    try:
        curs.execute("select p.project_id, p.name, p.alias, p.accession, p.ssid, count(distinct species_id), count(distinct a.individual_id) from project p \
        JOIN allocation a on p.project_id=a.project_id join individual i on i.individual_id=a.individual_id where i.latest=1 group by p.project_id, p.name, \
        p.alias, p.accession, p.ssid")
        presults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch projects")
    curs.close()
    if len(presults) == 0 :
        if ext_flag=='json':
            return jsonify({"Data error":"no project data available in the database '"+db+"'"})
        else:
            flash ("Error: no project data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        results=[columns+tuple(['species', 'individuals']),presults]
        if ext_flag=='json':
            json_results=tuple_to_dic(columns+tuple(['species', 'individuals']), presults, "projects")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all projects', url_param=['project', 0, '/web'], results=results, plus=['',''], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/provider/<p_id>/<ext_flag>', methods=['GET'])
def get_individual_by_provider(p_id, ext_flag):
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.*, p.provider_name FROM individual i right join provider p on p.provider_id=i.provider_id where i.latest=1 and p.provider_id ='%s';" % p_id)
        results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individual")
    curs.close()
    if len(results) == 0:
        if ext_flag=='json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('index'))
    else:
        list_individual_id=",".join([str(x[1]) for x in results])
        session['criteria']="provider name (provider_id)= "+results[0][-1]+" ("+str(p_id)+")"
        return redirect(url_for('get_individual_per_individual_id', i_id="("+list_individual_id+")", ext_flag=ext_flag))

@app.route('/api/1.1/provider/<ext_flag>', methods=['GET'])
def get_provider(ext_flag):
    pcolumns=get_columns_from_table('provider')
    columns=pcolumns[:2]+tuple([pcolumns[4]])+tuple(["species", 'individuals'])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct p.provider_id, p.provider_name, p.affiliation, \
        count(distinct i.species_id), count(distinct i.individual_id) from provider p join individual i on i.provider_id=p.provider_id \
        where p.latest=1 and i.latest=1 group by p.provider_id, p.provider_name, p.affiliation")
        results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch provider")
    curs.close()
    if len(results) == 0 :
        if ext_flag=='json':
            return jsonify({"Data error":"no provider data available in the database '"+db+"'"})
        else:
            flash ("Error: no provider data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        if ext_flag=='json':
            json_results=tuple_to_dic(columns, results, "providers")
            return jsonify(webresults_to_dic(json_results))
        else:
            if session['logged_in']:
                return render_template("mysql.html", title='Query was: all providers', url_param=['provider', 0, '/web' ], results=[columns,results], plus=['all/web','yes'], db=db, log=session['logged_in'], usrname=session.get('usrname', None))
            else:
                flash ("You need to be logged on to see contact details")
                return render_template("mysql.html", title='Query was: all providers', url_param=['provider', 0, '/web' ], results=[columns,results], plus=['/api/1.1/provider/web','yes'], db=db, log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/provider/all/<ext_flag>', methods=['GET'])
def get_provider_all(ext_flag):
    pcolumns=get_columns_from_table('provider')
    columns=pcolumns+tuple(["individuals", 'species'])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct p.provider_id, p.provider_name, p.email, p.affiliation, p.address, p.phone, p.changed, p.latest, \
        count(distinct i.individual_id), count(distinct i.species_id) from provider p join individual i on i.provider_id=p.provider_id \
        where p.latest=1 and i.latest=1 group by p.provider_id, p.provider_name, p.email, p.affiliation, p.address, p.phone, p.changed, p.latest")
        results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch provider")
    curs.close()
    if len(results) == 0 :
        if ext_flag=='json':
            return jsonify({"Data error":"no provider data available in the database '"+db+"'"})
        else:
            flash ("Error: no provider data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        if ext_flag=='json':
            json_results=tuple_to_dic(columns, results, "providers")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all providers', url_param=['provider', 0 , '/web'], results=[columns,results], plus=['/api/1.1/provider/web','no'], db=db, log=1)

@app.route('/api/1.1/sample/<s_id>/<ext_flag>', methods=['GET'])
def get_sample_per_sample_id(s_id, ext_flag):
    pcolumns=get_columns_from_table('project')
    icolumns=['row_id', 'individual_id', 'name', 'alias', 'species_id', 'sex', 'location_id']
    mcolumns=['row_id', 'material_id', 'individual_id', 'name', 'date_received', 'type', 'developmental_stage_id', 'organism_part_id', 'sample(s)']
    scolumns=['row_id', 'sample_id', 'material_id', 'accession', 'ssid', 'name', 'file(s)']
    fcolumns=['row_id', 'file_id', 'lane_id', 'name', 'format', 'type', 'md5', 'nber_reads', 'total_length', 'average_length']
    if "(" in s_id:
          s_id=s_id[1:-1]
    list_s_id=s_id.split(',')
    list_s_name=[]
    curs = mysql.connection.cursor()
    sample_results={}
    for sample_id in list_s_id:
        try:
            curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id left join \
            individual i on i.individual_id=a.individual_id left join material m on m.individual_id = i.individual_id left join \
            sample s on s.material_id=m.material_id where i.latest=1 and m.latest=1 and s.latest=1 and s.sample_id = %s" % sample_id)
            presults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch project data")
        try:
            curs.execute("select distinct i.row_id, i.individual_id, i.name, i.alias, i.species_id, i.sex, i.location_id FROM individual i \
            join material m on m.individual_id = i.individual_id left join sample s on s.material_id=m.material_id \
            where i.latest=1 and m.latest=1 and s.sample_id and s.sample_id = %s" % sample_id)
            iresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch individual data")
        try:
            curs.execute("select distinct m.row_id, m.material_id, m.individual_id, m.name, m.date_received, m.type, \
            m.developmental_stage_id, m.organism_part_id, count(s.sample_id) FROM material m left join sample s \
            on s.material_id=m.material_id where m.latest = 1 and s.latest=1 and s.sample_id = %s group by m.row_id, m.material_id, m.individual_id, m.name, m.date_received, m.type, \
            m.developmental_stage_id, m.organism_part_id" % sample_id)
            mresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch material data")
        try:
            curs.execute("select distinct s.row_id, s.sample_id, s.material_id, s.accession, s.ssid, s.name, (select count(distinct f.file_id) \
            FROM file f left join lane l on l.lane_id=f.lane_id where l.sample_id = {sample_id}) from sample s where s.latest=1 and s.sample_id = {sample_id} \
            group by s.row_id, s.sample_id, s.material_id, s.accession, s.ssid, s.name" .format(sample_id=sample_id))
            sresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch sample data")
        if len(sresults) > 0: list_s_name.append(sresults[0][5])
        try:
            curs.execute("select distinct f.row_id, f.file_id, f.lane_id, f.name, f.format, f.type, f.md5, f.nber_reads, \
            f.total_length, f.average_length FROM file f left join lane l on l.lane_id=f.lane_id left join sample s on \
            s.sample_id =l.sample_id where s.latest=1 and l.latest=1 and f.latest =1 and s.sample_id = %s" % sample_id)
            fresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch file data")
        table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
        sample_results[sample_id]=table_dic
    curs.close()
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(sample_results, col_dic, ext_flag, "sample")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        for_display="sample name (sample_id)= "+", ".join(list_s_name)+" ("+s_id+")"
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['sample',  0, '/web' ], results=web_results, plus=['/api/1.1/sample/'+s_id+'/all/web','yes'],db=db, log=session['logged_in'], usrname=session.get('usrname', None), first_display='sample')

@app.route('/api/1.1/sample/<s_id>/all/<ext_flag>', methods=['GET'])
def get_sample_per_sample_id_all(s_id, ext_flag):
    pcolumns=get_columns_from_table('project')
    icolumns=get_columns_from_table('individual')
    mcolumns=get_columns_from_table('material')+tuple(['sample(s)'])
    scolumns=get_columns_from_table('sample')+tuple(['file(s)'])
    fcolumns=get_columns_from_table('file')
    if "(" in s_id:
          s_id=s_id[1:-1]
    list_s_id=s_id.split(',')
    list_s_name=[]
    curs = mysql.connection.cursor()
    sample_results={}
    for sample_id in list_s_id:
        try:
            curs.execute("select distinct p.* FROM project p join allocation a  on a.project_id=p.project_id left join \
            individual i on i.individual_id=a.individual_id left join material m on m.individual_id = i.individual_id left join \
            sample s on s.material_id=m.material_id where i.latest=1 and m.latest=1 and s.latest=1 and s.sample_id = %s" % sample_id)
            presults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table project from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch project data")
        try:
            curs.execute("select distinct i.* FROM individual i join material m on m.individual_id = i.individual_id left \
            join sample s on s.material_id=m.material_id where i.latest=1 and m.latest=1 and s.latest=1 and s.sample_id= %s" % sample_id)
            iresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table individual from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch individual data")
        try:
            curs.execute("select distinct m.*, count(s.sample_id) FROM material m left join sample s \
            on s.material_id=m.material_id where m.latest = 1 and s.latest=1 and s.sample_id = %s group by m.row_id" % sample_id)
            mresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table material from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch material data")
        try:
            curs.execute("select distinct s.*, (select count(f.file_id) FROM file f left join lane l on l.lane_id=f.lane_id \
            where l.sample_id = {sample_id}) from sample s where s.latest=1 and s.sample_id = {sample_id} \
            group by s.row_id" .format(sample_id=sample_id))
            sresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table sample from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch sample data")
        if len(sresults) > 0: list_s_name.append(sresults[0][5])
        try:
            curs.execute("select distinct f.* FROM file f left join lane l on l.lane_id=f.lane_id left join sample s on \
            s.sample_id =l.sample_id where l.latest=1 and f.latest =1 and s.latest=1 and s.sample_id = %s" % sample_id)
            fresults=curs.fetchall()
        except:
            if ext_flag=='json':
                return jsonify({"Connection error":"could not connect to table file from database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch file data")
        table_dic={'project':presults, 'individual': iresults, 'material': mresults, 'sample': sresults, 'file': fresults}
        sample_results[sample_id]=table_dic
    curs.close()
    col_dic={'project':pcolumns, 'individual': icolumns, 'material': mcolumns, 'sample': scolumns, 'file': fcolumns}
    json_results, web_results=generate_json_for_display(sample_results, col_dic, ext_flag, "sample")
    if ext_flag=='json':
        return jsonify(webresults_to_dic(json_results))
    else:
        for_display="sample name (sample_id)= "+", ".join(list_s_name)+" ("+s_id+")"
        return render_template("mysqltab.html", title='Query was: '+for_display, url_param=['sample',  0, '/web' ], results=web_results, plus=['/api/1.1/sample/'+s_id+'/web','no'],db=db, log=session['logged_in'], usrname=session.get('usrname', None), first_display='sample')

@app.route('/api/1.1/sample/name/<sname>/<ext_flag>', methods=['GET'])
def get_samples_by_name(sname, ext_flag):
    s_list=sname.replace(" ","").replace(",", "','")
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct sample_id FROM sample where latest=1 and name in ('{slist}') or accession in ('{slist}');".format(slist=s_list))
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples")
    curs.close()
    if len(sresults) == 0:
        if ext_flag=='json':
            return jsonify({"Data error":"no sample associated with criteria provided"})
        else:
            flash ("Error: no sample associated with criteria provided")
            return redirect(url_for('index'))
    else:
        list_sample_id=",".join([str(x[0]) for x in sresults])
        if ext_flag=='json':
            return get_sample_per_sample_id(s_id=list_sample_id, ext_flag=ext_flag)
        else:
            return(redirect(url_for('get_sample_per_sample_id', s_id=list_sample_id, ext_flag=ext_flag)))

@app.route('/api/1.1/sample/name/<sname>/individual/name/<ind_name>/<ext_flag>', methods=['GET'])
def get_samples_by_sample_name_and_individual_name(sname, ind_name, ext_flag):
    s_list="('"+sname.replace(" ","").replace(",", "','")+"')"
    ind_list=ind_name.replace(" ","").replace(",", "','")
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.sample_id from sample s join material m on m.material_id = s.material_id join individual i on i.individual_id=m.individual_id where s.latest=1 and (i.name in ('{ind_list}') \
         or i.alias in ('{ind_list}')) and (s.accession in {s_list} or s.name in {s_list});".format(ind_list=ind_list, s_list=s_list))
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples with these criteria")
    curs.close()
    if len(sresults) == 0:
        if ext_flag=='json':
            return jsonify({"Data error":"no sample associated with criteria provided"})
        else:
            flash ("Error: no sample associated with criteria provided")
            return redirect(url_for('index'))
    else:
        list_sample_id=",".join([str(x[0]) for x in sresults])
        if ext_flag=='json':
            return get_sample_per_sample_id(s_id=list_sample_id,ext_flag=ext_flag)
        else:
            return(redirect(url_for('get_sample_per_sample_id', s_id=list_sample_id, ext_flag=ext_flag)))

@app.route('/api/1.1/sample/<ext_flag>', methods=['GET'])
def get_samples(ext_flag):
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["individual_id"]+list(scolumns[3:4])+list(scolumns[6:]) +list(["files"]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.sample_id, s.material_id, s.accession, s.ssid, s.name, s.public_name, s.changed, s.latest, count(distinct f.file_id) \
         from sample s join lane l on l.sample_id=s.sample_id join file f on f.lane_id=l.lane_id where s.latest=1 and l.latest=1 and f.latest=1 group by \
         s.sample_id, s.material_id, s.accession, s.ssid, s.name, s.public_name, s.changed, s.latest")
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples")
    if len(sresults) == 0:
        curs.close()
        if ext_flag=='json':
            return jsonify({"Data error":"no sample data available in the database '"+db+"'"})
        else:
            flash ("Error: no sample data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        for row in sresults:
            try:
                curs.execute("SELECT distinct i.individual_id from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s' ;" % row[1])
                id_return=curs.fetchall()
            except:
                if ext_flag=='json':
                    return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
                else:
                    flash ("Error: unable to fetch items")
            id_results=[row[0]]+[row[4]]+[id_return[0][0]]+list(row[2:3])+list(row[5:])
            results.append(tuple(id_results))
        curs.close()
        new_columns, display_results= change_for_display([columns], results, ext_flag)
        if ext_flag=='json':
            json_results=tuple_to_dic(tuple(new_columns[0]), display_results, "samples")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all samples', url_param=['sample', 0, '/web'], results=[new_columns[0],display_results], plus=['',''], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/species/<sp_id>/<ext_flag>', methods=['GET'])
def get_species_per_species_id(sp_id, ext_flag):
    columns=get_columns_from_table('individual')[1:8]
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.individual_id, s.name FROM individual i join species s on \
        s.species_id=i.species_id where i.latest=1 and i.species_id = %s;" % sp_id)
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
            return redirect(url_for('index'))
    curs.close
    if len(sresults) == 0:
        if ext_flag=='json':
            return jsonify({"Data error":"no species associated with criteria provided"})
        else:
            flash ("Error: no species associated with criteria provided")
            return redirect(url_for('index'))
    else:
        list_individual_id=", ".join([str(x[0]) for x in sresults])
        session['criteria']="species name (species_id)= "+sresults[0][-1]+" ("+str(sp_id)+")"
        return redirect(url_for('get_individual_per_individual_id', i_id="("+list_individual_id+")", ext_flag=ext_flag))

@app.route('/api/1.1/species/<ext_flag>', methods=['GET'])
def get_species(ext_flag):
    scolumns=get_columns_from_table('species')
    columns=scolumns[1:6]+tuple([scolumns[9]])+tuple(["individuals"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.species_id, s.name, s.strain, s.taxon_id, s.common_name, s.taxon_position, count(distinct i.individual_id) \
        from species s join individual i on i.species_id=s.species_id  where s.latest=1 and i.latest=1 group by s.species_id, s.name, s.strain, \
        s.taxon_id, s.common_name, s.taxon_position")
        results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch species")
            return redirect(url_for('index'))
    curs.close()
    if len(results) == 0 :
        if ext_flag=='json':
            return jsonify({"Data error":"no species data available in the database '"+db+"'"})
        else:
            flash ("Error: no species data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        new_columns, display_results= change_for_display(list([columns]), list(results), ext_flag)
        if ext_flag=='json':
            json_results=tuple_to_dic(tuple(new_columns[0]), display_results, "species")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all species', url_param=['species',0, '/web'], results=[new_columns[0], display_results], plus=['all/web', 'yes'], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/species/all/<ext_flag>', methods=['GET'])
def get_species_all(ext_flag):
    scolumns=get_columns_from_table('species')
    columns=scolumns[1:]+tuple(["individuals"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.species_id, s.name, s.strain, s.taxon_id, s.common_name, \
        s.karyotype, s.ploidy, s.family_id, s.taxon_position, s.genome_size, s.iucn, s.changed, s.latest, \
        count(distinct i.individual_id) from species s join individual i on i.species_id=s.species_id \
        where s.latest=1 and i.latest=1 group by s.species_id, s.name, s.strain, s.taxon_id, s.common_name, \
        s.karyotype, s.ploidy, s.family_id, s.taxon_position, s.genome_size, s.iucn, s.changed, s.latest")
        results=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch species")
            return redirect(url_for('index'))
    curs.close()
    if len(results) == 0 :
        if ext_flag=='json':
            return jsonify({"Data error":"no species data available in the database '"+db+"'"})
        else:
            flash ("Error: no species data available in the database '"+db+"'")
            return redirect(url_for('index'))
    else:
        new_columns, display_results= change_for_display(list([columns]), list(results), ext_flag)
        if ext_flag=='json':
            json_results=tuple_to_dic(tuple(new_columns[0]), display_results, "species")
            return jsonify(webresults_to_dic(json_results))
        else:
            return render_template("mysql.html", title='Query was: all species', url_param=['species',0, '/web'], results=[new_columns[0], display_results], plus=['/api/1.1/species/web','no'], db=db,  log=session['logged_in'], usrname=session.get('usrname', None))

@app.route('/api/1.1/species/name/<sp_name>/<ext_flag>', methods=['GET'])
def get_species_per_name(sp_name, ext_flag):
    list_species_id=""
    scolumns=get_columns_from_table('species')
    columns=scolumns[1:6]+scolumns[9:]+tuple(["individuals"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct i.individual_id, s.species_id from species s left join individual i on s.species_id = i.species_id where s.latest=1 \
        and (s.name like '%{spn}%' or s.common_name like '%{spn}%')".format(spn=sp_name))
        spresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch species")
            return redirect(url_for('index'))
    curs.close()
    if len(spresults) > 0:
        results="("+",".join([str(x[0]) for x in spresults])+")"
        session['criteria']='species name (species_id)='+sp_name +" ("+str(spresults[0][-1])+")"
        return(redirect(url_for('get_individual_per_individual_id', i_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'species_name='+sp_name:'No data available'})
        else:
            flash ("no species associated with the name provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/species/name/<sp_name>/individual/name/<ind_name>/<ext_flag>', methods=['GET'])
def get_individual_per_name_and_species_name(ind_name, sp_name, ext_flag):
    ind_list=ind_name.replace(" ","").replace(",", "','")
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.individual_id FROM individual i join species s on i.species_id=s.species_id WHERE i.latest=1 and (s.name like '%%{spn}%%' or s.common_name like '%%{spn}%%') and (i.name in ('{i_l}') or i.alias in ('{i_l}'));". format(spn=sp_name, i_l=ind_list))
        iresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(iresults) > 0:
        results="("+",".join([str(x[0]) for x in iresults])+")"
        return(redirect(url_for('get_individual_per_individual_id', i_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'species name=' +sp_name+' and individual name='+ind_name:'No data available'})
        else:
            flash ("no species associated with the name provided")
            return redirect(url_for('index'))

@app.route('/api/1.1/species/name/<sp_name>/sample/name/<sname>/<ext_flag>', methods=['GET'])
def get_samples_by_sample_name_and_species(sname, sp_name, ext_flag):
    s_list="('"+sname.replace(" ","").replace(",", "','")+"')"
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.sample_id from sample s join material m on m.material_id = s.material_id join individual i \
        on i.individual_id=m.individual_id left join species sp on sp.species_id=i.species_id where s.latest=1 \
        and (s.accession in {s_list} or s.name in {s_list}) and (sp.name like '%{spn}%' or sp.common_name like '%{spn}%');".format(spn=sp_name, s_list=s_list))
        sresults=curs.fetchall()
    except:
        if ext_flag=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples with these criteria")
    curs.close()
    if len(sresults) > 0:
        results="("+",".join([str(x[0]) for x in sresults])+")"
        return(redirect(url_for('get_sample_per_sample_id', s_id=results, ext_flag=ext_flag)))
    else:
        if ext_flag=='json':
            return jsonify({'species name=' +sp_name+' and sample name='+sname:'No data available'})
        else:
            flash ("no sample associated with the criteria provided")
            return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)
