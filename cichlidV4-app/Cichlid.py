#!/Library/Frameworks/Python.framework/Versions/3.7/bin/python3
 #/usr/bin/python3 for web version
from flask import Flask, render_template, request,  flash, redirect, url_for, session, send_file
from flask_mysqldb import MySQL
from flask_migrate import Migrate
from flask_login import UserMixin, login_user, logout_user, current_user, login_required, LoginManager
from wtforms import Form, BooleanField, TextField, PasswordField, validators
import hashlib
from MySQLdb import escape_string as thwart
import gc, json
import os, binascii
from flask_mail import Message, Mail
from forms import LoginForm, RegistrationForm, EntryForm, EnterDataForm, ViewForm
from config import Config
app = Flask(__name__)

'''
    Website script written by H. Denise (Cambridge Uni) 6/08/2019
    Script still in progress with optimisation and code clean-up to be carried out
    Also upload of data need to be fully implemented
'''

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
migrate = Migrate(app, mysql)
login = LoginManager(app)
app.config.update(mail_settings)
mail = Mail(app)
#login.login_view = 'login'
mail.init_app(app)
@login.user_loader
def load_user(id):
    return query.get(int(id))

def hash_password(password):
    """Hash a password for storing."""
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'),
                                salt, 100000)
    pwdhash = binascii.hexlify(pwdhash)
    return (salt + pwdhash).decode('ascii')

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

def get_columns_from_table(table_name):
    """extract the name of fields for a given table  extracted from the database"""
    col=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS where table_schema=  '"+configSettings['MySQL_db'] +"' and table_name='%s' ORDER BY ORDINAL_POSITION;" %table_name)
        columns=curs.fetchall()
    except:
        flash ("Error: unable to fetch column names")
    curs.close()
    for col_name in columns:
        col.append(col_name[0])
    return tuple(col)

def change_for_display(col, data):
    """change the table_ids in column_name by the corresponding names/attributes for display
        plus 1) deal when multicolumns of a table have to be displayed, 2) add thumbnail for display,
        3) call function to display all individual_data and 4) call function to re-order when multiple entries are available"""
    table_name_dic={}
    list_old_data=[]
    list_new_data=[]
    columns=list(col)
    #dictionary to with 'table' name as key and name/attibute(s) values
    table_dic={'assembly':'name', 'cv':'attribute, comment', 'developmental_stage':'name', 'family':'name', 'file':'name',
    'image':'filename', 'individual':'name', 'lane':'name', 'library':'ssid', 'library_type':'name',
    'location':'country_of_origin, location, sub_location, latitude, longitude', 'material':'name', 'ontology':'name', 'organism_part':'name',
    'pipeline':'name', 'project':'name', 'provider':'provider_name', 'sample':'name', 'seq_centre':'name',
     'seq_tech':'name', 'species':'name', 'tax_order':'name'}
    #change the tuple(s) representing the data into list(s)
    for tup in data:
        list_old_data.append(list(tup))
    #RELABELLING THE COLUMN_NAMES
    for field_index in range(1, len(col)):
        table2=""
        if col[field_index].endswith("_id"):
            table=col[field_index][:-3]
            #the mother and father table_id are in fact individual_id so rename accordingly
            if table=='mother' or table=='father':
                table2=table
                table='individual'
            #special case for taxon_id as not linked to table so not to be 'translated'
            if table != 'taxon':
                table_name_dic[field_index]=table
                if table2=='mother' or table2=='father':
                    columns[field_index]=table2+"_name"
                else:
                    #special case for cv: no name but attribute
                    if table == "cv":
                        columns[field_index]= table+"_attribute"
                    else:
                        #special case for location as no name and 3 fields
                        if table == 'location':
                            columns[field_index]= 'location'
                        elif table=='individual':
                            columns[field_index]= 'supplier_name'
                        else:
                            columns[field_index]= table+"_name"
    #special case for location where several fields are returned
    if 'location' in columns and columns[0]=='individual_id':
        columns.insert(columns.index('location'), 'country_of_origin')
        columns.insert(columns.index('location')+1, 'sub_location')
        columns.insert(columns.index('location')+2, 'latitude')
        columns.insert(columns.index('location')+3, 'longitude')
    #special case for cv where two fields are returned
    if 'cv_attribute' in columns:
        columns.insert(columns.index('cv_attribute')+1, 'cv_comment')
    #REPLACING THE 'table_id' VALUES BY THE NAMES/ATTRIBUTES VALUES
    for row in list_old_data:
        for index in table_name_dic:
            if row[index] != None:
                curs = mysql.connection.cursor()
                try:
                    curs.execute("SELECT "+table_dic[table_name_dic[index]]+ " FROM "+table_name_dic[index]+" WHERE "+table_name_dic[index]+"_id = '{id}';". format(id=row[index]))
                    results=curs.fetchall()
                    if table_name_dic[index] in ('location', 'cv'):
                        row[index]=results[0]
                    else:
                        row[index]=results[0][0]
                except:
                    flash ("Error: unable to fetch items: "+"SELECT "+table_dic[table_name_dic[index]]+ " FROM "+table_name_dic[index]+" WHERE "+table_name_dic[index]+"_id = '{id}';". format(id=row[index]))
                curs.close()
        #add data in correct field when several fields are returned
        if 'country_of_origin' in columns:
            if row[columns.index('country_of_origin')] is None:
                for idx in range(1,5):
                    row.insert(columns.index('country_of_origin')+idx, '')
            else:
                for idx in range(1,5):
                    row.insert(columns.index('country_of_origin')+idx, row[columns.index('country_of_origin')][idx])
                row[columns.index('country_of_origin')]= str(row[columns.index('country_of_origin')][0])
        if 'cv_attribute' in columns:
            if row[columns.index('cv_attribute')] is None:
                row.insert(columns.index('cv_attribute')+1, None)
            else:
                row.insert(columns.index('cv_attribute')+1, row[columns.index('cv_attribute')][1])
                row[columns.index('cv_attribute')]= str(row[columns.index('cv_attribute')][0])
        #reformat number of reads
        if 'nber_reads' in columns and row[columns.index('nber_reads')] is not None:
            row[columns.index('nber_reads')]= str(format(row[columns.index('nber_reads')],"*>3,d"))
        #get the image details
        row=['' if x is None else x for x in row]
        if columns[0]=='individual_id':
            columns[1]="supplier_name"
            curs = mysql.connection.cursor()
            curs.execute("SELECT filepath, filename FROM image WHERE individual_id= '{id}';". format(id=row[0]))
            im_res=curs.fetchall()
            curs.close()
            if im_res:
                row.append("/".join(list(im_res[0])))
            else:
                row.append('')
            if 'thumbnail' not in columns: columns.append('thumbnail')
        #add to columns and row if there is an image path
        list_new_data.append(tuple(row))
    #to display the vertical individual table
    if columns[0]=='individual_id' and len(columns) > 13:
        #to display all the annotations for individual
        columns, list_new_data = reformat_comment(columns, list_new_data)
        #reorder if there is several entries for same individual by latest and reverse date
        list_new_data = reorder_for_vertical_display(list_new_data)
    return tuple(columns), tuple(list_new_data)

