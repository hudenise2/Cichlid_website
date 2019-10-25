#!/Library/Frameworks/Python.framework/Versions/3.7/bin/python3
 #/usr/bin/python3 for web version
from flask import Flask, render_template, request,  flash, redirect, url_for, session, send_file, jsonify
from flask_mysqldb import MySQL
from flask_migrate import Migrate
from flask_login import UserMixin, login_user, logout_user, current_user, login_required, LoginManager
from wtforms import Form, BooleanField, TextField, PasswordField, validators
import hashlib
from MySQLdb import escape_string as thwart
import gc, json
import os, binascii
from flask_mail import Message, Mail
from forms import LoginForm, RegistrationForm, EntryForm, EnterDataForm, DatabaseForm
from config import Config
app = Flask(__name__)

'''
    Website script written by H. Denise (Cambridge Uni) 6/08/2019
    Script still in progress with optimisation and code clean-up to be carried out
    Also upload of data need to be fully implemented
'''
#initialisation of connection
config_file_path='./Cichlid_dbV4.json'       # for web version: '/www/hd2/www-dev/other-sites/darwin-tracking.sanger.ac.uk/cichlidV4-app/Cichlid_dbV4.json'
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
            if json=='json':
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
            if json=='json':
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

def change_for_display(col, data):
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
     'seq_tech':'name', 'species':'name', 'tax_order':'name'}
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
                    curs.execute("SELECT "+table_dic[table_name_dic[dic_index]]+ " FROM "+table_name_dic[dic_index]+" WHERE "+table_name_dic[dic_index]+"_id = '{id}';". format(id=row[dic_index]))
                    results=curs.fetchall()
                    #location and cv queries returned several fields, the other tables will return a single field
                    if table_name_dic[dic_index] in ('location', 'cv'):
                        row[dic_index]=results[0]
                    else:
                        row[dic_index]=results[0][0]
                except:
                    if json=='json':
                        return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
                    else:
                        flash ("Error: unable to fetch items: "+"SELECT "+table_dic[table_name_dic[dic_index]]+ " FROM "+table_name_dic[dic_index]+" WHERE "+table_name_dic[dic_index]+"_id = '{id}';". format(id=row[dic_index]))
                curs.close()
        #section to add data in correct field when several fields are returned
        #if 'cv_attribute' field in column (can have multiple entries):
        for field_index in range(1, len(column)):
            if column[field_index] == 'cv_attribute':
                if row[field_index] is None:
                    row.insert(field_index+1, None)
                else:
                    row.insert(field_index+1, row[field_index][1])
                    row[field_index] = row[field_index][0]
        #if location field (country of origin) in column:
        if 'country_of_origin' in column:
            if row[column.index('country_of_origin')] is None:
                for idx in range(1,5):
                    row.insert(column.index('country_of_origin')+idx, '')
            else:
                for idx in range(1,5):
                    row.insert(column.index('country_of_origin')+idx, str(row[column.index('country_of_origin')][idx]))
                row[column.index('country_of_origin')]= str(row[column.index('country_of_origin')][0])
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
            if image_results:
                #create path to image file
                row.append("/".join(list(image_results[0])))
            else:
                row.append('')
            if 'thumbnail' not in column:
                column.append('thumbnail')
        #get the updated columns and data in a list
        list_new_data.append(row)
        list_new_columns.append(column)
        #if there is more than one entry for an individual, order by latest and reverse date
        if column[0]=='individual_id' and len(column) > 13:
            list_new_data = reorder_for_vertical_display(list_new_data)
    return tuple(list_new_columns), tuple(list_new_data)

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
        if json=='json':
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
    if column_idx == 1:
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

def tuple_to_dic(col, data):
    new_list=[]
    for index in range(0, len(data)):
        new_dic={}
        for column_index in range(0, len(col)):
            new_dic[col[column_index]]=data[index][column_index]
        new_list.append(new_dic)
    return new_list
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
@app.route('/<db>', methods=['GET', 'POST'])
def db_index(db):
    """main function for the main page where user can choose the way to interrogate the database"""
    individual_name=""
    list_proj=[]
    list_loc =[]
    json="web"
    if 'usrname' not in session:
        session['usrname']=""
    session['name']=""
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT accession, name FROM project")
        prows=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch projects")
    try:
        curs.execute("SELECT distinct location FROM location where location is not NULL")
        lrows=curs.fetchall()
    except:
        if json=='json':
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
            return redirect(url_for('db_index', db=db))
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
            return redirect(url_for(url_dic[flag], accession=arg_dic[flag], db=db, json=json))
        elif flag == 'AI':
            return redirect(url_for(url_dic[flag], accession=arg_dic[flag][0], ind_name=arg_dic[flag][1], db=db, json=json))
        elif flag == 'AS':
                return redirect(url_for(url_dic[flag], accession=arg_dic[flag][0], sp_name=arg_dic[flag][1], db=db, json=json))
        elif flag=='I':
            session['breadcrumbs']=[[url_for('db_index', db=db), db]]
            session['query']=[url_for('get_individual_per_individual_name', ind_name=individual_name, db=db, json=json), 'individual']
            return redirect(url_for(url_dic[flag], ind_name= individual_name, db=db, json=json))
        elif flag=='IS':
            return redirect(url_for(url_dic[flag], ind_name= individual_name, sp_name=arg_dic[flag][1], db=db, json=json))
        elif flag=='S':
            return redirect(url_for(url_dic[flag], sp_name=species_name, db=db, json=json))
        elif flag =='L':
            return redirect(url_for(url_dic[flag], location=loc_region, db=db, json=json))
        elif flag =='SL':
            return redirect(url_for(url_dic[flag], location=arg_dic[flag][1], sp_name=arg_dic[flag][0], db=db, json=json))
        elif flag =='IL':
            session['breadcrumbs']=[[url_for('db_index', db=db), db]]
            session['query']=[url_for('get_individual_per_location', location=loc_region, db=db, json=json), 'individual']
            return redirect(url_for(url_dic[flag], location=arg_dic[flag][1], ind_name=arg_dic[flag][0], db=db, json=json))
        elif flag =='AL':
            return redirect(url_for(url_dic[flag], location=arg_dic[flag][1], accession=arg_dic[flag][0], db=db, json=json))
        elif flag =='X':
            return redirect(url_for(url_dic[flag], sname=sample_name, db=db, json=json))
        elif flag =='XL':
            return redirect(url_for(url_dic[flag], sname=sample_name, location=loc_region, db=db, json=json))
        elif flag =='IX':
            return redirect(url_for(url_dic[flag], sname=sample_name, ind_name=individual_name, db=db, json=json))
        elif flag =='SX':
            return redirect(url_for(url_dic[flag], sname=sample_name, sp_name=species_name, db=db, json=json))
        elif flag =='AX':
            return redirect(url_for(url_dic[flag], sname=sample_name, accession=arg_dic[flag][-1], db=db, json=json))
        else:
            return redirect(url_for('db_index', db=db))
            flash("Please enter valid criteria")
    return render_template("entry.html", title='Query was: returnall', form=form, project_list=tuple(list_proj), loc_list=tuple(list_loc), db=db, json=json)

@app.route('/<db>/api/1.1/entry', methods=['GET', 'POST'])
def enter_data(db):
    """function for the entry page where user can update, overwrite or enter new data in the database"""
    usrname=session.get('usrname', None)
    form = EnterDataForm(request.form)
    provider_list=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct provider_name FROM provider")
        provider_res=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch provider names")
    curs.close()
    for prov in provider_res:
        provider_list.append(prov[0])
    provider_list.append("-current providers-")
    if request.method == "POST" and form.validate():
        results=request.form
        if 'Download' in results:
            return redirect(url_for('download', db=db))
        elif 'Upload' in results:
            return redirect(url_for('upload', file = results['Upload'], db=db))
        else:
            flash("your data have been submitted successfully")
            return redirect(url_for('enter_data', db=db))
    return render_template('enter_data.html', title='Signed in as: '+usrname, form=form, prov_list=tuple(provider_list), db=db, session=session)

@app.route('/')
@app.route('/index', methods=['GET', 'POST'])
def index():
    """main function for the main page where user can choose which database to interrogate"""
    project_acc=""
    individual_name=""
    flag=""
    list_proj=[]
    list_loc =[]
    if 'usrname' not in session:
        session['usrname']=""
    list_db = ['CICHLID_TRACKINGV4','DARWIN_TRACKINGV1','-- select --']
    form=DatabaseForm()
    if form.validate_on_submit():
        details=request.form
        if details['db_choice'][:2]=='--':
            flash("Please select a database")
            return redirect(url_for('index'))
        elif details['db_choice']=='DARWIN_TRACKINGV1':
            config_file_path="./Darwin_dbV1.json"
            db='darwin'
        elif details['db_choice']=='CICHLID_TRACKINGV4':
            config_file_path="./Cichlid_dbV4.json"
            db='cichlid'
        # for web version: '/www/hd2/www-dev/other-sites/darwin-tracking.sanger.ac.uk/cichlidV4-app/XXXXXXX.json'
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
        app.config.update()
        session['query']=[]
        return redirect(url_for('db_index', db=db))
    return render_template("entry2.html", title='Query was: returnall', form=form, db_list=tuple(list_db))

