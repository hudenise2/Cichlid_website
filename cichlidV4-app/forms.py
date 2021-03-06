from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, RadioField, SelectField, validators
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
 Usrname= StringField('uname')
 option= SelectField('Choose entry type: ', choices = [('nwd', 'new_data'), ('upd', 'update'), ('ovw', 'overwrite')])
 #individual table info
 ind_name = StringField('Individual name: ')
 ind_alias = StringField('Individual alias: ')
 gender = RadioField('Gender', [validators.Required()], choices = [('U','Unknown'), ('M','Male'), ('F','Female')], default='U')
 ind_collected = StringField('Date collected (YYYY-MM-DD): ', validators = (validators.Optional(),))
 coll_method = StringField('Collection method : ')
 coll_details = StringField(' details: ')
 ind_provider = StringField('Collector: ')
 coll_weight = StringField('Weight: ')
 coll_unit = SelectField('unit', choices = [('gr', 'grams'), ('ug', 'micrograms'), ('mg', 'milligrams'), ('kg', 'kilograms')], validators = (validators.Optional(),))
 #species table info
 sp_name = StringField('Species name: ')
 sp_genus = StringField('Genus name: ')
 sp_species = StringField('Species name: ')
 sp_informal = StringField('Informal name: ')
 sp_taxid = StringField('Taxon_id: ', [validators.Optional()])
 sp_clade = SelectField('Species clade: ', choices = [('unk', '-select-'), ('Mal', 'Malawi species'), ('Tang', 'Tanganyika'), ('nonM', 'non-Malawi species'), ('oth', 'Others'), ('Mas', 'Caliptera Masoko')])
 sp_subset = SelectField('Subset group: ', choices = [('unk', '-select-'), ('Mb', 'Mbuna'), ('Deep', 'Deep'), ('Bent', 'Benthic'), ('AstC', 'Astatotilapia Caliptera'), ('Uta', 'Utaka'), ('Dip', 'DiploChromis'), ('Rham', 'Rhamphochromis')])
 sp_cname = StringField('Species common name: ')
 sp_taxpos = SelectField('Taxon position :', choices = [('unk', '-select-'), ('species', 'species'), ('informal', 'species informal'), ('order', 'order'), ('class', 'class'), ('family', 'family'), ('genus', 'genus'), ('phylum', 'phylum'), ('kingdom', 'kindom')])
 #material table info
 dev_stage= SelectField('Developmental stage: ', choices = [('unk', '-select-'), ('juv', 'juvenile'), ('adt', 'adult'), ('fry', 'fry'), ('gra', 'gravid')])
 mat_name = StringField('Material name: ')
 mat_acc = StringField(' Material accession: ')
 mat_type= SelectField('Material type: ', choices=[('unk','-select-'), ('dna', 'gDNA'), ('rna', 'RNA'), ('amp', 'amplicon')], validators = (validators.Optional(),))
 mat_part= SelectField('Organism part: ', choices = [('unk', ''), ('fin', 'fin'), ('liv', 'liver'), ('mus', 'muscle'), ('hed', 'head'), ('bra', 'brain'), ('bod', 'body'), ('tai', 'tail'), ('gil', 'gills'),
 ('gon', 'gonads'), ('ova', 'ovaries'), ('tes', 'testes'), ('hrt', 'heart'), ('kid', 'kidney'), ('lng', 'lung'), ('org', 'organs'), ('spl', 'spleen'), ('lim', 'limb'), ('jaw', 'jaw'), ('skn', 'skin'), ('eye', 'eye'), ('itt', 'intestine'), ('bld', 'blood'), ('anf', 'anal fin'), ('tss', 'tissue')])
 mat_cond= SelectField('Storage conditions: ', choices = [('unk',''), ('frz', 'frozen'), ('eth', 'ethanol'), ('dry', 'air dried'), ('Rlat', 'RNAlater'),('otr', 'other')])
 mat_wgt = StringField('Material amount: ', [validators.Optional()])
 mat_unit= SelectField(' unit: ', choices = [('gr', 'grams'), ('ul', 'microlitre')])
 mat_location = StringField('Material location: ')
 mat_loc_pos = StringField(' position: ')
 mat_comment = StringField('Comment: ')
 mat_received = StringField('Date received (YYYY-MM-DD): ', validators = (validators.Optional(),))
 mat_provider = StringField('Provider: ')
 #location table information
 loc_country = StringField('Country of origin: ')
 loc_region = StringField('Location: ')
 loc_details = StringField(' Sub-location: ')
 loc_lat = StringField('Latitude: ', [validators.Optional()])
 loc_lng = StringField(' Longitude: ', [validators.Optional()])
 #image table info
 img_name = StringField('Image name: ')
 img_source = StringField('Image path: ')
 img_licence = StringField('Image licence: ')
 img_comment = StringField('Image comment: ')
 #project table information
 prj_name = StringField('Project name: ')
 prj_alias = StringField('Project alias: ')
 prj_acc = StringField('Project accession: ')
 prj_ssid = StringField(' Project ssid: ' , [validators.Optional()])
 #annotationd table info
 ann_ann = StringField('Annotation: ')
 ann_comment = StringField('Annotation comment: ')
 ann_cat= SelectField('Category: ', choices = [('unk','-choose-'), ('ext', 'extraction'), ('col', 'collection'), ('stg', 'storage'), ('pro', 'processing')], validators = (validators.Optional(),))
 #provider table info
 pv_name = StringField('Provider name: ')
 pv_fname = StringField('First name: ')
 pv_mail = StringField('Email: ')
 pv_phone = StringField('Phone: ')
 pv_address = StringField('Address: ')
 #file table info
 file_accession= StringField('File accession: ')
 file_comment= StringField('File comment: ')
 file_format =SelectField('File format: ', choices = [('unk','-select-'), ('cram', 'cram'), ('bam', 'bam'), ('fastq', 'fastq'), ('fasta', 'fasta'), ('fast5', 'fast5'), ('vcf', 'vcf')], validators =(validators.Optional(),))
 file_md5= StringField('MD5 checksum: ')
 file_name= StringField('File name: ')
 file_path= StringField('File path: ')
 file_PE = RadioField(' Paired_end:', validators = (validators.Optional(),), choices=[('y', 'Y'), ('n', 'N')])
 file_reads=StringField(' Number of reads: ' , [validators.Optional()])
 file_average=StringField('Average read length: ' , [validators.Optional()])
 file_total=StringField('Total read length: ' , [validators.Optional()])
 file_depth=StringField('Sequencing depth: ' , [validators.Optional()])
 file_exclusion=SelectField('Exclusion code: ', choices = [('unk','-select-'), ('susp', 'suspect'), ('dup', 'duplicated'), ('err', 'erroneous'), ('anom', 'anomalous')], validators =(validators.Optional(),))
 #lane table info
 lane_accession= StringField(' Lane accession: ')
 lane_name= StringField('Lane name: ')
 #library table info
 lib_name= StringField('Library name: ')
 lib_ssid= StringField(' Library ssid: ' , [validators.Optional()])
 #seq_tech and centre info
 seq_centre= StringField('Sequencing centre: ')
 seq_tech = SelectField('Sequencing technology: ', choices = [('unk','-select-'), ('illumina', 'Illumina'), ('PACBIO', 'PacBio'), ('ONT', 'Oxford Nanopore'), ('10X', '10X Genomics'), ('HIC', 'Hi-C'), ('RNASeq', 'RNA-Seq'), ('OTH', 'other')], validators = (validators.Optional(),))
 #sample table info
 spl_name= StringField('Sample name: ')
 spl_accession= StringField('Sample accession: ')
 spl_comment= StringField('Sample comment: ')
 spl_ssid= StringField(' Sample ssid: ' , [validators.Optional()])

 submit = SubmitField('Submit Data')


class ViewForm(FlaskForm):
 '''
 section to choose the individual view content
 '''
 submit = SubmitField('View all individuals')