def reorder_for_vertical_display(data):
    """re-order the entries according to their uniqueness, latest field and changed date"""
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
    #extract the individual_id with only one index
    single_dic={ k:v for k,v in id_dic.items() if len(v)==1 }
    for key in single_dic:
        new_data.append(data[id_dic[key][0]])
    for key in multiple_dic:
        #reorder the ones with more than one index
        new_dic={}
        for idx in range(0, len(id_dic[key])):
            #get the value of latest field for this multiple_dic key (individual_id)
            latest=data[id_dic[key][idx]][18]
            #get the value of changed field for this multiple_dic key (individual_id)
            changed=data[id_dic[key][idx]][17]
            #create dictionary with latest as key and tuple(s) as value(s) if latest=0
            if latest ==1:
                new_data.append(data[id_dic[key][idx]])
            else:
                new_dic[changed]=data[id_dic[key][idx]]
        #rearrange to sort according to changed date
        for key in reversed(sorted(new_dic)):
            new_data.append(new_dic[key])
    return new_data

def reformat_comment(col, data):
    """ensure that all comments associated to an entry are displayed"""
    dic_ind_id ={}
    new_data=[]
    index=-1
    for entry in data:
        index+=1
        list_data=list(entry)
        #only display the concatenated comments for the latest data
        if list_data[18]==1:
            if list_data[1] in dic_ind_id:
                previous_data=list(data[dic_ind_id[list_data[1]]])
                #add the headers to columns and insert data from previous record [16 is index of latest field]
                for i in range(19,24):
                        col.insert(len(col)-1, col[i])
                        previous_data.insert(len(previous_data)-1, list_data[i])
                #remove previous entry for this individual_id
                new_data = new_data[:-1]
            else:
                #if not already encountered, then add tp dictionary
                dic_ind_id[list_data[1]]=index
                previous_data =list_data
        else:
            previous_data=list_data
        new_data.append(previous_data)
    for entry in new_data:
        #ensure that all lines have the same length than 'columns'
        if len(entry) != len(col):
            for i in range(0, len(col)-len(entry)):
                entry.insert(len(entry)-1,'')
    return(col, new_data)

def add_data_to_tuple(old_tuple, new_data):
    """create new_tuple by adding new_data to previous tuple"""
    old_list=list(old_tuple[0])
    #ensure that new_data is a list
    if isinstance(new_data, tuple):
        new_list=list(new_data[0])
    else:
        new_list=list(new_data)
    #concatenate lists
    new_list += old_list
    return tuple(new_list)

def transpose_table(col, data):
    """transpose data from horizontal display to vertical one"""
    new_data=[]
    l=[]
    nl=[]

    #get the index from column list
    for index in range(1,len(col)):
        #get header
        new_list=[col[index]]
        #get corresponding data and append it to column header
        for entry in data:
            new_list.append(entry[index])
        #only keep info if there is data to display
        if new_list.count(None)!=len(data) and new_list.count('None')!=len(data) and new_list.count('')!=len(data):
            new_data.append(new_list)
            l.append(index)
        else:
            nl.append(index)
    index_col=[]
    if col[0]=='individual_id':
        if len([i for i in l if i>5 and i<11 ]) >0:
            index_col.append(min([i for i in l if i>5 and i<11 ]))
        if len([i for i in l if i>11 and i<17]) >0:
            index_col.append(min([i for i in l if i>11 and i<17]))
        if len([i for i in l if i>16 and i<19]) >0:
            index_col.append(min([i for i in l if i>16 and i<19 ]))
        if len([i for i in l if i>18 and i<24]) >0:
            index_col.append(min([i for i in l if i>18 and i<24 ]))
        if 11 in l:
            index_col.append(11)
    elif col[0]=='file_id':
        if len([i for i in l if i>4 and i<8 ]) >0:
            index_col.append(min([i for i in l if i>4 and i<8 ]))
        if len([i for i in l if i>8 and i<11]) >0:
            index_col.append(min([i for i in l if i>8 and i<11]))
        if 8 in l:
            index_col.append(8)
    name_col=[col[x] for x in index_col]
    return new_data, name_col