@app.route('/<db>/login', methods=['GET', 'POST'])
def login(db):
    """function to ensure that only authorized people can log in"""
    rows=""
    if current_user.is_authenticated:
        return redirect(url_for('db_index', db=db))
    form = LoginForm()
    if form.validate_on_submit():
        details=request.form
        curs = mysql.connection.cursor()
        try:
            curs.execute("SELECT * FROM users where username ='%s';" % details['username'])
            rows=curs.fetchall()
        except:
            if json=='json':
                return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch items")
        curs.close()
        if len(rows) == 0:#if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login', db=db))
        else :
            compare = verify_password(rows[0][3], details['password'])
            if compare:
                session['usrname']=rows[0][1]
                session['logged_in']=True
                return redirect(url_for('enter_data', db=db))
            else:
                flash('Invalid password provided')
                return redirect(url_for('login', db=db))
    return render_template('login.html', title='Sign In', form=form, db=db)

@app.route('/<db>/logout')
def logout(db):
    """function to logout"""
    logout_user()
    session={}
    crumbs=[[url_for('db_index', db=db), db]]
    session['breadcrumbs'] = crumbs
    return redirect(url_for('db_index', db=db))

@app.route('/<db>/register', methods=['GET', 'POST'])
def register(db):
    """function for the main page where user can choose the way to interrogate the database"""
    try:
        form = RegistrationForm(request.form)
        if request.method == "POST" and form.validate():
            username  = form.username.data
            email = form.email.data
            password=form.password.data
            password2=form.password2.data
            if db=='cichlid':
                email_list=('had38@cam.ac.uk','sam68@cam.ac.uk','sm15@sanger.ac.uk', 'tylerp.linderoth@gmail.com','ib400@cam.ac.uk','bef22@hermes.cam.ac.uk','rd109@cam.ac.uk','rd@sanger.ac.uk', 'gv268@cam.ac.uk', 'es754@cam.ac.uk', 'hs10@sanger.ac.uk')
            elif db=='darwin':
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
                        return redirect(url_for('login', db=db))
                    else:
                        msg = Message(body='username: '+username+'\nemail: '+email+'\npassword: '+password, subject = 'New registration', sender ='had38@cam.ac.uk', recipients = ['had38@cam.ac.uk'])
                        mail.send(msg)
                        return redirect(url_for('db_index', db=db))
                        flash("Thanks for registering: your registration is now pending approval")
                    curs.close()
            else:
                flash("The passwords did not match, please try again")
                return render_template('register.html', form=form, db=db)
    except Exception as e:
        return("Issue: "+str(e))
    return render_template('register.html', title='Register', form=form, db=db)

@app.route('/<db>/api/1.1/download', methods=['GET', 'POST'])
def download(db):
    """function to provide the csv template to enter data"""
    return send_file("entry.csv",
        mimetype="text/csv",
        attachment_filename='entry.csv',
                     as_attachment=True)

@app.route('/<db>/api/1.1/upload/<file>', methods=['GET', 'POST'])
def upload(file, db):
    """function to reupload the filled csv template to add, update or overwrite the database"""
    f = open(file, 'r')
    #only keep lines with data
    File = [line.rstrip('\n') for line in f if len(line.split(",")[0]) > 0]
    flash ('file uploaded successfully')
    return redirect(url_for('db_index', db=db))

