from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, RadioField, SelectField, IntegerField, FloatField, DateField, validators
from wtforms.validators import DataRequired, ValidationError, Email, EqualTo
from flask_login import UserMixin
import datetime

class LoginForm(FlaskForm):
    '''
    section describing the entries for the login form
    '''
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    '''
    section describing the entries for the registration form
    '''
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class EntryForm(FlaskForm):
    '''
    section describing the entries for the home page entry form
    '''
    name = StringField('and / or provide individual name(s) or alias(es) (comma separated)')
    spname = StringField('and / or provide a species name (partial name accepted)')
    sname = StringField('and / or provide a sample name(s) or accession(s) (comma separated)')
    submit = SubmitField('Search database')

class EnterDataForm(FlaskForm):
    '''
    section describing the entries for the enter data form
    '''
    Gender = RadioField('Gender', validators = (validators.Optional(),), choices = [('M','Male'), ('F','Female')])
    Option= SelectField('Choose entry type: ', choices = [('nwd', 'new_data'), ('upd', 'update'), ('ovw', 'overwrite')])
    ind_name = StringField('Individual name: ')
    ind_alias = StringField('Individual alias: ')
    dev_stage= SelectField('Developmental stage: ', choices = [('unk', 'unknown'), ('juv', 'juvenile'), ('adt', 'adult'), ('fry', 'fry'), ('gra', 'gravid')])
    sp_name = StringField('Species name: ')
    sp_taxid = IntegerField('Taxon_id: ', [validators.Optional()])
    sp_cname = StringField('Species common name: ')
    sp_taxpos = SelectField('Taxon position :', choices = [('unk', 'unknown'), ('sp', 'species'), ('ord', 'order'), ('cla', 'class'), ('fam', 'family'), ('gen', 'genus'), ('phy', 'phylum'), ('kin', 'kindom')])
    mat_name = StringField('Material name: ')
    mat_acc = StringField('Material accession: ')
    mat_type= SelectField('Material type: ', choices=[('dna', 'gDNA'), ('rna', 'RNA'),  ('amp', 'amplicon')],  validators = (validators.Optional(),))
    mat_part= SelectField('Organism part: ', choices = [('unk', ''), ('fin', 'fin'), ('liv', 'liver'), ('mus', 'muscle'), ('hed', 'head'), ('bra', 'brain'), ('bod', 'body'), ('tai', 'tail'), ('gil', 'gills'),
     ('gon', 'gonads'),  ('ova', 'ovaries'), ('tes', 'testes'), ('hrt', 'heart'), ('kid', 'kidney'), ('lng', 'lung'), ('org', 'organs'), ('spl', 'spleen'), ('lim', 'limb'), ('jaw', 'jaw'), ('skn', 'skin'), ('eye', 'eye'), ('itt', 'intestine'), ('bld', 'blood'), ('anf', 'anal fin'), ('tss', 'tissue')])
    mat_cond= SelectField('Storage conditions: ', choices = [('unk',''), ('frz', 'frozen'), ('eth', 'ethanol'), ('dry', 'air dried'), ('Rlat', 'RNAlater'),('otr', 'other')])
    mat_wgt = FloatField('Material amount: ', [validators.Optional()])
    mat_unit= SelectField('    Material unit: ', choices = [('gr', 'grams'), ('ul', 'microlitre')])
    mat_location = StringField('Material location: ')
    mat_loc_pos = StringField('    Material location position: ')
    loc_collected = DateField('Date collected (YYYY-MM-DD): ', format ='%Y-%m-%d', validators = (validators.Optional(),))
    mat_received = DateField('Date received (YYYY-MM-DD): ', format ='%Y-%m-%d', validators = (validators.Optional(),))
    loc_region = StringField('Geographical region: ')
    loc_details = StringField('Source location: ')
    loc_lat = FloatField('Latitude: ', [validators.Optional()])
    loc_lng = FloatField('Longitude: ', [validators.Optional()])
    loc_method = StringField('Collection method : ')
    img_name = StringField('Image name: ')
    img_source = StringField('Image source: ')
    img_comments = StringField('Image comments: ')
    prj_name = StringField('Project name: ')
    prj_alias = StringField('Project alias: ')
    prj_acc = StringField('Project acc: ')
    prj_ssid = IntegerField('Project ssid: ' , [validators.Optional()])
    ann_ann = StringField('Annotation: ')
    ann_comments = StringField('Annotation comments: ')
    ann_cat= SelectField('Category: ', choices = [('oth', ''), ('lbn', 'labnote'), ('idv', 'individual'), ('spc', 'species'), ('mat', 'material'), ('col', 'collection'), ('stg', 'storage'), ('prj', 'project'), ('img', 'image')],  validators = (validators.Optional(),))
    pv_name = StringField('Provider name: ')
    pv_fname = StringField('First name: ')
    pv_mail = StringField('Email: ')
    pv_phone = StringField('Phone: ')
    pv_address = StringField('Address: ')
    submit = SubmitField('Submit Data')

class ViewForm(FlaskForm):
    '''
    section to choose the individual view content
    '''
    submit = SubmitField('View all individuals')