def remove_column(original_tuple, col_idx):
    """remove column from all elements from tuple according to index input"""
    if col_idx == 1:
        new_list=[x[1:] for x in list(original_tuple)]
    #use 'L' as length of elements is not always known, otherwise could provide this value to remove the last column
    elif col_idx == "L" :
        new_list=[x[:-1] for x in list(original_tuple)]
    else:
        new_list=[x[:col_idx -1]+x[col_idx:] for x in list(original_tuple)]
    return (tuple(new_list))

@app.route('/')
@app.route('/index', methods=['GET', 'POST'])
def index():
    """main function for the main page where user can choose the way to interrogate the database"""
    project_acc=""
    individual_name=""
    flag=""
    list_proj=[]
    list_loc =[]
    if 'usrname' not in session:
        session['usrname']=""
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT accession, name FROM project")
        prows=curs.fetchall()
    except:
        flash ("Error: unable to fetch projects")
    try:
        curs.execute("SELECT distinct location FROM location")
        lrows=curs.fetchall()
    except:
        flash ("Error: unable to fetch location information")
    curs.close()
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
        loc_r=""
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
            loc_r=details['loc_choice']
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
        ,'L': loc_r, 'AL': [project_acc.split(" - ")[0], loc_r], 'IL' : [individual_name, loc_r],
        'SL': [species_name,loc_r], 'IS':[individual_name, species_name], 'X': sample_name,
        'SX':[sample_name, species_name], 'AX':[sample_name, project_acc.split(" - ")[0]],
        'IX' : [sample_name, individual_name], 'XL' : [sample_name, loc_r]}
        if flag == 'A':
            return redirect(url_for(url_dic[flag], accession=arg_dic[flag]))
        elif flag == 'AI':
            return redirect(url_for(url_dic[flag], accession=arg_dic[flag][0], ind_name=arg_dic[flag][1]))
        elif flag == 'AS':
                return redirect(url_for(url_dic[flag], accession=arg_dic[flag][0], sp_name=arg_dic[flag][1]))
        elif flag=='I':
            return redirect(url_for(url_dic[flag], ind_name= individual_name))
        elif flag=='IS':
            return redirect(url_for(url_dic[flag], ind_name= individual_name, sp_name=arg_dic[flag][1]))
        elif flag=='S':
            return redirect(url_for(url_dic[flag], sp_name=species_name))
        elif flag =='L':
            return redirect(url_for(url_dic[flag], location=loc_r))
        elif flag =='SL':
            return redirect(url_for(url_dic[flag], location=arg_dic[flag][1], sp_name=arg_dic[flag][0]))
        elif flag =='IL':
            return redirect(url_for(url_dic[flag], location=arg_dic[flag][1], ind_name=arg_dic[flag][0]))
        elif flag =='AL':
            return redirect(url_for(url_dic[flag], location=arg_dic[flag][1], accession=arg_dic[flag][0]))
        elif flag =='X':
            return redirect(url_for(url_dic[flag], sname=sample_name))
        elif flag =='XL':
            return redirect(url_for(url_dic[flag], sname=sample_name, location=loc_r))
        elif flag =='IX':
            return redirect(url_for(url_dic[flag], sname=sample_name, ind_name=individual_name))
        elif flag =='SX':
            return redirect(url_for(url_dic[flag], sname=sample_name, sp_name=species_name))
        elif flag =='AX':
            return redirect(url_for(url_dic[flag], sname=sample_name, accession=arg_dic[flag][-1]))
        else:
            return redirect(url_for('index'))
            flash("Please enter valid criteria")
    return render_template("entry.html", title='Query was: returnall', form=form, project_list=tuple(list_proj), loc_list=tuple(list_loc))

@app.route('/login/', methods=['GET', 'POST'])
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
            flash ("Error: unable to fetch items")
        curs.close()
        if len(rows) == 0:#if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        #login_user(user, remember=form.remember_me.data)
        else :
            compare = verify_password(rows[0][3], details['password'])
            if compare:
                session['usrname']=rows[0][1]
                session['logged_in']=True
                return redirect(url_for('enter_data'))
            else:
                flash('Invalid password provided')
                return redirect(url_for('login'))
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout/')
def logout():
    """function to logout"""
    logout_user()
    session['usrname']=""
    return redirect(url_for('index'))

@app.route('/register/', methods=['GET', 'POST'])
def register():
    """function for the main page where user can choose the way to interrogate the database"""
    try:
        form = RegistrationForm(request.form)
        if request.method == "POST" and form.validate():
            username  = form.username.data
            email = form.email.data
            password = hash_password(form.password.data)
            curs = mysql.connection.cursor()
            x = curs.execute("SELECT * FROM users WHERE username = '{user}';".format(user=username))
            if int(x) > 0:
                flash("That username is already taken, please choose another")
                return render_template('register.html', form=form)
            else:
                curs.execute("INSERT INTO users (username, password, email) VALUES ('{user}', '{psw}', '{eml}')".
                          format(user=username, psw=password, eml=email))
                if email in ('had38@cam.ac.uk','sam68@cam.ac.uk','tylerp.linderoth@gmail.com','ib400@cam.ac.uk','bef22@hermes.cam.ac.uk','rd109@cam.ac.uk','gv268@cam.ac.uk', 'es754@cam.ac.uk') :
                    curs.execute("commit")
                    flash("Thanks for registering!")
                    return redirect(url_for('login'))
                else:
                    msg = Message(body='username: '+username+'\nemail: '+email+'\npassword: '+password, subject = 'New registration', sender ='had38@cam.ac.uk', recipients = ['had38@cam.ac.uk'])
                    mail.send(msg)
                    return redirect(url_for('index'))
                    flash("Thanks for registering: your registration is now pending approval")
                curs.close()
    except Exception as e:
        return("Issue: "+str(e))
    return render_template('register.html', title='Register', form=form)