################### API RELATED FUNCTIONS ######################################
@app.route('/<db>/api/1.1/file/<la_id>/<json>', methods=['GET'])
def get_files_per_lane_id(la_id, db, json):
    results=[]
    file_columns=get_columns_from_table('file')
    columns=tuple([file_columns[1]]+[file_columns[3]]+[file_columns[2]]+list(file_columns[4:]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct f.*, l.accession FROM file f join lane l on f.lane_id=l.lane_id where f.latest=1 and f.lane_id = '%s';" % la_id)
        fresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch files")
    curs.close()
    if len(fresults) == 0:
        if json == 'json':
            return jsonify({"Data error":"no file associated with criteria provided"})
        else:
            flash ("Error: no file associated with criteria provided")
            return redirect(session['query'][0])
    else:
        for row in fresults:
            f_results=[row[1]]+[row[3]]+[row[2]]+list(row[4:])
            lane_accession=row[-1]
            results.append(f_results)
        new_column, display_results= change_for_display([columns], results)
        new_columns= list(new_column)
        new_columns[0][5]='file_type'
        v_display_results, split_col=transpose_table(new_columns, display_results)
        if json =='json':
            return jsonify(tuple_to_dic(new_columns[0], display_results))
        else:
            #to display navigation history
            crumbs=session.get('breadcrumbs', None)
            session['breadcrumbs'].append(session.get('query', None))
            list_crumbs=[x[-1] for x in crumbs]
            session['breadcrumbs'] = crumbs
            if 'file' in list_crumbs:
                session['query']=[]
            #for vertical display: view_param (field before which blank line will be inserted), results (data to display with field, data_file1, data_file2...), crumbs (to display navigation history))
            return render_template("mysqlV.html", title='Query was: file(s) where lane_accession = "' + str(lane_accession)+'"', view_param=split_col, results=[v_display_results], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/image/<im_id>/<json>', methods=['GET'])
def get_image_per_image_id(im_id, db, json):
    results=[]
    columns=get_columns_from_table('image')
    col=[columns[0]]+[columns[2]]+[columns[1]]+['thumbnail']+list(columns[3:])
    columns=tuple(col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM image where latest=1 and image_id = '%s';" % im_id)
        img_results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch images")
    curs.close()
    if len(img_results) ==0:
        if json == 'json':
            return jsonify({"Data error":"no image associated with criteria provided"})
        else:
            flash ("Error: no image associated with criteria provided")
    else:
        for row in img_results:
            i_results=[row[0]]+[row[2]]+[row[1]]+list([row[3]+"/"+row[2]])+list(row[3:])
            results.append(i_results)
        new_column, display_results= change_for_display([columns], results)
        if json =='json':
            return jsonify(tuple_to_dic(new_column[0],display_results))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'individual' not in list_crumbs:
                session['breadcrumbs'].append(session.get('query', None))
            else:
                crumbs.pop()
            session['query']=[url_for('get_image_per_image_id', im_id=im_id, db=db, json=json), 'individual']
            #for image display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), plus ([0] to create link , [1] indicate no display), crumbs (to display navigation history))
            return render_template("image.html", title="Query was: file name (image_id) = '"+img_results[0][2] +"' ("+str(im_id) +")" , url_param=['individual/name', 2, '/web'], results=[new_column[0],display_results], plus=['', ''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/image/<json>', methods=['GET'])
def get_images(db, json):
    results=[]
    columns=get_columns_from_table('image')
    col=[columns[0]]+[columns[2]]+[columns[1]]+['thumbnail']+[columns[4]]
    columns=tuple(col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM image where latest=1")
        img_results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch images")
    curs.close()
    if len(img_results) ==0:
        if json == 'json':
            return jsonify({"Data error":"no image data available in the database '"+db+"'"})
        else:
            flash ("Error: no image data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    for row in img_results:
        i_results=[row[0]]+[row[2]]+[row[1]]+list([row[3]+"/"+row[2]])+[row[4]]
        results.append(tuple(i_results))
    new_column, display_results= change_for_display([columns], results)
    if json =='json':
        return get_images_all(db=db, json=json)
    else:
        crumbs=[[url_for('db_index', db=db), db]]
        session['breadcrumbs'] = crumbs
        session['query']=[url_for('get_images', db=db, json=json), 'image']
        #for image display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), plus ([0] to create link , [1] select if '+' or '-' is displayed)crumbs (to display navigation history))
        return render_template("image.html", title='Query was: all images', url_param=['image', 0, '/web'], results=[new_column[0],display_results], plus=['all/web', 'yes'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/image/all/<json>', methods=['GET'])
def get_images_all(db, json):
    results=[]
    columns=get_columns_from_table('image')
    col=[columns[0]]+[columns[2]]+[columns[1]]+['thumbnail']+list(columns[3:])
    columns=tuple(col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM image")
        img_results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch images")
    curs.close()
    if len(img_results)==0:
        if json == 'json':
            return jsonify({"Data error":"no image data available in the database '"+db+"'"})
        else:
            flash ("Error: no image data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        for row in img_results:
            i_results=[row[0]]+[row[2]]+[row[1]]+list([row[3]+"/"+row[2]])+list(row[3:])
            results.append(tuple(i_results))
        new_column, display_results= change_for_display([columns], results)
        if json =='json':
            return jsonify(tuple_to_dic(new_column[0],display_results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_images', db=db, json=json), 'image']
            #for image display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), plus ([0] to create link , [1] select if '+' or '-' is displayed), crumbs (to display navigation history))
            return render_template("image.html", title='Query was: all images', url_param=['image', 0, '/web'], results=[new_column[0],display_results], plus=['/'+db+'/api/1.1/image/web', 'no'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/individual/<i_id>/<json>', methods=['GET'])
def get_individual_per_individual_id(i_id, db, json):
    i_columns=get_columns_from_table('individual')
    id_columns=get_columns_from_table('individual_data')
    ind_name_dic={}
    all_results=[]
    all_columns=[]
    res_dic={}
    ind_id="("+i_id+")"
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.*, p.name, p.alias, p.accession, p.ssid FROM individual i left join allocation a \
        on a.individual_id=i.individual_id left join project p on p.project_id=a.project_id where i.individual_id in {identif} and i.latest=1;". format(identif=ind_id))
        i_results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
    curs.close()
    if len(i_results)==0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(session['query'][0])
    else:
        for index in range(0, len(i_results)):
            ind_name_dic[i_results[index][2]]=i_results[index][1]
            if i_results[index][0] in res_dic:
                res_dic[i_results[index][0]].append(i_results[index])
            else:
                res_dic[i_results[index][0]]=[i_results[index]]
        for entry in res_dic:
            columns, p_results=add_project_info(i_columns[1:7], res_dic[entry])
            new_column, sp_results=add_sample_info(columns, p_results)
            updated_columns, updated_results=add_individual_data_info(new_column, sp_results)
            all_columns.append(updated_columns+i_columns[7:])
            all_results.append(updated_results+res_dic[entry][0][7:16])
        display_columns, display_results = change_for_display(all_columns, list(all_results))
        v_display_results, split_col=transpose_table(display_columns, display_results)
        if json == "json":
            return jsonify(tuple_to_dic(display_columns[0], display_results))
        else:
            crumbs=session.get('breadcrumbs', None)
            if len(crumbs) >1:
                list_crumbs=[x[-1] for x in crumbs]
                if 'individual' in list_crumbs:
                    if 'location' in list_crumbs or 'project' in list_crumbs or 'species' in list_crumbs:#session['breadcrumbs'].append(session.get('query', None))
                        crumbs.pop()
                        session['breadcrumbs'].append(session.get('query', None))
            else:
                session['breadcrumbs'].append(session.get('query', None))
            for_display=str(ind_name_dic)[1:-1].replace(",", "),").replace(": ", " (")+")"
            #for vertical display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), crumbs (to display navigation history))
            return render_template("mysqlV.html", title='Query was: supplier_name (individual_id) = ' + for_display, view_param=split_col, results=[v_display_results], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/individual/name/<ind_name>/<json>', methods=['GET'])
def get_individual_per_individual_name(ind_name, db, json):
    ind_list=ind_name.replace(" ","").replace(",", "','")
    results=""
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.individual_id, im.image_id FROM individual i left join image im on i.individual_id=im.individual_id where i.name in ('{identif}') or i.alias in ('{identif}') ". format(identif=ind_list))
        i_results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
    curs.close()
    if len(i_results)==0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(session['query'][0])
    else:
        for row in i_results:
            results+=","+str(row[0])
        if json == 'json':
            return get_individual_per_individual_id(i_id=results[1:], db=db, json=json)
        else:
            crumbs=session.get('breadcrumbs', None)
            session['breadcrumbs'].append(session.get('query', None))
            return(redirect(url_for('get_individual_per_individual_id', i_id=results[1:], db=db, json=json)))

@app.route('/<db>/api/1.1/individual/<json>', methods=['GET'])
def get_individuals(db, json):
    icolumns=get_columns_from_table('individual')
    columns=list(icolumns[1:8]+tuple(['samples']))
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct i.individual_id, i.name, i.alias, i.species_id, i.sex, i.accession, i.location_id, \
        count(distinct s.sample_id) from individual i left join material m on m.individual_id=i.individual_id \
        left join sample s on s.material_id=m.material_id where i.latest=1 and s.latest=1 group by i.individual_id, i.name, \
        i.alias, i.species_id, i.sex, i.accession, i.location_id")
        iresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
    curs.close()
    if len(iresults)==0:
        if json == 'json':
            return jsonify({"Data error":"no individual data available in the database '"+db+"'"})
        else:
            flash ("Error: no individual data available in the database '"+db+"'")
            return redirect(session['query'][0])
    else:
        new_columns, results= change_for_display(list([tuple(columns)]), list(iresults))
        if json == 'json':
            return get_individuals_all(db=db, json=json)
        else:
            columns=new_columns[0][:-4]+new_columns[0][-2:-1]
            display_results=remove_column(remove_column(results, -3), -2)
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_individuals', db=db, json=json), 'individual']
            if session.get('html', None) =='image':
                return redirect(url_for('get_images', db=db, json=json))
            else:
                #for image display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), plus ([0] to create link , [1] select if '+' or '-' is displayed), crumbs (to display navigation history))
                return render_template("mysql.html", title='Query was: all individuals', url_param=['individual', 0, '/web'], results=[columns, remove_column(display_results, 'L')], plus=['all/web', 'yes'],db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/individual/all/<json>', methods=['GET'])
def get_individuals_all(db, json):
    icolumns=get_columns_from_table('individual')
    columns=list(icolumns[1:]+tuple(['samples']))
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct i.individual_id, i.name, i.alias, i.species_id, i.sex, i.accession, i.location_id, i.provider_id, \
        i.date_collected, i.collection_method, i.collection_details, i.father_id, i.mother_id, i.changed, i.latest, count(distinct s.sample_id) \
        from individual i left join material m on m.individual_id=i.individual_id left join sample s on s.material_id=m.material_id where \
        s.latest=1 group by i.individual_id, i.name, i.alias, i.species_id, i.sex, i.accession, i.location_id, i.provider_id,  \
        i.date_collected, i.collection_method, i.collection_details, i.father_id, i.mother_id, i.changed, i.latest")
        iresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
    curs.close()
    if len(iresults)==0:
        if json == 'json':
            return jsonify({"Data error":"no individual data available in the database '"+db+"'"})
        else:
            flash ("Error: no individual data available in the database '"+db+"'")
            return redirect(session['query'][0])
    else:
        new_columns, display_results= change_for_display(list([tuple(columns)]), list(iresults))
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_individuals', db=db, json=json), 'individual']
            if session.get('html', None) =='image':
                return redirect(url_for('get_images', db=db, json=json))
            else:
                #for classical display: url_param ([0]: to create link, [1]: identify field to use in link), results (data to display with field, data_file1, data_file2...), plus ([0] to create link , [1] select if '+' or '-' is displayed), crumbs (to display navigation history))
                return render_template("mysql.html", title='Query was: all individuals', url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['/'+db+'/api/1.1/individual/web', 'no'],db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/lane/<l_id>/<json>', methods=['GET'])
def get_lane_per_lane_id(l_id, db, json):
    results=[]
    lane_acc_dic={}
    lcolumns=get_columns_from_table('lane')
    columns=tuple([lcolumns[1]]+[lcolumns[7]]+[lcolumns[6]]+list(lcolumns[3:6])+list(lcolumns[8:]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct l.*, s.name FROM lane l join sample s on s.sample_id=l.sample_id where l.latest=1 and l.sample_id = '%s';" % l_id)
        lresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch lanes")
    curs.close()
    if len(lresults)==0:
        if json == 'json':
            return jsonify({"Data error":"no lane associated with criteria provided"})
        else:
            flash ("Error: no lane associated with criteria provided")
            return redirect(session['query'][0])
    else:
        for row in lresults:
            lane_acc_dic[row[7]]=row[1]
            l_results=[row[1]]+[row[7]]+[row[6]]+list(row[3:6])+list(row[8:-1])
            results.append(tuple(l_results))
        new_column, display_results= change_for_display([columns], results)
        new_columns= list(new_column)
        new_columns[0][5]='library_accession'
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0], display_results))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if len(session['query']) > 1:
                session['breadcrumbs'].append(session.get('query', None))
            if 'file' in list_crumbs:
                crumbs.pop()
            session['query']=[url_for('get_lane_per_lane_id', l_id=l_id, db=db, json=json), 'file']
            for_display='lane accession (lane_id) = '+str(lane_acc_dic)[1:-1].replace(",", "),").replace(": ", " (")+")"
            return render_template("mysql.html", title='Query was: lane(s) where ' +for_display, url_param=['file', 0, '/web'], results=[new_columns[0], display_results], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/lane/<json>', methods=['GET'])
def get_lanes(db, json):
    lcolumns=get_columns_from_table('lane')
    columns=tuple([lcolumns[1]])+tuple([lcolumns[6]])+tuple([lcolumns[2]])+tuple([lcolumns[3]]) +tuple([lcolumns[6]]) +tuple([lcolumns[7]]) + tuple(["files"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct l.lane_id,l.name,l.sample_id, l.seq_tech_id, l.library_id, l.accession, \
        count(distinct f.file_id) from lane l join file f on f.lane_id=l.lane_id where l.latest=1 and f.latest=1 group by l.lane_id,l.name,l.sample_id, \
        l.seq_tech_id, l.library_id, l.accession")
        lresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch lanes")
    curs.close()
    if len(lresults)==0:
        if json == 'json':
            return jsonify({"Data error":"no lane data available in the database '"+db+"'"})
        else:
            flash ("Error: no lane data available in the database '"+db+"'")
            return redirect(session['query'][0])
    else:
        new_column, display_results= change_for_display([columns], list(lresults))
        if json == 'json':
            return get_lanes_all(db=db, json=json)
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_lanes', db=db, json=json), 'lane']
            return render_template("mysql.html", title='Query was: all lanes', url_param=['lane', 0, '/web'], results=[new_column[0], display_results], plus =['all/web','yes'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/lane/all/<json>', methods=['GET'])
def get_lanes_all(db, json):
    lcolumns=get_columns_from_table('lane')
    columns=[lcolumns[1]]+[lcolumns[6]]+list(lcolumns[2:6]) + list(lcolumns[7:] +tuple(["files"]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct l.lane_id,l.name,l.sample_id, l.seq_tech_id, l.seq_centre_id, l.library_id, l.accession, l.ss_qc_status, l.auto_qc_status, l.manually_withdrawn, l.run_date, l.changed, l.latest, \
        count(distinct f.file_id) from lane l join file f on f.lane_id=l.lane_id where f.latest=1 group by l.lane_id,l.name,l.sample_id, l.seq_tech_id, \
        l.seq_centre_id, l.library_id, l.accession,l.ss_qc_status, l.auto_qc_status, l.manually_withdrawn, l.run_date, l.changed, l.latest")
        lresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch lanes")
    curs.close()
    if len(lresults)==0:
        if json == 'json':
            return jsonify({"Data error":"no lane data available in the database '"+db+"'"})
        else:
            flash ("Error: no lane data available in the database '"+db+"'")
            return redirect(session['query'][0])
    else:
        new_column, display_results= change_for_display([columns], lresults)
        if json =='json':
            return jsonify(tuple_to_dic(new_column[0], display_results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['query']=[url_for('get_lanes', db=db, json=json), 'lane']
            return render_template("mysql.html", title='Query was: all lanes', url_param=['lane', 0, '/web'], results=[new_column[0], display_results], plus=['/'+db+'/api/1.1/lane/web','no'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/location/<loc_id>/<json>', methods=['GET'])
def get_individual_per_location_id(loc_id, db, json):
    columns=get_columns_from_table('individual')[1:]
    results=[]
    list_loc_id ="("+loc_id+")"
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.*, l.location, l.sub_location FROM individual i join location l on i.location_id=l.location_id where l.location_id in %s and i.latest=1;" % list_loc_id)
        res=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
    curs.close()
    if len(res)==0:
        if json == 'json':
            return jsonify({"Data error":"no location associated with criteria provided"})
        else:
            flash ("Error: no location associated with criteria provided")
            return redirect(session['query'][0])
    else:
        l_results=remove_column(res, 1)
        for row in l_results:
            results.append(row[:15])
            if row[-2] is not None:
                loc_name=row[-2]
            elif row[-1] is not None:
                loc_name=row[-1]
            else:
                loc_name=""
        new_columns, display_results = change_for_display([columns[:15]], results)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'location' not in list_crumbs:
                session['breadcrumbs'].append(session.get('query', None))
                session['query']=[url_for('get_individual_per_location_id', loc_id=loc_id, db=db, json=json), 'individual']
            else:
                if len(crumbs)==1 or len(crumbs)==3:
                    crumbs.pop()
            if "," in list_loc_id:
                for_display = "location = '"+session['name']+"'"
            else:
                for_display = "location (location_id) = '" + str(loc_name) +"' ("+str(loc_id)+")"
            return render_template("mysql.html", title="Query was: individual(s) where "+ for_display, url_param=['location/'+str(loc_id)+'/individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus =['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/location/<loc_id>/individual/<ind_id>/<json>', methods=['GET'])
def get_individual_per_id_and_per_location_id(loc_id, ind_id, db, json):
    list_loc_id ="("+loc_id+")"
    loc_columns=get_columns_from_table('individual')
    columns=loc_columns[1:8]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct I.*, L.location FROM individual I join location L on L.location_id = I.location_id \
        join species S on S.species_id = I.species_id where L.location_id in {reg} and I.individual_id = '{indl}' ;". format(reg=list_loc_id, indl=ind_id))
        res=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location and / or individual")
    curs.close
    if len(res)==0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(session['query'][0])
    else:
        results=tuple([x[1:8] for x in list(res)])
        new_columns, display_results= change_for_display([columns], results)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'individual' not in list_crumbs:
                session['breadcrumbs'].append(session.get('query', None))
            else:
                crumbs.pop()
                session['breadcrumbs'].append([url_for('get_individual_per_location_id', loc_id=loc_id, db=db, json=json), 'individual'])
            session['query']=[url_for('get_individual_per_id_and_per_location_id', loc_id=loc_id, ind_id=ind_id, db=db, json=json), 'individual']
            if "," in list_loc_id:
                for_display="location name =  '"+res[0][-1] + "' and supplier_name (individual_id) = '"+res[0][2] +"' ("+str(ind_id)+")"
            else:
                for_display="location name (location_id) =  '"+res[0][-1] + "' ("+str(loc_id)+") and supplier_name (individual_id) = '"+res[0][2] +"' ("+str(ind_id)+")"
            return render_template("mysql.html", title='Query was: individual(s) where '+for_display, url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus =['.',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/location/name/<location>/<json>', methods=['GET'])
def get_individual_per_location(location, db, json):
    loc_columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct location_id from  location where location = '{loc}' or sub_location = '{loc}';". format(loc=location))
        res=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location")
    curs.close()
    if len(res)==0:
        if json == 'json':
            return jsonify({"Data error":"no location associated with criteria provided"})
        else:
            flash ("Error: no location associated with criteria provided")
            return redirect(session['query'][0])
    else:
        list_loc_id=",".join([str(x[0]) for x in res])
        if json=='json':
            return get_individual_per_location_id(loc_id=list_loc_id, db=db, json=json)
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            crumbs.append([url_for('get_location', db=db, json=json), 'location'])
            session['breadcrumbs']=crumbs
            session['query']=[url_for('get_individual_per_location', location=location, db=db, json=json), 'individual']
            if len(res) > 1: session['name']=location
            return(redirect(url_for('get_individual_per_location_id', loc_id=list_loc_id, db=db, json=json)))

@app.route('/<db>/api/1.1/location/name/<location>/individual/name/<ind_name>/<json>', methods=['GET'])
def get_individual_per_name_and_per_location(location, ind_name, db, json):
    loc_columns=get_columns_from_table('individual')
    columns=loc_columns[1:8]
    ind_list=ind_name.replace(" ","").replace(",", "','")
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct I.* FROM individual I join location L on L.location_id = I.location_id \
        join species S on S.species_id = I.species_id where L.location = '{reg}' and (I.name in ('{indl}') or I.alias in ('{indl}')) ;". format(reg=location, indl=ind_list))
        res=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location and / or individual")
    curs.close
    if len(res) == 0:
        if json=='json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        results=[x[1:8] for x in list(res)]
        new_columns, display_results= change_for_display([columns], results)
        if json == 'json':
            return jsonify(tuple_to_dic(tuple(new_columns[0][:-1]), remove_column(display_results, 'L')))
        else:
            crumbs=session.get('breadcrumbs', None)
            if len(crumbs) > 1:
                crumbs.pop()
            session['query']=[url_for('get_individual_per_name_and_per_location', location=location, ind_name=ind_name, db=db, json=json), 'individual']
            return render_template("mysql.html", title='Query was: individual(s) where location = "'+ location +'" and individual name = "'+ind_name+'"', url_param=['individual', 0, '/web'], results=[tuple(new_columns[0][:-1]), remove_column(display_results, 'L')], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/location/name/<location>/sample/name/<sname>/<json>', methods=['GET'])
def get_samples_by_sample_name_and_location(sname, location, db, json):
    s_list="('"+sname.replace(" ","").replace(",", "','")+"')"
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.* from sample s join material m on m.material_id = s.material_id join individual i \
        on i.individual_id=m.individual_id left join location l on l.location_id=i.location_id where s.latest=1 \
        and (s.accession in {s_list} or s.name in {s_list}) and l.location='{loc}';".format(loc=location, s_list=s_list))
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples with these criteria")
    if len(sresults) > 0:
        for row in sresults:
            try:
                curs.execute("SELECT distinct i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                if json=='json':
                    return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
                else:
                    flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
            curs.close()
        if json == 'json':
            return jsonify(tuple_to_dic(columns,results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_samples_by_sample_name_and_location', sname=sname, location=location, db=db, json=json), 'sample']
            return render_template("mysql.html", title="Query was: sample(s) where sample_name  = " +s_list+" and location ='"+location+"'", url_param=['lane', 0, '/web'], results=[columns,results], plus=['',''], db=db, crumbs=crumbs)
    else:
        curs.close()
        if json=='json':
            return jsonify({"Data error":"no sample associated with criteria provided"})
        else:
            flash("no sample associated with criteria provided")
            return redirect(url_for('db_index', db=db))

@app.route('/<db>/api/1.1/location/name/<location>/species/name/<sp_name>/<json>', methods=['GET'])
def get_species_per_name_and_per_location(location, sp_name, db, json):
    loc_columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct I.* FROM individual I join location L on L.location_id = I.location_id \
        join species S on S.species_id = I.species_id where I.latest=1 and L.location = '{reg}' and (S.name like '%%{spn}%%' or S.common_name like '%%{spn}%%');". format(reg=location, spn=sp_name))
        res=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location and / or species")
    curs.close()
    if len(res) == 0:
        if json=='json':
            return jsonify({"Data error":"no species associated with criteria provided"})
        else:
            flash ("Error: no species associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        results=list([x[1:8] for x in list(res)])
        new_columns, display_results= change_for_display([loc_columns[1:8]], results)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_species_per_name_and_per_location', location=location, sp_name=sp_name, db=db, json=json), 'individual']
            return render_template("mysql.html", title='Query was: individual(s) where location = "'+ location +'" and species like "'+sp_name+'"', url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/location/<json>', methods=['GET'])
def get_location(db, json):
    loc_columns=get_columns_from_table('location')
    columns=list(loc_columns)+["individuals", "species"]
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct l.location_id, l.country_of_origin, l.location, l.sub_location, l.latitude, l.longitude, \
        count(distinct i.individual_id), count(distinct i.species_id) from location l join individual i on l.location_id = i.location_id \
        where  i.latest = 1 group by l.location_id, l.country_of_origin, l.location, l.sub_location, l.latitude, l.longitude limit 5")
        l_results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch locations")
    curs.close()
    if len(l_results) == 0:
        if json=='json':
            return jsonify({"Data error":"no location data available in the database '"+db+"'"})
        else:
            flash ("Error: no location data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        for row in l_results:
            row=['' if x is None else x for x in row]
            row[4]=str(row[4])
            row[5]=str(row[5])
            results.append(row)
        if json == 'json':
            return jsonify(tuple_to_dic(columns, results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_location', db=db, json=json), 'location']
            return render_template("mysql.html", title='Query was: all locations', url_param=['location',0, '/web'], results=[columns,results], plus =['.',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/material/<m_id>/<json>', methods=['GET'])
def get_material_per_material_id(m_id, db, json):
    scolumns=get_columns_from_table('sample')
    columns=tuple([scolumns[1]]+[scolumns[5]]+["individual_id"]+list(scolumns[2:5])+list(scolumns[6:]) +list(["files"]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct s.sample_id, s.name, s.material_id, s.accession, s.ssid, s.public_name, s.changed, s.latest, \
        count(distinct f.file_id) from sample s join lane l on l.sample_id=s.sample_id join file f on f.lane_id=l.lane_id where \
        s.latest=1 and f.latest=1 and s.material_id = '%s' group by s.sample_id, s.name, s.material_id, s.accession, s.ssid, s.public_name, s.changed, \
        s.latest;" % m_id)
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch sample")
    if len(sresults) == 0 :
        curs.close()
        if json=='json':
            return jsonify({"Data error":"no sample associated with criteria provided"})
        else:
            flash ("Error: no sample associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        try:
            curs.execute("SELECT distinct individual_id FROM material where material_id = '%s' ;" % m_id)
            iresults=curs.fetchall()
        except:
            if json=='json':
                return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
            else:
                flash ("Error: unable to fetch individual")
        results=tuple(sresults[0][:3]+tuple([iresults[0][0]])+sresults[0][3:])
        curs.close
        new_columns, display_results= change_for_display([columns], [results])
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0], display_results))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'sample' not in list_crumbs:
                session['breadcrumbs'].append(session.get('query', None))
            else:
                crumbs.pop()
            session['query']=[url_for('get_material_per_material_id', m_id=m_id, db=db, json=json), 'sample']
            for_display = "'"+display_results[0][3] + "' ("+str(m_id)+")"
            session["name"] = display_results[0][3]
            return render_template("mysql.html", title='Query was: material name (material_id) = '+for_display, url_param=['material/'+str(m_id)+'/sample',0, '/web'], results=[new_columns[0], display_results], plus=['.',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/material/<m_id>/sample/<s_id>/<json>', methods=['GET'])
def get_material_per_material_id_and_sample_id(m_id, s_id, db, json):
    lcolumns=get_columns_from_table('lane')
    columns=[lcolumns[1]]+[lcolumns[6]]+list(lcolumns[2:6]) +[lcolumns[7]] + list(lcolumns[12:] +tuple(["files"]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct l.lane_id,l.name,l.sample_id, l.seq_tech_id, l.seq_centre_id, l.library_id, l.accession, l.changed, l.latest, \
        count(distinct f.file_id) from lane l join file f on f.lane_id=l.lane_id where l.latest=1 and f.latest=1 and l.sample_id = '%s' group by l.lane_id,l.name,l.sample_id, l.seq_tech_id, \
        l.seq_centre_id, l.library_id, l.accession, l.changed, l.latest;" % s_id)
        lresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch lane")
    try:
        curs.execute("select material_id, sample_id from sample where latest = 1 and material_id = '%s';" % m_id)
        mresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch sample data")
    curs.close
    if len(lresults) == 0 or len(mresults) == 0:
        if json=='json':
            return jsonify({"Data error":"no lane associated with criteria provided"})
        else:
            flash ("Error: no lane associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        new_columns, display_results= change_for_display([columns], lresults)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0], display_results))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'lane' not in list_crumbs:
                session['breadcrumbs'].append(session.get('query', None))
                session['query']=[url_for('get_material_per_material_id_and_sample_id', m_id=m_id, s_id=s_id, db=db, json=json), 'lane']
            else:
                crumbs.pop()
            for_display="material name (material_id) = '"+session["name"]+"' (" +str(m_id)+") and sample name (sample_id)=  '"+display_results[0][2]+"' ("+str(s_id)+")"
            return render_template("mysql.html", title='Query was: material = '+for_display, url_param=['file',0, '/web'], results=[new_columns[0], display_results], plus=['.',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/material/<json>', methods=['GET'])
def get_material(db, json):
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
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch materials")
    curs.close
    if len(results) == 0 :
        if json=='json':
            return jsonify({"Data error":"no material data available in the database '"+db+"'"})
        else:
            flash ("Error: no material data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        new_columns, display_results= change_for_display([columns], list(results))
        if json == 'json':
            return get_material_all(db=db, json=json)
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_material', db=db, json=json), 'material']
            return render_template("mysql.html", title='Query was: all materials', url_param=['material',0, '/web'], results=[new_columns[0], display_results], plus=['all/web', 'yes'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/material/all/<json>', methods=['GET'])
def get_material_all(db, json):
    scolumns=get_columns_from_table('material')
    columns=tuple([scolumns[1]])+tuple([scolumns[4]])+scolumns[2:4]+tuple([scolumns[12]])+scolumns[5:12]+scolumns[13:]+tuple(["samples"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct m.material_id, m.name, m.individual_id, m.accession, m.developmental_stage_id, m.provider_id, m.date_received, \
        m.storage_condition, m.storage_location, m.type, m.volume, m.concentration, m.organism_part_id, m.changed, m.latest, \
        count(distinct s.sample_id) FROM material m join sample s on s.material_id=m.material_id where s.latest=1 group by m.material_id, \
        m.name, m.individual_id, m.accession, m.developmental_stage_id, m.provider_id, m.date_received, m.storage_condition, m.storage_location, \
        m.type, m.volume, m.concentration, m.organism_part_id, m.changed, m.latest")
        results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch materials")
    curs.close
    if len(results) == 0 :
        if json=='json':
            return jsonify({"Data error":"no material data available in the database '"+db+"'"})
        else:
            flash ("Error: no material data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        new_columns, display_results= change_for_display([columns], list(results))
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0], display_results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_material', db=db, json=json), 'material']
            return render_template("mysql.html", title='Query was: all materials', url_param=['material',0, '/web'], results=[new_columns[0], display_results], plus=['/'+db+'/api/1.1/material/web','no'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/project/<p_id>/<json>', methods=['GET'])
def get_project_per_project_id(p_id, db, json):
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct I.*, p.name FROM individual I join allocation a  on a.individual_id=i.individual_id join project p \
        on p.project_id  = a.project_id and p.project_id ='%s' and I.latest=1" % p_id)
        presults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(presults) == 0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(session['query'][0])
    else:
        columns = columns[1:7]
        result=remove_column(presults, 1)
        results=list([x[:6] for x in list(result)])
        new_columns, display_results= change_for_display([columns], results)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'individual' not in list_crumbs:
                crumbs.append([url_for('get_projects', db=db, json=json), 'project'])
            else:
                crumbs.pop()
            session['query']=[url_for('get_project_per_project_id', p_id=p_id, db=db, json=json), 'individual']
            for_display="project name (project_id)= '"+presults[0][-1]+"' ("+str(p_id)+")"
            return render_template("mysql.html", title='Query was: individual(s) where '+for_display, url_param=['project/'+str(p_id)+'/individual',  0, '/web' ], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['',''],db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/project/<p_id>/individual/<i_id>/<json>', methods=['GET'])
def get_individual_per_project_id_and_individual_id(p_id, i_id, db, json):
    results=[]
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.*, p.name FROM individual i left join allocation a on a.individual_id=i.individual_id left join project p \
        on p.project_id=a.project_id WHERE i.individual_id  = '{i_id}' and latest=1 and p.project_id = '{p_id}';". format(i_id=i_id, p_id=p_id))
        presults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(presults) == 0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        columns = columns[1:7]
        result=remove_column(presults, 1)
        results=tuple([x[:6] for x in list(result)])
        new_columns, display_results= change_for_display([columns], results)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'individual' not in list_crumbs:
                session['breadcrumbs'].append(session.get('query', None))
            else:
                crumbs.pop()
                crumbs.append([url_for('get_project_per_project_id', p_id=p_id, db=db, json=json), 'individual'])
            session['query']=[url_for('get_individual_per_project_id_and_individual_id', p_id=p_id, i_id=i_id, db=db, json=json), 'individual']
            for_display="project name (project_id) = '"+presults[0][-1]+"' ("+str(p_id)+ ") and supplier_name (individual_id) = '" +display_results[0][1]+"' ("+str(i_id)+")"
            return render_template("mysql.html", title='Query was: individual(s) where '+for_display, url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/project/name/<accession>/<json>', methods=['GET'])
def get_project_per_accession(accession, db, json):
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct project_id FROM project WHERE accession = '%s';" % accession)
        results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(results) == 0:
        if json == 'json':
            return jsonify({"Data error":"no project associated with criteria provided"})
        else:
            flash ("Error: no project associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        if json=='json':
            return get_project_per_project_id(p_id=results[0][0], db=db, json=json)
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs']=crumbs
            session['query']=[url_for('db_index', db=db), db]
            return(redirect(url_for('get_project_per_project_id', p_id=results[0][0], db=db, json=json)))

@app.route('/<db>/api/1.1/project/name/<accession>/individual/name/<ind_name>/<json>', methods=['GET'])
def get_individual_per_project_accession_and_name(accession, ind_name, db, json):
    result=[]
    ind_list=ind_name.replace(" ","").replace(",", "','")
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        query=("SELECT * FROM individual WHERE individual_id in (select individual_id from allocation a join project p \
        where p.project_id  = a.project_id and p.accession = '{acc}') and (individual.name in ('{i_list}') or individual.alias in ('{i_list}')) and latest=1;". format(acc=accession, i_list=ind_list))
        curs.execute(query)
        result=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(result) == 0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        results=[x[1:7] for x in list(result)]
        new_columns, display_results= change_for_display([columns[1:7]], results)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_individual_per_project_accession_and_name', accession=accession, ind_name=ind_name, db=db, json=json), 'individual']
            return render_template("mysql.html", title='Query was: individual(s) where project_accession = "'+accession+'" & individual_name = "'+ind_name +'"', url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/project/name/<accession>/location/name/<location>/<json>', methods=['GET'])
def get_project_per_accession_and_location(accession, location, db, json):
    loc_columns=get_columns_from_table('individual')
    columns=loc_columns[1:8]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct I.* FROM individual I join location L on L.location_id = I.location_id \
        join species S on S.species_id = I.species_id \
        left outer join allocation A on A.individual_id=I.individual_id \
        left outer join project P on P.project_id=A.project_id \
        where L.location = '{reg}' and P.accession = '{acc}'". format(reg=location, acc=accession))
        res=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch location and / or project accession")
    curs.close()
    if len(res) >0:
        results=[x[1:8] for x in list(res)]
        new_columns, display_results= change_for_display([columns], results)
        display_results=remove_column(display_results, 'L')
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], display_results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_project_per_accession_and_location', accession=accession, location=location, db=db, json=json),'individual']
            return render_template("mysql.html", title='Query was: individual(s) where location = "'+ location +'" and project_accession = "'+accession+'"', url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], display_results], plus=['',''], db=db, crumbs=crumbs)
    else:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('db_index', db=db))

@app.route('/<db>/api/1.1/project/name/<accession>/sample/name/<sname>/<json>', methods=['GET'])
def get_samples_by_sample_name_and_project(sname, accession, db, json):
    s_list="('"+sname.replace(" ","").replace(",", "','")+"')"
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.* from sample s join material m on m.material_id = s.material_id join individual i \
    on i.individual_id=m.individual_id left join allocation a on a.individual_id=i.individual_id join project p \
    on p.project_id=a.project_id where s.latest=1 and (s.accession in {s_list} or s.name in {s_list}) \
    and p.accession='{acc}';".format(acc=accession, s_list=s_list))
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples with these criteria")
    if len(sresults) > 0:
        for row in sresults:
            try:
                curs.execute("SELECT distinct i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                if json=='json':
                    return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
                else:
                    flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
        curs.close()
        if json == 'json':
            return jsonify(tuple_to_dic(columns,results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_samples_by_sample_name_and_project', sname=sname, accession=accession, db=db, json=json), 'sample']
            for_display="in " + s_list
            if "," not in s_list:
                for_display="= " + s_list[1:-1]
            return render_template("mysql.html", title="Query was: sample(s) where sample_name " +for_display+ " and project = '"+accession+"'", url_param=['lane', 0, '/web'], results=[columns,results], plus=['',''], db=db, crumbs=crumbs)
    else:
        curs.close()
        if json == 'json':
            return jsonify({"Data error":"no sample associated with criteria provided"})
        else:
            flash ("Error: no sample associated with criteria provided")
            return redirect(url_for('db_index', db=db))

@app.route('/<db>/api/1.1/project/name/<accession>/species/name/<sp_name>/<json>', methods=['GET'])
def get_individual_per_project_accession_and_species(accession, sp_name, db, json):
    results=()
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct * FROM individual WHERE individual_id in (select individual_id from allocation a join project p \
        where p.project_id  = a.project_id and p.accession = '{acc}') and species_id in (select species_id from species where \
         name like '%%{spn}%%' or common_name like '%%{spn}%%') and latest=1;". format(acc=accession, spn=sp_name))
        result=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(result) == 0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        results=tuple([x[1:7] for x in list(result)])
        new_columns, display_results = change_for_display([columns[1:7]], results)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_individual_per_project_accession_and_species', accession=accession, sp_name=sp_name, db=db, json=json),'individual']
            return render_template("mysql.html", title='Query was: individual(s) where project_id = "'+accession+'" & species like = "'+sp_name+'"', url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/project/<json>', methods=['GET'])
def get_projects(db, json):
    columns=get_columns_from_table('project')
    curs = mysql.connection.cursor()
    try:
        curs.execute("select p.project_id, p.name, p.alias, p.accession, p.ssid, count(distinct a.individual_id), count(distinct species_id) from project p \
        JOIN allocation a on p.project_id=a.project_id join individual i on i.individual_id=a.individual_id where i.latest=1 group by p.project_id, p.name, \
        p.alias, p.accession, p.ssid")
        presults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch projects")
    curs.close()
    if len(presults) == 0 :
        if json=='json':
            return jsonify({"Data error":"no project data available in the database '"+db+"'"})
        else:
            flash ("Error: no project data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        if json == 'json':
            return jsonify(tuple_to_dic(columns+tuple(['individuals', 'species']),presults))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_projects', db=db, json=json), 'projects']
            return render_template("mysql.html", title='Query was: all projects', url_param=['project', 0, '/web'], results=[columns+tuple(['individuals', 'species']),presults], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/provider/<p_id>/<json>', methods=['GET'])
def get_individual_by_provider(p_id, db, json):
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.*, p.provider_name FROM individual i right join provider p on p.provider_id=i.provider_id where i.latest=1 and p.provider_id ='%s';" % p_id)
        result=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individual")
    curs.close()
    if len(result) == 0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        results=tuple([x[1:7] for x in list(result) if x[1] is not None])
        new_columns, display_results = change_for_display([columns[1:7]], results)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'individual' not in list_crumbs:
                crumbs.append(session.get('query', None))
            else:
                crumbs.pop()
            session['query']=[url_for('get_individual_by_provider', p_id=p_id, db=db, json=json), 'individual']
            return render_template("mysql.html", title='Query was: individuals from provider ="' + result[0][-1]+'"', url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/provider/<json>', methods=['GET'])
def get_provider(db, json):
    pcolumns=get_columns_from_table('provider')
    columns=pcolumns[:2]+tuple([pcolumns[4]])+tuple(["individuals", 'species'])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct p.provider_id, p.provider_name, p.affiliation, \
        count(distinct i.individual_id), count(distinct i.species_id) from provider p join individual i on i.provider_id=p.provider_id \
        where p.latest=1 and i.latest=1 group by p.provider_id, p.provider_name, p.affiliation")
        results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch provider")
    curs.close()
    if len(results) == 0 :
        if json=='json':
            return jsonify({"Data error":"no provider data available in the database '"+db+"'"})
        else:
            flash ("Error: no provider data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        if json == 'json':
            return get_provider_all(db=db, json=json)
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_provider', db=db, json=json), 'provider']
            return render_template("mysql.html", title='Query was: all providers', url_param=['provider', 0, '/web' ], results=[columns,results], plus=['all/web','yes'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/provider/all/<json>', methods=['GET'])
def get_provider_all(db, json):
    pcolumns=get_columns_from_table('provider')
    columns=pcolumns+tuple(["individuals", 'species'])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct p.provider_id, p.provider_name, p.email, p.affiliation, p.address, p.phone, p.changed, p.latest, \
        count(distinct i.individual_id), count(distinct i.species_id) from provider p join individual i on i.provider_id=p.provider_id \
        where i.latest=1 group by p.provider_id, p.provider_name, p.email, p.affiliation, p.address, p.phone, p.changed, p.latest")
        results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch provider")
    curs.close()
    if len(results) == 0 :
        if json=='json':
            return jsonify({"Data error":"no provider data available in the database '"+db+"'"})
        else:
            flash ("Error: no provider data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        if json == 'json':
            return jsonify(tuple_to_dic(columns,results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_provider', db=db, json=json), 'provider']
            return render_template("mysql.html", title='Query was: all providers', url_param=['provider', 0 , '/web'], results=[columns,results], plus=['/'+db+'/api/1.1/provider/web','no'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/sample/<s_id>/<json>', methods=['GET'])
def get_sample_per_sample_id(s_id, db, json):
    results=[]
    scolumns=get_columns_from_table('lane')
    col=tuple(list(scolumns[1:2])+["individual_id"]+["sample_id"]+list(scolumns[3:8])+list(scolumns[12:]))
    updated_col=col+tuple(["files"])
    columns=updated_col
    list_s_id ="("+s_id+")"
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct * FROM lane where sample_id in %s ;" % list_s_id)
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters1"})
        else:
            flash ("Error: unable to fetch lanes")
    if len(sresults) > 0:
        for index in range(0, len(sresults)):
            row=sresults[index]
            try:
                curs.execute("SELECT distinct m.individual_id, s.name, s.sample_id FROM material m left join sample s on m.material_id=s.material_id where s.sample_id = %s ;" % row[2])
                iresults=curs.fetchall()
            except:
                if json=='json':
                    return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters2"})
                else:
                    flash ("Error: unable to fetch individual")
            try:
                curs.execute("SELECT count(file_id) from file where lane_id = %s;" % row[1])
                file_return=curs.fetchall()
            except:
                if json=='json':
                    return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters3ß"})
                else:
                    flash ("Error: unable to fetch items")
            id_results=list(row[1:2])+[iresults[0][0]]+[iresults[0][2]]+list(row[3:8])+list(row[12:])+[file_return[0][0]]
            results.append(tuple(id_results))
        curs.close()
        columns, results= change_for_display([columns], results)
        if json == 'json':
            return jsonify(tuple_to_dic(columns[0],results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            crumbs.append([url_for('get_samples', db=db, json=json), 'sample'])
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_sample_per_sample_id', s_id=s_id, db=db, json=json), 'lane']
            dicj=dict(remove_column(iresults, 1))
            for_display="sample name (sample_id) = "+str(dicj)[1:-1].replace(",", "),").replace(": ", " (")+")"
            return render_template("mysql.html", title='Query was: lane(s) where '+for_display, url_param=['file', 0, '/web'], results=[columns[0],results], plus=['',''], db=db, crumbs=crumbs)
    else:
        curs.close()
        if json == 'json':
            return jsonify({"Data error":"no lane associated with criteria provided"})
        else:
            flash ("Error: no lane associated with criteria provided")
            return redirect(url_for('db_index', db=db))

@app.route('/<db>/api/1.1/sample/<s_id>/lane/<l_id>/<json>', methods=['GET'])
def get_lane_per_sample_id_and_lane_id(s_id, l_id, db, json):
    results=[]
    sample_dic={}
    lcolumns=get_columns_from_table('lane')
    columns=tuple([lcolumns[1]]+[lcolumns[7]]+[lcolumns[6]]+list(lcolumns[3:6])+list(lcolumns[8:]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct l.*, s.name FROM lane l join sample s on s.sample_id=l.sample_id where l.latest=1 and l.lane_id = '%s';" % l_id)
        lresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch lanes")
    curs.close()
    if len(lresults) == 0:
        if json == 'json':
            return jsonify({"Data error":"no lane associated with criteria provided"})
        else:
            flash ("Error: no lane associated with criteria provided")
    else:
        for row in lresults:
            sample_dic[row[-1]]=row[2]
            l_results=[row[1]]+[row[7]]+[row[6]]+list(row[3:6])+list(row[8:-1])
            results.append(l_results)
        new_column, display_results= change_for_display([columns], results)
        new_columns=list(new_column)
        new_columns[0][5]='library_accession'
        if json=='json':
            return jsonify(tuple_to_dic(new_columns[0], tuple(display_results)))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'file' in list_crumbs:
                crumbs.pop(list_crumbs.index('file'))
            if 'lane' not in list_crumbs:
                crumbs.append([url_for('get_sample_per_sample_id', s_id=s_id, db=db, json=json), 'lane'])
            session['breadcrumbs']=crumbs
            session['query']=[url_for('get_lane_per_sample_id_and_lane_id', s_id=s_id, l_id=l_id, db=db, json=json), 'file']
            for_display="sample name (sample_id)= '" + str(sample_dic)[1:-1].replace(": ", " (")+")"
            return render_template("mysql.html", title='Query was: lane(s) where '+for_display, url_param=['file', 0, '/web'], results=[new_columns[0], tuple(display_results)], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/sample/name/<sname>/<json>', methods=['GET'])
def get_samples_by_name(sname, db, json):
    s_list=sname.replace(" ","").replace(",", "','")
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct sample_id FROM sample where latest=1 and name in ('{slist}') or accession in ('{slist}');".format(slist=s_list))
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples")
    curs.close()
    if len(sresults) == 0:
        if json == 'json':
            return jsonify({"Data error":"no sample associated with criteria provided"})
        else:
            flash ("Error: no sample associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        list_sample_id=",".join([str(x[0]) for x in sresults])
        if json=='json':
            return get_sample_per_sample_id(s_id=list_sample_id, db=db, json=json)
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs']=crumbs
            session['query']=[url_for('db_index', db=db), db]
            return(redirect(url_for('get_sample_per_sample_id', s_id=list_sample_id, db=db, json=json)))

@app.route('/<db>/api/1.1/sample/name/<sname>/individual/name/<ind_name>/<json>', methods=['GET'])
def get_samples_by_sample_name_and_individual_name(sname, ind_name, db, json):
    s_list="('"+sname.replace(" ","").replace(",", "','")+"')"
    ind_list=ind_name.replace(" ","").replace(",", "','")
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.* from sample s join material m on m.material_id = s.material_id join individual i on i.individual_id=m.individual_id where s.latest=1 and (i.name in ('{ind_list}') \
         or i.alias in ('{ind_list}')) and (s.accession in {s_list} or s.name in {s_list});".format(ind_list=ind_list, s_list=s_list))
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples with these criteria")
    if len(sresults) > 0:
        for row in sresults:
            try:
                curs.execute("SELECT distinct i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                if json=='json':
                    return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
                else:
                    flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
        curs.close()
        if json=='json':
            return jsonify(tuple_to_dic(columns,results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_samples_by_sample_name_and_individual_name', sname=sname, ind_name=ind_name, db=db, json=json), 'individual']
            return render_template("mysql.html", title="Query was: sample(s) where sample_name  = " +s_list+" and individual_name = '"+ind_name+"'", url_param=['lane', 0, '/web'], results=[columns,results], plus=['',''], db=db, crumbs=crumbs)
    else:
        curs.close()
        if json == 'json':
            return jsonify({"Data error":"no sample associated with criteria provided"})
        else:
            flash ("Error: no sample associated with criteria provided")
            return redirect(url_for('db_index', db=db))

@app.route('/<db>/api/1.1/sample/<json>', methods=['GET'])
def get_samples(db, json):
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["individual_id"]+list(scolumns[3:4])+list(scolumns[6:]) +list(["files"]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.sample_id, s.material_id, s.accession, s.ssid, s.name, s.public_name, s.changed, s.latest, count(distinct f.file_id) \
         from sample s join lane l on l.sample_id=s.sample_id join file f on f.lane_id=l.lane_id where s.latest=1 and f.latest=1 group by \
         s.sample_id, s.material_id, s.accession, s.ssid, s.name, s.public_name, s.changed, s.latest")
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples")
    if len(sresults) == 0:
        curs.close()
        if json=='json':
            return jsonify({"Data error":"no sample data available in the database '"+db+"'"})
        else:
            flash ("Error: no sample data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        for row in sresults:
            try:
                curs.execute("SELECT distinct i.individual_id from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s' ;" % row[1])
                id_return=curs.fetchall()
            except:
                if json=='json':
                    return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
                else:
                    flash ("Error: unable to fetch items")
            id_results=[row[0]]+[row[4]]+[id_return[0][0]]+list(row[2:3])+list(row[5:])
            results.append(tuple(id_results))
        curs.close()
        new_columns, display_results= change_for_display([columns], results)
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0],display_results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_samples', db=db, json=json), 'sample']
            return render_template("mysql.html", title='Query was: all samples', url_param=['sample', 0, '/web'], results=[new_columns[0],display_results], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/species/<sp_id>/<json>', methods=['GET'])
def get_species_per_species_id(sp_id, db, json):
    columns=get_columns_from_table('individual')[1:8]
    results=[]
    curs = mysql.connection.cursor()
    list_sp_id ="("+sp_id+")"
    try:
        curs.execute("SELECT distinct i.*, s.name FROM individual i join species s on i.species_id=s.species_id where i.latest=1 and s.species_id in %s;" % list_sp_id)
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
            return redirect(url_for('db_index', db=db))
    curs.close
    if len(sresults) == 0:
        if json=='json':
            return jsonify({"Data error":"no species associated with criteria provided"})
        else:
            flash ("Error: no species associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        for row in sresults:
            s_results=list(row)[1:8]
            sname=row[-1]
            results.append(tuple(s_results))
        new_columns, display_results = change_for_display(list([columns]), list(results))
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'species' not in list_crumbs:
                crumbs.append(session.get('query', None))
            else:
                crumbs.pop()
            if isinstance(session['query'], str):
                sname="like '"+session['query']+"'"
            else:
                sname="= '"+str(sname)+"'"
            session['query']=[url_for('get_species_per_species_id', sp_id=sp_id, db=db, json=json), 'individual']
            if "," in list_sp_id:
                for_display = "species name like '" + session['name']+"'"
            else:
                for_display = "species name (species_id) " + sname + " ("+str(sp_id)+")"
                session['name']=""
            return render_template("mysql.html", title='Query was: individual(s) where ' +for_display, url_param=['species/'+str(sp_id)+'/individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/species/<sp_id>/individual/<i_id>/<json>', methods=['GET'])
def get_individual_per_species_id_and_individual_id(sp_id, i_id, db, json):
    columns=get_columns_from_table('individual')[1:8]
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct * FROM individual where latest=1 and individual_id = '{ind}' and species_id = '{sp}';". format(ind=i_id, sp=sp_id))
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch individuals")
            return redirect(url_for('db_index', db=db))
    curs.close
    if len(sresults) == 0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        for row in sresults:
            s_results=list(row)[1:8]
            results.append(s_results)
        new_columns, display_results = change_for_display([columns], tuple(results))
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], remove_column(display_results, 'L')))
        else:
            crumbs=session.get('breadcrumbs', None)
            list_crumbs=[x[-1] for x in crumbs]
            if 'individual' not in list_crumbs:
                crumbs.append(session.get('query', None))
            else:
                crumbs.pop()
                crumbs.append([url_for('get_species_per_species_id', sp_id=sp_id, db=db, json=json), 'individual'])
            if "," in sp_id:
                for_display = "species name like '" + session['name']+"'"
                session['query']=[url_for('get_individual_per_species_id_and_individual_id', sp_id=sp_id, i_id=i_id, db=db, json=json), 'individual']
            else:
                for_display = "species name (species_id) = '" + display_results[0][3] +"' ("+str(sp_id) +")"
                session['query']=[url_for('get_individual_per_species_id_and_individual_id', sp_id=sp_id, i_id=i_id, db=db, json=json), 'individual']
            for_display+=" and individual name (individual_id) = '"+sresults[0][2] +"' ("+str(i_id)+")"
            return render_template("mysql.html", title='Query was: individual(s) where '+for_display, url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], remove_column(display_results, 'L')], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/species/<json>', methods=['GET'])
def get_species(db, json):
    scolumns=get_columns_from_table('species')
    columns=scolumns[1:6]+tuple([scolumns[9]])+tuple(["individuals"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.species_id, s.name, s.strain, s.taxon_id, s.common_name, s.taxon_position, count(distinct i.individual_id) \
        from species s join individual i on i.species_id=s.species_id  where s.latest=1 and i.latest=1 group by s.species_id, s.name, s.strain, \
        s.taxon_id, s.common_name, s.taxon_position")
        results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch species")
            return redirect(url_for('db_index', db=db))
    curs.close()
    if len(results) == 0 :
        if json=='json':
            return jsonify({"Data error":"no species data available in the database '"+db+"'"})
        else:
            flash ("Error: no species data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        new_columns, display_results= change_for_display(list([columns]), list(results))
        if json == 'json':
            return get_species_all(db=db, json=json)
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_species', db=db, json=json), 'species']
            return render_template("mysql.html", title='Query was: all species', url_param=['species',0, '/web'], results=[new_columns[0], display_results], plus=['all/web', 'yes'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/species/all/<json>', methods=['GET'])
def get_species_all(db, json):
    scolumns=get_columns_from_table('species')
    columns=scolumns[1:]+tuple(["individuals"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.species_id, s.name, s.strain, s.taxon_id, s.common_name, \
        s.karyotype, s.ploidy, s.family_id, s.taxon_position, s.genome_size, s.iucn, s.changed, s.latest, \
        count(distinct i.individual_id) from species s join individual i on i.species_id=s.species_id \
        where i.latest=1 group by s.species_id, s.name, s.strain, s.taxon_id, s.common_name, \
        s.karyotype, s.ploidy, s.family_id, s.taxon_position, s.genome_size, s.iucn, s.changed, s.latest")
        results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch species")
            return redirect(url_for('db_index', db=db))
    curs.close()
    if len(results) == 0 :
        if json=='json':
            return jsonify({"Data error":"no species data available in the database '"+db+"'"})
        else:
            flash ("Error: no species data available in the database '"+db+"'")
            return redirect(url_for('db_index', db=db))
    else:
        new_columns, display_results= change_for_display(list([columns]), list(results))
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0], display_results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_species', db=db, json=json), 'species']
            return render_template("mysql.html", title='Query was: all species', url_param=['species',0, '/web'], results=[new_columns[0], display_results], plus=['/'+db+'/api/1.1/species/web','no'], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/species/name/<sp_name>/<json>', methods=['GET'])
def get_species_per_name(sp_name, db, json):
    list_species_id=""
    scolumns=get_columns_from_table('species')
    columns=scolumns[1:6]+scolumns[9:]+tuple(["individuals"])
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.species_id from species s where s.latest=1 and (s.name like '%{spn}%' or s.common_name like '%{spn}%')".format(spn=sp_name))
        results=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch species")
            return redirect(url_for('db_index', db=db))
    curs.close()
    if len(results) == 0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        for row in results:
            list_species_id+=","+str(row[0])
        if json == 'json':
            return get_species_per_species_id(sp_id=list_species_id[1:], db=db, json=json)
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_species', db=db, json=json), 'species']
            session['name']=sp_name
            return redirect(url_for('get_species_per_species_id', sp_id=list_species_id[1:], db=db, json=json))

@app.route('/<db>/api/1.1/species/name/<sp_name>/individual/name/<ind_name>/<json>', methods=['GET'])
def get_individual_per_name_and_species_name(ind_name, sp_name, db, json):
    ind_list=ind_name.replace(" ","").replace(",", "','")
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT distinct i.* FROM individual i join species s on i.species_id=s.species_id WHERE (s.name like '%%{spn}%%' or s.common_name like '%%{spn}%%') and (i.name in ('{i_l}') or i.alias in ('{i_l}'));". format(spn=sp_name, i_l=ind_list))
        res=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch items")
    curs.close()
    if len(res) == 0:
        if json == 'json':
            return jsonify({"Data error":"no individual associated with criteria provided"})
        else:
            flash ("Error: no individual associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        results=[x[1:8] for x in list(res)]
        new_columns, display_results = change_for_display([columns[1:8]], results)
        #remove the thumbnail field for display
        display_results=tuple([x[:-1] for x in list(display_results)])
        session['query']=[]
        if json == 'json':
            return jsonify(tuple_to_dic(new_columns[0][:-1], display_results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_individual_per_name_and_species_name', ind_name=ind_name, sp_name=sp_name, db=db, json=json), 'individual']
            return render_template("mysql.html", title='Query was : individual(s) where supplier_name = "'+str(ind_name)+'" & species like "'+str(sp_name)+ '"', url_param=['individual', 0, '/web'], results=[new_columns[0][:-1], display_results], plus=['',''], db=db, crumbs=crumbs)

@app.route('/<db>/api/1.1/species/name/<sp_name>/sample/name/<sname>/<json>', methods=['GET'])
def get_samples_by_sample_name_and_species(sname, sp_name, db, json):
    s_list="('"+sname.replace(" ","").replace(",", "','")+"')"
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select distinct s.* from sample s join material m on m.material_id = s.material_id join individual i \
        on i.individual_id=m.individual_id left join species sp on sp.species_id=i.species_id where s.latest=1 \
        and (s.accession in {s_list} or s.name in {s_list}) and (sp.name like '%{spn}%' or sp.common_name like '%{spn}%');".format(spn=sp_name, s_list=s_list))
        sresults=curs.fetchall()
    except:
        if json=='json':
            return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
        else:
            flash ("Error: unable to fetch samples with these criteria")
    if len(sresults) == 0:
        curs.close()
        if json == 'json':
            return jsonify({"Data error":"no sample associated with criteria provided"})
        else:
            flash ("Error: no sample associated with criteria provided")
            return redirect(url_for('db_index', db=db))
    else:
        for row in sresults:
            try:
                curs.execute("SELECT distinct i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                if json=='json':
                    return jsonify({"Connection error":"could not connect to database "+db+" or unknown url parameters"})
                else:
                    flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
        curs.close()
        if json == 'json':
            return jsonify(tuple_to_dic(columns,results))
        else:
            crumbs=[[url_for('db_index', db=db), db]]
            session['breadcrumbs'] = crumbs
            session['query']=[url_for('get_samples_by_sample_name_and_species', sname=sname, sp_name=sp_name, db=db, json=json), 'sample']
            return render_template("mysql.html", title="Query was: sample(s) where sample_name  = " +s_list+" and species like '"+sp_name+"'", url_param=['lane', 0, '/web'], results=[columns,results], plus=['',''], db=db, crumbs=crumbs)

if __name__ == "__main__":
    app.run(debug=True)
