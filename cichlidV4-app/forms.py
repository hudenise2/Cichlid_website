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

class DatabaseForm(FlaskForm):
 submit = SubmitField('Select database')


class EntryForm(FlaskForm):
 '''
 section describing the entries for the home page entry form
 '''
 name = StringField('and / or provide individual name(s) or alias(es) (comma separated)')
 spname = StringField('and / or provide a species name or common name (partial name accepted)')
 sname = StringField('and / or provide sample name(s) or accession(s) (comma separated)')
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
 mat_acc = StringField(' Material accession: ')
 mat_type= SelectField('Material type: ', choices=[('dna', 'gDNA'), ('rna', 'RNA'), ('amp', 'amplicon')], validators = (validators.Optional(),))
 mat_part= SelectField('Organism part: ', choices = [('unk', ''), ('fin', 'fin'), ('liv', 'liver'), ('mus', 'muscle'), ('hed', 'head'), ('bra', 'brain'), ('bod', 'body'), ('tai', 'tail'), ('gil', 'gills'),
 ('gon', 'gonads'), ('ova', 'ovaries'), ('tes', 'testes'), ('hrt', 'heart'), ('kid', 'kidney'), ('lng', 'lung'), ('org', 'organs'), ('spl', 'spleen'), ('lim', 'limb'), ('jaw', 'jaw'), ('skn', 'skin'), ('eye', 'eye'), ('itt', 'intestine'), ('bld', 'blood'), ('anf', 'anal fin'), ('tss', 'tissue')])
 mat_cond= SelectField('Storage conditions: ', choices = [('unk',''), ('frz', 'frozen'), ('eth', 'ethanol'), ('dry', 'air dried'), ('Rlat', 'RNAlater'),('otr', 'other')])
 mat_wgt = FloatField('Material amount: ', [validators.Optional()])
 mat_unit= SelectField(' unit: ', choices = [('gr', 'grams'), ('ul', 'microlitre')])
 mat_location = StringField('Material location: ')
 mat_loc_pos = StringField(' position: ')
 mat_comment = StringField('Comment: ')
 mat_provider = StringField(' Provider: ')
 loc_collected = DateField('Date collected (YYYY-MM-DD): ', format ='%Y-%m-%d', validators = (validators.Optional(),))
 mat_received = DateField('Date received (YYYY-MM-DD): ', format ='%Y-%m-%d', validators = (validators.Optional(),))
 loc_country = StringField('Country of origin: ')
 loc_region = StringField('Location: ')
 loc_details = StringField(' Sub-location: ')
 loc_lat = FloatField('Latitude: ', [validators.Optional()])
 loc_lng = FloatField(' Longitude: ', [validators.Optional()])
 loc_method = StringField('Collection method : ')
 loc_details = StringField(' details: ')
 loc_provider = StringField('Provider: ')
 loc_weight = StringField('Weight: ')
 loc_unit = SelectField('unit', choices = [('gr', 'grams'), ('ug', 'micrograms'), ('mg', 'milligrams'), ('kg', 'kilograms')], validators = (validators.Optional(),))
 img_name = StringField('Image name: ')
 img_source = StringField('Image path: ')
 img_licence = StringField('Image licence: ')
 img_comments = StringField('Image comments: ')
 prj_name = StringField('Project name: ')
 prj_alias = StringField('Project alias: ')
 prj_acc = StringField('Project accession: ')
 prj_ssid = IntegerField(' Project ssid: ' , [validators.Optional()])
 ann_ann = StringField('Annotation: ')
 ann_comments = StringField('Annotation comments: ')
 ann_cat= SelectField('Category: ', choices = [('oth', ''), ('lib', 'library'), ('ext', 'extraction'), ('spc', 'species'), ('col', 'collection'), ('stg', 'storage'), ('prj', 'project'), ('pro', 'processing')], validators = (validators.Optional(),))
 pv_name = StringField('Provider name: ')
 pv_fname = StringField('First name: ')
 pv_mail = StringField('Email: ')
 pv_phone = StringField('Phone: ')
 pv_address = StringField('Address: ')
 file_accession= StringField('File accession: ')
 file_comment= StringField('File comment: ')
 file_format =SelectField('File format: ', choices = [('CR', 'cram'), ('BM', 'bam'), ('FQ', 'fastq'), ('FA', 'fasta'), ('F5', 'fast5'), ('VC', 'vcf')], validators =(validators.Optional(),))
 file_md5= StringField('MD5 checksum: ')
 file_name= StringField('File name: ')
 file_path= StringField('File path: ')
 file_PE = SelectField(' Paired_end', choices=[('y', 'Y'), ('n', 'N')])
 file_reads=IntegerField(' Number of reads: ' , [validators.Optional()])
 file_length=IntegerField('Average read length: ' , [validators.Optional()])
 lane_accession= StringField(' Lane accession: ')
 lane_name= StringField('Lane name: ')
 lib_name= StringField('Library name: ')
 lib_ssid= IntegerField(' Library ssid: ' , [validators.Optional()])
 seq_centre= StringField('Sequencing centre: ')
 seq_tech = SelectField('Sequencing technology: ', choices = [('ILL', 'Illumina'), ('PCB', 'PacBio'), ('ONT', 'Oxford Nanopore'), ('ARI', 'Arima'), ('HIC', 'Hi-C'), ('RNS', 'RNA-Seq'), ('OTH', 'other')], validators = (validators.Optional(),))
 spl_name= StringField('Sample name: ')
 spl_accession= StringField('Sample accession: ')
 spl_comment= StringField('Sample comment: ')
 spl_ssid= IntegerField(' Sample ssid: ' , [validators.Optional()])
 submit = SubmitField('Submit Data')


class ViewForm(FlaskForm):
 '''
 section to choose the individual view content
 '''
 submit = SubmitField('View all individuals')