@app.route('/api/1.0/entry/', methods=['GET', 'POST'])
def enter_data():
    """function for the entry page where user can update, overwrite or enter new data in the database"""
    usrname=session.get('usrname', None)
    form = EnterDataForm(request.form)
    provider_list=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT provider_name FROM provider")
        provider_res=curs.fetchall()
    except:
        flash ("Error: unable to fetch provider names")
    curs.close()
    for prov in provider_res:
        provider_list.append(prov[0])
    provider_list.append("-current providers-")
    if request.method == "POST" and form.validate():
        results=request.form
        if 'Download' in results:
            return redirect(url_for('download'))
        elif 'Upload' in results:
            return redirect(url_for('upload', file = results['Upload']))
        else:
            return redirect(url_for('enter_data'))
    return render_template('enter_data.html', title='Signed in as: '+usrname, form=form, prov_list=tuple(provider_list))

@app.route('/api/1.0/download/', methods=['GET', 'POST'])
def download():
    """function to provide the csv template to enter data"""
    return send_file("entry.csv",
        mimetype="text/csv",
        attachment_filename='entry.csv',
                     as_attachment=True)

@app.route('/api/1.0/upload/<file>', methods=['GET', 'POST'])
def upload(file):
    """function to reupload the filled csv template to add, update or overwrite the database"""
    f = open(file, 'r')
    #only keep lines with data
    File = [line.rstrip('\n') for line in f if len(line.split(",")[0]) > 0]
    flash ('file uploaded successfully')
    return redirect(url_for('index'))

##############functions related to the API below this line####################################

@app.route('/api/1.0/file/<la_id>', methods=['GET'])
def get_files_per_lane_id(la_id):
    id_results=[]
    results=[]
    lcolumns=get_columns_from_table('file')
    columns=tuple([lcolumns[1]]+[lcolumns[3]]+[lcolumns[2]]+list(lcolumns[4:]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT f.*, l.accession FROM file f join lane l on f.lane_id=l.lane_id where f.latest=1 and f.lane_id = '%s';" % la_id)
        fresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch files")
    for row in fresults:
        f_results=[row[1]]+[row[3]]+[row[2]]+list(row[4:])
        l_accession=row[-1]
        results.append(f_results)
    curs.close()
    new_column, display_results= change_for_display(columns, results)
    new_columns= list(new_column)
    new_columns[5]='file_type'
    v_display_results, split_col=transpose_table(new_columns, display_results)
    return render_template("mysqlV.html", title='Query was: file(s) where lane_accession = "' + str(l_accession)+'"', view_param=split_col, results=[v_display_results])

@app.route('/api/1.0/images/', methods=['GET'])
def get_images():
    id_results=[]
    results=[]
    columns=get_columns_from_table('image')
    col=[columns[0]]+[columns[2]]+[columns[1]]+['thumbnail']+list(columns[3:])
    columns=tuple(col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM image where latest=1")
        img_results=curs.fetchall()
    except:
        flash ("Error: unable to fetch images")
    curs.close()
    for row in img_results:
        i_results=[row[0]]+[row[2]]+[row[1]]+list([row[3]+"/"+row[2]])+list(row[3:])
        results.append(i_results)
    new_column, display_results= change_for_display(columns, results)
    return render_template("image.html", title='Query was: all images', url_param=['individual', 2, '/'], results=[new_column,display_results])

@app.route('/api/1.0/individual/', methods=['GET'])
def get_individuals():
    icolumns=get_columns_from_table('individual')
    columns=icolumns[1:7]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM individual where latest=1")
        results=curs.fetchall()
    except:
        flash ("Error: unable to fetch individuals")
    curs.close()
    result=remove_column(results, 1)
    results=tuple([x[:6] for x in list(result)])
    new_columns, display_results= change_for_display(columns, results)
    return render_template("mysql.html", title='Query was: all individuals', url_param=['individual', 0, ''], results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/individual/<i_id>', methods=['GET'])
def get_individual_per_individual_id(i_id):
    columns=get_columns_from_table('individual')
    id_columns=get_columns_from_table('individual_data')
    results=[]
    all_results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM individual i left join individual_data id on id.individual_id=i.individual_id where i.individual_id = '{identif}';". format(identif=i_id))
        i_results=curs.fetchall()
    except:
        flash ("Error: unable to fetch individuals")
    curs.close()
    for row in i_results:
        i_results=list(row[1:16])+list(row[18:22])
        if row[15]==1:
            results.append(i_results)
        all_results.append(i_results)
        #1 display results
    if len(results) > len(all_results):
        #1 display button on mysqlV
        #2 if button clicm:
        results=all_results
    new_column, display_results= change_for_display(columns[1:]+id_columns[2:6], results)
    new_columns=list(new_column)
    v_display_results, split_col=transpose_table(new_columns, display_results)
    return render_template("mysqlV.html", title='Query was: individual = "' + str(results[0][1]) +'"', view_param=split_col, results=[v_display_results]) #form=form)

@app.route('/api/1.0/individual/<ind_name>/', methods=['GET'])
def get_individual_per_individual_name(ind_name):
    ind_list=ind_name.replace(" ","").replace(",", "','")
    columns=get_columns_from_table('individual')
    id_columns=get_columns_from_table('individual_data')
    results=[]
    all_results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM individual i left join individual_data id on i.individual_id=id.individual_id where i.name in ('{identif}') or i.alias in ('{identif}') ". format(identif=ind_list))
        iresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch individuals")
    curs.close()
    if len(iresults) > 0:
        for row in iresults:
            i_results=list(row[1:16])+list(row[18:22])
            if row[15] ==1:
                results.append(i_results)
            all_results.append(i_results)
        if len(all_results) > len(results):
            results=all_results
        new_columns, display_results= change_for_display(columns[1:]+id_columns[2:6], results)
        v_display_results, split_col=transpose_table(new_columns, display_results)
    else:
        flash("unable to fetch the individual(s)")
        return redirect(url_for('index'))
    return render_template("mysqlV.html", title='Query was: individual = "' + str(ind_name) +'"', view_param=split_col, results=[v_display_results])

@app.route('/api/1.0/individual/<ind_name>/species/<sp_name>', methods=['GET'])
def get_individual_per_name_and_species_name(ind_name, sp_name):
    results=[]
    ind_list=ind_name.replace(" ","").replace(",", "','")
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT i.* FROM individual i join species s on i.species_id=s.species_id WHERE s.name like '%%{spn}%%' and (i.name in ('{i_l}') or i.alias in ('{i_l}'));". format(spn=sp_name, i_l=ind_list))
        res=curs.fetchall()
    except:
        flash ("Error: unable to fetch items")
    if len(res)==0:
        flash('No individual with the criteria provided')
        return redirect(url_for('index'))
    results=tuple([x[1:8] for x in list(res)])
    new_columns, display_results = change_for_display(columns[1:8], results)
    #remove the thumbnail field for display
    display_results=tuple([x[:-1] for x in list(display_results)])
    return render_template("mysql.html", title='Query was : individual(s) where individual name = "'+str(ind_name)+'" & species like "'+str(sp_name)+ '"', url_param=['individual', 0], results=[new_columns[:-1], display_results])

@app.route('/api/1.0/lane/', methods=['GET'])
def get_lanes():
    id_results=[]
    results=[]
    lcolumns=get_columns_from_table('lane')
    columns=list(lcolumns[:2])+[lcolumns[7]]+[lcolumns[6]]+list(lcolumns[2:6]) +list(lcolumns[8:])
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM lane where latest=1")
        lresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch lanes")
    lresults=remove_column(lresults, 1)
    curs.close()
    for row in lresults:
        id_results=list(row[:1])+[row[6]]+[row[5]]+list(row[1:5])+list(row[7:])
        results.append(id_results)
    new_column, display_results= change_for_display(columns[1:], results)
    return render_template("mysql.html", title='Query was: all lanes', url_param=['file', 0,], results=[new_column, display_results])

@app.route('/api/1.0/lane/<spl_id>', methods=['GET'])
def get_lanes_per_sample_id(spl_id):
    id_results=[]
    results=[]
    lcolumns=get_columns_from_table('lane')
    columns=tuple([lcolumns[1]]+[lcolumns[7]]+[lcolumns[6]]+list(lcolumns[3:6])+list(lcolumns[8:]))
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT l.*, s.name FROM lane l join sample s on s.sample_id=l.sample_id where l.latest=1 and l.sample_id = '%s';" % spl_id)
        lresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch lanes")
    for row in lresults:
        l_results=[row[1]]+[row[7]]+[row[6]]+list(row[3:6])+list(row[8:-1])
        results.append(l_results)
    curs.close()
    new_column, display_results= change_for_display(columns, results)
    new_columns= list(new_column)
    new_columns[5]='library_accession'
    return render_template("mysql.html", title='Query was: lane(s) where sample_name = "' + str(row[-1])+'"', url_param=['file', 0,], results=[new_columns, display_results])

@app.route('/api/1.0/location/', methods=['GET'])
def get_location():
    loc_columns=get_columns_from_table('location')
    columns=list(loc_columns)
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM location")
        l_results=curs.fetchall()
    except:
        flash ("Error: unable to fetch locations")
    for row in l_results:
        row=['' if x is None else x for x in row]
        results.append(row)
    curs.close()

    return render_template("mysql.html", title='Query was: all locations', url_param=['location',0,'/individual'], results=[columns,results])

@app.route('/api/1.0/location/<loc_id>/individual/', methods=['GET'])
def get_individual_per_location_id(loc_id):
    columns=get_columns_from_table('individual')[1:]
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT i.*, l.location, l.sub_location FROM individual i join location l on i.location_id=l.location_id where l.location_id = '%s' and i.latest=1;" % loc_id)
        res=curs.fetchall()
        iresults=remove_column(res, 1)
    except:
        flash ("Error: unable to fetch individuals")
    curs.close()
    for row in iresults:
        results.append(list(row[:7]))
        if row[-2] is not None:
            loc_name=row[-2]+", "+row[-1]
        else: loc_name=row[-1]
    new_columns, display_results = change_for_display(columns[:7], results)
    return render_template("mysql.html", title='Query was: individual(s) where location = "' + str(loc_name) +'"', url_param=['individual', 0,], results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/location/<location>', methods=['GET'])
def get_individual_per_location(location):
    loc_columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT I.* FROM individual I join location L on L.location_id = I.location_id \
        where L.location = '%s';" % location)
        res=curs.fetchall()
    except:
        flash ("Error: unable to fetch location")
    curs.close()
    results=tuple([x[1:8] for x in list(res)])
    new_columns, display_results= change_for_display(loc_columns[1:8], results)
    return render_template("mysql.html", title='Query was: individual(s) where location = "'+ location +'"', url_param=['individual', 0, ''],results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/location/<location>/individual/<ind_name>', methods=['GET'])
def get_individual_per_name_and_per_location(location, ind_name):
    loc_columns=get_columns_from_table('individual')
    columns=loc_columns[1:8]
    ind_list=ind_name.replace(" ","").replace(",", "','")
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT I.* FROM individual I join location L on L.location_id = I.location_id \
        join species S on S.species_id = I.species_id where L.location = '{reg}' and (I.name in ('{indl}') or I.alias in ('{indl}')) ;". format(reg=location, indl=ind_list))
        res=curs.fetchall()
    except:
        flash ("Error: unable to fetch location and / or individual")
    curs.close
    results=tuple([x[1:8] for x in list(res)])
    new_columns, display_results= change_for_display(columns, results)
    return render_template("mysql.html", title='Query was: individual(s) where location = "'+ location +'" and individual name = "'+ind_name+'"', url_param=['individual', 0, ''], results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/location/<location>/species/<sp_name>', methods=['GET'])
def get_species_per_name_and_per_location(location, sp_name):
    loc_columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT I.* FROM individual I join location L on L.location_id = I.location_id \
        join species S on S.species_id = I.species_id where L.location = '{reg}' and S.name like '%%{spn}%%';". format(reg=location, spn=sp_name))
        res=curs.fetchall()
    except:
        flash ("Error: unable to fetch location and / or species")
    curs.close()
    results=tuple([x[1:8] for x in list(res)])
    new_columns, display_results= change_for_display(loc_columns[1:8], results)
    return render_template("mysql.html", title='Query was: individual(s) where location = "'+ location +'" and species_name like "'+sp_name+'"', url_param=['individual', 0, ''], results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/material/', methods=['GET'])
def get_material():
    scolumns=get_columns_from_table('material')
    columns=tuple([scolumns[1]])+tuple([scolumns[4]])+scolumns[2:4]+tuple([scolumns[12]])+scolumns[5:12]+scolumns[13:]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT material_id, name, individual_id, accession, developmental_stage_id, provider_id, date_received, \
        storage_condition, storage_location, type, volume, concentration, organism_part_id, changed, \
        latest FROM material where latest=1")
        results=curs.fetchall()
    except:
        flash ("Error: unable to fetch materials")
    curs.close
    new_columns, display_results= change_for_display(columns, results)
    return render_template("mysql.html", title='Query was: all materials', url_param=['sample',0], results=[new_columns, display_results])

@app.route('/api/1.0/project/', methods=['GET'])
def get_projects():
    columns=get_columns_from_table('project')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM project")
        results=curs.fetchall()
    except:
        flash ("Error: unable to fetch projects")
    curs.close()
    return render_template("mysql.html", title='Query was: all projects', url_param=['project', 3, ], results=[columns,results])

@app.route('/api/1.0/project/<accession>', methods=['GET'])
def get_project_per_accession(accession):
    results=[]
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM individual WHERE individual_id in (select individual_id from allocation a join project p \
        where p.project_id  = a.project_id and p.accession = '%s') and latest=1;" % accession)
        results=curs.fetchall()
    except:
        flash ("Error: unable to fetch items")
    curs.close()
    columns = columns[1:7]
    result=remove_column(results, 1)
    results=tuple([x[:6] for x in list(result)])
    if len(results) == 0:
        flash('Unknown project accession')
        return redirect(url_for('index'))
    new_columns, display_results= change_for_display(columns, results)
    return render_template("mysql.html", title='Query was: individual(s) where project_accession = "'+accession+'"', url_param=['individual', 0, ], results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/project/<accession>/individual/<ind_name>', methods=['GET'])
def get_individual_per_project_accession_and_name(accession, ind_name):
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
        flash ("Error: unable to fetch items")
    curs.close()
    if len(result) == 0:
        flash('Unknown project accession or individual name')
        return redirect(url_for('index'))
    results=tuple([x[1:7] for x in list(result)])
    new_columns, display_results= change_for_display(columns[1:7], results)
    return render_template("mysql.html", title='Query was: individual(s) where project_accession = "'+accession+'" & individual_name = "'+ind_name +'"', url_param=['individual', 0,], results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/project/<accession>/location/<location>', methods=['GET'])
def get_project_per_accession_and_location(accession, location):
    loc_columns=get_columns_from_table('individual')
    columns=loc_columns[1:8]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT I.* FROM individual I join location L on L.location_id = I.location_id \
        join species S on S.species_id = I.species_id \
        left outer join allocation A on A.individual_id=I.individual_id \
        left outer join project P on P.project_id=A.project_id \
        where L.location = '{reg}' and P.accession = '{acc}'". format(reg=location, acc=accession))
        res=curs.fetchall()
    except:
        flash ("Error: unable to fetch location and / or project accession")
    curs.close()
    results=tuple([x[1:8] for x in list(res)])
    new_columns, display_results= change_for_display(columns, results)
    display_results=remove_column(display_results, 'L')
    return render_template("mysql.html", title='Query was: individual(s) where location = "'+ location +'" and project_accession = "'+accession+'"', url_param=['individual', 0, ''], results=[new_columns[:-1], display_results])

@app.route('/api/1.0/project/<accession>/species/<sp_name>', methods=['GET'])
def get_individual_per_project_accession_and_species(accession, sp_name):
    results=()
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM individual WHERE individual_id in (select individual_id from allocation a join project p \
        where p.project_id  = a.project_id and p.accession = '{acc}') and species_id in (select species_id from species where \
         name like '%%{spn}%%') and latest=1;". format(acc=accession, spn=sp_name))
        result=curs.fetchall()
    except:
        flash ("Error: unable to fetch items")
    curs.close()
    if len(result) == 0:
        flash('Unknown project accession, species name or no corresponding results')
        return redirect(url_for('index'))
    results=tuple([x[1:7] for x in list(result)])
    new_columns, display_results = change_for_display(columns[1:7], results)
    return render_template("mysql.html", title='Query was: individual(s) where project_id = "'+accession+'" & species like = "'+sp_name+'"', url_param=['individual', 0, ''], results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/provider/', methods=['GET'])
def get_provider():
    columns=get_columns_from_table('provider')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM provider where latest=1")
        results=curs.fetchall()
    except:
        flash ("Error: unable to fetch provider")
    curs.close()
    return render_template("mysql.html", title='Query was: all providers', url_param=['provider', 0, '/individual' ], results=[columns,results])

@app.route('/api/1.0/provider/<p_id>/individual', methods=['GET'])
def get_individual_by_provider(p_id):
    columns=get_columns_from_table('individual')
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT i.*, p.provider_name FROM individual i right join provider p on p.provider_id=i.provider_id where i.latest=1 and p.provider_id ='%s';" % p_id)
        result=curs.fetchall()
    except:
        flash ("Error: unable to fetch individual")
    curs.close()
    results=tuple([x[1:7] for x in list(result) if x[1] is not None])
    new_columns, display_results = change_for_display(columns[1:7], results)
    return render_template("mysql.html", title='Query was: individuals from provider ="' + result[0][-1]+'"', url_param=['individual', 0,  ], results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/sample/', methods=['GET'])
def get_samples():
    id_results=[]
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["individual_id"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM sample where latest=1")
        sresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch samples")
    for row in sresults:
        try:
            curs.execute("SELECT i.individual_id from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s' ;" % row[2])
            id_return=curs.fetchall()
        except:
            flash ("Error: unable to fetch items")
        id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
        results.append(tuple(id_results))
    curs.close()
    new_columns, display_results= change_for_display(columns, results)
    return render_template("mysql.html", title='Query was: all samples', url_param=['lane', 0, ''], results=[new_columns,display_results])

@app.route('/api/1.0/sample/<m_id>', methods=['GET'])
def get_samples_per_material_name(m_id):
    id_results=[]
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["individual_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM sample where material_id = '%s' ;" % m_id)
        sresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch samples")
    if len(sresults) > 0:
        for row in sresults:
            try:
                curs.execute("SELECT i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
        curs.close()
    else:
        flash("no sample associated with this material name")
        return redirect(url_for('index'))
    return render_template("mysql.html", title='Query was: sample(s) where material_name = "' +str(m_name)+'"', url_param=['lane', 0,], results=[columns,results])

@app.route('/api/1.0/sample/<sname>/', methods=['GET'])
def get_samples_by_name(sname):
    s_list=sname.replace(" ","").replace(",", "','")
    id_results=[]
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM sample where latest=1 and name in ('{slist}') or accession in ('{slist}');".format(slist=s_list))
        sresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch samples")
    if len(sresults) > 0:
        for row in sresults:
            try:
                curs.execute("SELECT i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
        curs.close()
    else:
        flash("no sample associated with this/these sample name(s)")
        return redirect(url_for('index'))
    return render_template("mysql.html", title='Query was: sample(s) where sample_name  = "' +sname+'"', url_param=['lane', 0,], results=[columns,results])

@app.route('/api/1.0/sample/<sname>/individual/<ind_name>', methods=['GET'])
def get_samples_by_sample_name_and_individual_name(sname, ind_name):
    s_list=sname.replace(" ","").replace(",", "','")
    ind_list=ind_name.replace(" ","").replace(",", "','")
    id_results=[]
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select s.* from sample s join material m on m.material_id = s.material_id join individual i on i.individual_id=m.individual_id where s.latest=1 and (i.name in ('{ind_list}') \
         or i.alias in ('{ind_list}')) and (s.accession in ('{s_list}') or s.name in ('{s_list}'));".format(ind_list=ind_list, s_list=s_list))
        sresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch samples with these criteria")
    if len(sresults) > 0:
        for row in sresults:
            try:
                curs.execute("SELECT i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
        curs.close()
    else:
        flash("no sample associated with this/these sample name(s)")
        return redirect(url_for('index'))
    return render_template("mysql.html", title='Query was: sample(s) where sample_name  = "' +sname+'" and individual_name ="'+ind_name+'"', url_param=['lane', 0,], results=[columns,results])

@app.route('/api/1.0/sample/<sname>/location/<location>', methods=['GET'])
def get_samples_by_sample_name_and_location(sname, location):
    s_list=sname.replace(" ","").replace(",", "','")
    id_results=[]
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select s.* from sample s join material m on m.material_id = s.material_id join individual i \
        on i.individual_id=m.individual_id left join location l on l.location_id=i.location_id where s.latest=1 \
        and (s.accession in ('{s_list}') or s.name in ('{s_list}')) and l.location='{loc}';".format(loc=location, s_list=s_list))
        sresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch samples with these criteria")
    if len(sresults) > 0:
        for row in sresults:
            try:
                curs.execute("SELECT i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
        curs.close()
    else:
        flash("no sample associated with this/these sample name(s) and location")
        return redirect(url_for('index'))
    return render_template("mysql.html", title='Query was: sample(s) where sample_name  = "' +sname+'" and location ="'+location+'"', url_param=['lane', 0,], results=[columns,results])

@app.route('/api/1.0/sample/<sname>/project/<accession>', methods=['GET'])
def get_samples_by_sample_name_and_project(sname, accession):
    s_list=sname.replace(" ","").replace(",", "','")
    id_results=[]
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select s.* from sample s join material m on m.material_id = s.material_id join individual i \
    on i.individual_id=m.individual_id left join allocation a on a.individual_id=i.individual_id join project p \
    on p.project_id=a.project_id where s.latest=1 and (s.accession in ('{s_list}') or s.name in ('{s_list}')) \
    and p.accession='{acc}';".format(acc=accession, s_list=s_list))
        sresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch samples with these criteria")
    if len(sresults) > 0:
        for row in sresults:
            try:
                curs.execute("SELECT i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
        curs.close()
    else:
        flash("no sample associated with this/these sample name(s) and project accession")
        return redirect(url_for('index'))
    return render_template("mysql.html", title='Query was: sample(s) where sample_name  = "' +sname+'" and project ="'+accession+'"', url_param=['lane', 0,], results=[columns,results])


@app.route('/api/1.0/sample/<sname>/species/<sp_name>', methods=['GET'])
def get_samples_by_sample_name_and_species(sname, sp_name):
    s_list=sname.replace(" ","").replace(",", "','")
    id_results=[]
    results=[]
    scolumns=get_columns_from_table('sample')
    col=tuple([scolumns[1]]+[scolumns[5]]+["supplier_name"]+list(scolumns[3:4])+list(scolumns[6:]))
    updated_col=col
    columns=tuple(updated_col)
    curs = mysql.connection.cursor()
    try:
        curs.execute("select s.* from sample s join material m on m.material_id = s.material_id join individual i \
        on i.individual_id=m.individual_id left join species sp on sp.species_id=i.species_id where s.latest=1 \
        and (s.accession in ('{s_list}') or s.name in ('{s_list}')) and sp.name like '{sp}%';".format(sp=sp_name, s_list=s_list))
        sresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch samples with these criteria")
    if len(sresults) > 0:
        for row in sresults:
            try:
                curs.execute("SELECT i.name, i.individual_id, m.name from material m join individual i on i.individual_id=m.individual_id where m.material_id = '%s';" % row[2])
                id_return=curs.fetchall()
            except:
                flash ("Error: unable to fetch items")
            id_results=[row[1]]+[row[5]]+[id_return[0][0]]+list(row[3:4])+list(row[6:])
            results.append(tuple(id_results))
            m_name=id_return[0][2]
        curs.close()
    else:
        flash("no sample associated with this/these sample name(s) and species")
        return redirect(url_for('index'))
    return render_template("mysql.html", title='Query was: sample(s) where sample_name  = "' +sname+'" and species like "'+sp_name+'"', url_param=['lane', 0,], results=[columns,results])

@app.route('/api/1.0/species/', methods=['GET'])
def get_species():
    scolumns=get_columns_from_table('species')
    columns=scolumns[1:]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM species where latest=1")
        results=curs.fetchall()
    except:
        flash ("Error: unable to fetch species")
    curs.close()
    results=remove_column(results, 1)
    new_columns, display_results= change_for_display(columns, results)
    return render_template("mysql.html", title='Query was: all species', url_param=['species/tax_id',3, ], results=[new_columns, display_results])

@app.route('/api/1.0/species/<sp_id>/individual/', methods=['GET'])
def get_individual_per_species_name(sp_id):
    columns=get_columns_from_table('individual')[1:8]
    results=[]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT i.*, s.name FROM individual i join species s on i.species_id=s.species_id where i.latest=1 and s.species_id = '%s';" % sp_id)
        sresults=curs.fetchall()
    except:
        flash ("Error: unable to fetch individuals")
    curs.close
    for row in sresults:
        s_results=list(row)[1:8]
        sname=row[-1]
        results.append(s_results)
    new_columns, display_results = change_for_display(columns, results)
    return render_template("mysql.html", title='Query was: individual(s) where species = "' + str(sname) +'"', url_param=['individual', 0, ], results=[new_columns[:-1], remove_column(display_results, 'L')])

@app.route('/api/1.0/species/<sp_name>', methods=['GET'])
def get_species_per_name(sp_name):
    results=tuple()
    scolumns=get_columns_from_table('species')
    columns=scolumns[1:]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT * FROM species where latest=1 and name like '%%%s%%'" % sp_name)
        results=curs.fetchall()
    except:
        flash ("Error: unable to fetch species")
    curs.close()
    results=remove_column(results, 1)
    new_columns, display_results= change_for_display(columns, results)
    return render_template("mysql.html", title='Query was: all species where name contains "' + sp_name +'"', url_param=['species', 0, '/individual'],results=[new_columns,display_results])

@app.route('/api/1.0/species/tax_id/<tax_id>', methods=['GET'])
def get_individual_per_tax_id(tax_id):
    results=tuple()
    scolumns=get_columns_from_table('individual')
    columns=scolumns[1:]
    curs = mysql.connection.cursor()
    try:
        curs.execute("SELECT i.* FROM individual i join species s on s.species_id=i.species_id where s.taxon_id = '%s' and i.latest=1" % tax_id)
        results=curs.fetchall()
    except:
        flash ("Error: unable to fetch species")
    curs.close()
    results=remove_column(results, 1)
    new_columns, display_results= change_for_display(columns, results)
    return render_template("mysql.html", title='Query was: individual(s) where taxon_id = "' + tax_id +'"', url_param=['individual', 0,], results=[new_columns[:-1], remove_column(display_results, 'L')])

if __name__ == "__main__":
    app.run(debug=True)
