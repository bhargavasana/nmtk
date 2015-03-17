from celery.task import task
import simplejson as json
import decimal
import requests
import urlparse
import hmac
import hashlib
import uuid
from django.utils import timezone
from django.conf import settings
from django.core.management.color import no_style
from django.db import connections, transaction
import logging
import os
from django.core.exceptions import ObjectDoesNotExist
from NMTK_apps.helpers.data_output import getQuerySet
from NMTK_server.data_loaders.loaders import NMTKDataLoader
from django.core.files import File
from django.contrib.gis import geos
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.core.management.commands import inspectdb
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.core.files.base import ContentFile
from django.shortcuts import render
from django.db.models import fields as django_model_fields
from django.db.models import Max, Min, Count
from osgeo import ogr
import imp
import datetime
from django.contrib.gis.geos import GEOSGeometry
import tempfile

#from django.core.serializers.json import DjangoJSONEncoder
logger=logging.getLogger(__name__)

geomodel_mappings={ ogr.wkbPoint: ('models.PointField', geos.Point, 'point'),
                    ogr.wkbGeometryCollection: ('models.GeometryField', geos.GEOSGeometry, 'point'),
                    ogr.wkbLineString:  ('models.LineStringField', geos.LineString, 'line'),
                    ogr.wkbMultiPoint: ('models.MultiPointField', geos.MultiPoint,'point'),
                    ogr.wkbMultiPolygon: ('models.MultiPolygonField', geos.MultiPolygon,'polygon'),
                    ogr.wkbPolygon: ('models.PolygonField', geos.Polygon,'polygon'),
                    ogr.wkbMultiLineString: ('models.MultiLineStringField', geos.MultiLineString,'line'),
                   }
    


# This actually does not get done as a task - it is inline with the
# response from the tool server.
def generate_datamodel(datafile, loader):
    def propertymap(data):
        output={}
        used=[]
        c=inspectdb.Command()
        for k in data:
            att_name, params, notes=inspectdb.Command.normalize_col_name(c, k, used, False)
#             logger.debug('Field %s, %s', att_name, notes)
            used.append(att_name)    
            output[k]=att_name
#         logger.debug('Mappings are %s', output)
        return output

    try:
        if loader.is_spatial:
            spatial=True
            geom_type=loader.info.type
            model_type, geos_func, mapfile_type=geomodel_mappings[geom_type]
        else:
            spatial=False
        db_created=False
        this_model=None
        colors=[]
        model_content=['from django.contrib.gis.db import models']
#         feature_id=1
        for (row, geometry) in loader:
            if not db_created:
                db_created=True
                if datafile.result_field:
                    min_result=max_result=float(row[datafile.result_field])
                # Create the model for this data
                model_content.append('class Results_{0}(models.Model):'.format(datafile.pk))
                # Add an auto-increment field for it (the PK)
                model_content.append('{0}nmtk_id=models.AutoField(primary_key=True, )'.format(' ' * 4))
#                 model_content.append('{0}nmtk_feature_id=models.IntegerField()'.format(' '*4))
                # Add an entry for each of the fields
                # So instead of doing this - getting the keys to figure out the fields
                fields_types=loader.info.fields_types
                field_map=propertymap((field_name for field_name, type in fields_types))
                type_mapping={str: ('models.TextField',''),
                              unicode: ('models.TextField',''),
                              int: ('models.DecimalField','max_digits=32, decimal_places=0, '), # We support up to a 32 digit integer.
                              float: ('models.FloatField',''),
                              datetime.date: ('models.DateField',''),
                              datetime.time: ('models.TimeField',''),
                              bool: ('models.BooleanField',''),
                              datetime.datetime: ('models.DateTimeField',''),}
                for field_name, field_type in fields_types:
                    if field_type not in type_mapping:
                        logger.info('No type mapping exists for type %s (using TextField)!', field_type)
                        field_type=str
                    model_content.append("""{0}{1}={2}({3} null=True, db_column='''{4}''')""".
                                         format(' '*4, 
                                                field_map[field_name], 
                                                type_mapping[field_type][0],
                                                type_mapping[field_type][1],
                                                field_name)
                                         )    
                if spatial:
                    model_content.append('''{0}nmtk_geometry={1}(null=True, srid=4326, dim={2})'''.
                                         format(' '*4, model_type,
                                                loader.info.dimensions))
                model_content.append('''{0}objects=models.GeoManager()'''.format(' '*4,))
                
                model_content.append('''{0}class Meta:'''.format(' '*4,))
                model_content.append('''{0}db_table='userdata_results_{1}' '''.format(' '*8,datafile.pk))
                datafile.model.save('model.py', ContentFile('\n'.join(model_content)),
                                    save=False)
                #logger.debug('\n'.join(model_content))
                user_models=imp.load_source('%s.models' % (datafile.pk,),datafile.model.path)
                Results_model=getattr(user_models,'Results_{0}'.format(datafile.pk))
               
                database='default'
                # If using PostgreSQL, then just create the model and go...
                dbtype='postgis'
                connection=connections[database] 
                cursor=connection.cursor()
                for statement in connection.creation.sql_create_model(Results_model, no_style())[0]:
                    cursor.execute(statement)
                for statement in connection.creation.sql_indexes_for_model(Results_model, no_style()):
                    cursor.execute(statement)
            
            this_row=dict((field_map[k],v) for k,v in row.iteritems())
            if spatial:
                this_row['nmtk_geometry']=geometry
            if datafile.result_field:
                try:
                    logger.debug('Row is %s', this_row)
                    min_result=min(float(this_row[datafile.result_field.lower()]), min_result)
                    max_result=max(float(this_row[datafile.result_field.lower()]), max_result)
                except Exception, e:
                    logger.exception('Result field (%s) is not a float (ignoring)', datafile.result_field)
            else:
                min_result=max_result=1
            m=Results_model(**this_row)
            try:
                m.save(using=database)
            except Exception, e:
                logger.exception('Failed to save record from data file (%s)', this_row)
                logger.error('The type of data in question was %s (%s)',m, this_row )
                raise e
        logger.debug('Completing transferring results to %s database %s', dbtype,datafile.pk,)

    except Exception, e:
        logger.exception ('Failed to create spatialite results table')
        return datafile
    logger.debug('About to return job back to caller - %s', datafile.pk)
    return datafile
    

@task(ignore_result=True)
def email_user_job_done(job):
    context={'job': job,
             'user': job.user,
             'tool': job.tool,
             'site': Site.objects.get_current()}
    logger.debug('Job complete (%s), sending email to %s', 
                 job.tool.name, job.user.email)
    subject=render_to_string('NMTK_server/job_finished_subject.txt',
                             context).strip().replace('\n',' ')
    message=render_to_string('NMTK_server/job_finished_message.txt',
                             context)
    logger.debug('Sending job complete notification email to %s', job.user.email)
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL,
              [job.user.email,])

@task(ignore_result=False)
def add_toolserver(name, url, username, remote_ip=None):
    from NMTK_server import models
    try:
        User=get_user_model()
        user=User.objects.get(username=username)
    except Exception, e:
        raise CommandError('Username specified (%s) not found!' % 
                           username)
    m=models.ToolServer(name=name,
                        server_url=url,
                        remote_ip=remote_ip,
                        created_by=user)
    m.save()
    return m

@task(ignore_result=False)
def discover_tools(toolserver):
    from NMTK_server import models
    if not toolserver.server_url.endswith('/'):
        append_slash='/'
    else:
        append_slash=''
    url="{0}{1}index".format(toolserver.server_url, append_slash) # index returns a json list of tools.
    tool_list=requests.get(url).json()
    logger.debug('Retrieved tool list of: %s', tool_list)
    for tool in tool_list:
        try:
            t=models.Tool.objects.get(tool_server=toolserver,
                                      tool_path=tool)
            # Clean up any sample files, we will reload them now.
            if hasattr(t,'toolsampleconfig'):
                t.toolsampleconfig.delete()    
            t.toolsamplefile_set.all().delete()
        except ObjectDoesNotExist:
            t=models.Tool(tool_server=toolserver,
                          name=tool)
        t.active=True
        t.tool_path=tool
        t.name=tool
        t.save()
    
    # Locate all the tools that aren't there anymore and disable them.
    for row in models.Tool.objects.exclude(tool_path__in=tool_list).filter(active=True, tool_server=toolserver):
        logger.debug('Disabling tool %s', row.name)
        row.active=False
        row.save()

@task(ignore_result=False)
def cancelJob(job_id, tool_id):
    '''
    Whenever a job that is active is cancelled, we need to notify the tool
    server to cancel the job as well.
    
    The tool doesn't support this (yet), since each tool might be different
    '''
    from NMTK_server import models
    logger=cancelJob.get_logger()
    tool=models.Tool.objects.get(pk=tool_id)
    logger.debug('Cancelling job %s to tool %s for processing', job_id,
                 tool)
    config_data=job_id
    digest_maker =hmac.new(str(tool.tool_server.auth_token), 
                           config_data, 
                           hashlib.sha1)
    digest=digest_maker.hexdigest()
    files={'cancel': ('cancel', job_id) }
    r=requests.delete(job.tool.analyze_url, files=files,
                    headers={'Authorization': digest })
    logger.debug("Submitted cancellation request for job to %s tool, response was %s (%s)", 
                 tool, r.text, r.status_code)
        
@task(ignore_result=False)
def submitJob(job_id):
    '''
    Whenever a job status is set to active in the database, the 
    signal attached to the model causes the job to be submitted.
    This causes this task (a celery task) to run, and submit
    the job to the tool.
    '''
    from NMTK_server import models
    job=models.Job.objects.get(pk=job_id)
    # Get a logger to log status for this task.
    logger=submitJob.get_logger()
    logger.debug('Submitting job %s to tool %s for processing', job.pk,
                 job.tool)
    
    configuration={'analysis settings': job.config }
    configuration['job']= {'tool_server_id': "%s" % (job.tool.tool_server.tool_server_id,),
                           'job_id': str(job.job_id),
                           'timestamp': timezone.now().isoformat() }

    config_data=json.dumps(configuration, use_decimal=True) #cls=DjangoJSONEncoder)
    digest_maker =hmac.new(str(job.tool.tool_server.auth_token), 
                           config_data, 
                           hashlib.sha1)
    digest=digest_maker.hexdigest()
    
    files= {'config': ('config', config_data) }
    for jobfile in job.jobfile_set.all():
        if jobfile.datafile.processed_file:
            files[jobfile.namespace]=(jobfile.datafile.processed_file.name, jobfile.datafile.processed_file)
        else:
            files[jobfile.namespace]=(jobfile.datafile.file.name, jobfile.datafile.file)
    logger.debug('Files for job are %s', files)
    r=requests.post(job.tool.analyze_url, files=files,
                    headers={'Authorization': digest })
    logger.debug("Submitted job to %s tool, response was %s (%s)", 
                 job.tool, r.text, r.status_code)
    if r.status_code <> 200:
        job.status=job.TOOL_FAILED
        js=models.JobStatus(job=job,
                            message=('Tool failed to accept ' + 
                                     'job (return code %s)') % (r.status_code,))
        js.save()
        job.save()
    else:
        status_m=models.JobStatus(message='Submitted job to {0} tool, response was {1} ({2})'.format(job.tool, 
                                                                                                 r.text, 
                                                                                                 r.status_code),
                              timestamp=timezone.now(),
                              job=job)
        status_m.save()
        
    
@task(ignore_result=False)
def updateToolConfig(tool):
    from NMTK_server import models
    json_config=requests.get(tool.config_url)
    try:
        config=tool.toolconfig
    except:
        config=models.ToolConfig(tool=tool)
    config_data=json_config.json()
    config.json_config=config_data
    config.save()
    if hasattr(tool, 'toolsampleconfig') and tool.toolsampleconfig.pk:
        tool.toolsampleconfig.delete()
    tool.toolsamplefile_set.all().delete()
    try:
        logger.debug('Trying to load sample config for %s', tool.name)
        logger.debug('Config is %s', config_data)
        if (isinstance(config_data.get('sample', None), (dict,)) and 
            config_data['sample'].get('config')): 
            objects_to_save=[]
            objects_to_delete=[]
            tsc=models.ToolSampleConfig(sample_config=config_data['sample']['config'], 
                                        tool=tool)
            objects_to_save.append(tsc)
            reqd_fields=['namespace','checksum']
            for fconfig in config_data['sample'].get('files',[]):
                logger.debug('Working with %s', fconfig)
                sample_config_fields={'tool': tool}
                for f in reqd_fields:
                    if fconfig.has_key(f): 
                        sample_config_fields[f]=fconfig.get(f)
                    else:
                        raise Exception('Missing required field: %s' % (f,))
                m=models.ToolSampleFile(**sample_config_fields)
                if fconfig.has_key('uri'):
                    parsed=urlparse.urlparse(fconfig.get('uri'))
                    if not parsed.scheme:
                        if parsed.path[0] == '/':
                            p=urlparse.urlparse(tool.tool_server.server_url)
                            fconfig['uri']=urlparse.urlunparse([p.scheme,
                                                                p.netloc,
                                                                fconfig['uri'],
                                                                '',
                                                                '',
                                                                ''])
                        else:
                            raise Exception('Only absolute URLs or fully-qualified URLs allowed')
                    logger.debug('Attempting to download %s', fconfig['uri'])       
                    data=requests.get(fconfig['uri'], stream=True)
                    checksum=hashlib.sha1()
                    if data.status_code != 200:
                        raise Exception('Failed to download data file %s',
                                        fconfig['uri'])
                    logger.debug('Download succeeded!')
                    with tempfile.TemporaryFile() as f:
                        for chunk in data.iter_content(chunk_size=1024): 
                            if chunk: # filter out keep-alive new chunks
                                f.write(chunk)
                                checksum.update(chunk)
                                f.flush()
                        logger.debug('Checksum is %s=%s', fconfig['checksum'],
                                     checksum.hexdigest())
                        if checksum.hexdigest() == fconfig['checksum']:
                            f.seek(0)
                            # Get the file name
                            name=os.path.basename(urlparse.urlparse(fconfig['uri']).path)
                            if fconfig.has_key('content-type'):
                                m.content_type=fconfig['content-type']
                            elif data.headers.has_key('content-type'):
                                m.content_type=data.headers['content-type'].partition(';')[0]
                            else:
                                t=mimetypes.guess_type(fconfig['uri'])[0]
                                if t:
                                    m.content_type=t
                            m.file.save(name, File(f))
                            objects_to_delete.append(m)
            for m in objects_to_save:
                m2=models.ToolSampleConfig.objects.filter(tool=m.tool)
                if len(m2) == 1:
                    m.pk=m2[0].pk
            [m.save() for m in objects_to_save]
    except:
        logger.exception('Failed to load tool sample config.')
        # If we fail, we need to delete any downloaded files we saved.
        [m.delete() for m in objects_to_delete]

    # Note: We use update here instead of save, since we want to ensure that
    # we don't call the post_save handler, which would result in
    # a recursion loop.
    logger.debug('Setting tool name to %s', config_data['info']['name'])
    # This doesn't call the save method, so we're okay here in preventing a loop.
    models.Tool.objects.filter(pk=config.tool.pk).update(name=config_data['info']['name'])
    
         
@task(ignore_result=False)
def importDataFile(datafile, job_id=None):
    from NMTK_server import models
    datafile.status_message=None
    try:
        loader=NMTKDataLoader(datafile.file.path, 
                              srid=datafile.srid)
        if loader.is_spatial:
            datafile.srid=loader.info.srid
            datafile.srs=loader.info.srs
            datafile.geom_type=loader.info.type
            logger.debug('Loader extent is %s', loader.info.extent)
            extent=geos.Polygon.from_bbox(loader.info.extent)
            logger.debug("Extent is 'srid=%s;%s'::geometry", loader.info.srid, 
                         extent,)
            if datafile.srid:
                extent.srid=int(loader.info.srid)
                extent.transform(4326)
            logger.debug("Extent is 'srid=%s;%s'::geometry", 4326, 
                         extent,)
            datafile.extent=extent
        datafile.feature_count=loader.info.feature_count
        if loader.is_spatial and not datafile.srid:
            datafile.status=datafile.IMPORT_FAILED
            datafile.status_message='Please specify SRID for this file (unable to auto-identify SRID)'
        elif not job_id:
            datafile.status=datafile.IMPORTED
        else:
            datafile.status=datafile.IMPORT_RESULTS_COMPLETE
        datafile.fields=loader.info.fields
        # Create an empty file using ContentFile, then we can overwrite it 
        # with the desired GeoJSON data.
        if loader.is_spatial: 
            suffix='geojson'
        else: 
            suffix='json'
        if datafile.status in (datafile.IMPORTED, datafile.IMPORT_RESULTS_COMPLETE):
            datafile.processed_file.save('{0}.{1}'.format(datafile.pk, suffix), 
                                         ContentFile(''))
            loader.export_json(datafile.processed_file.path)
            generate_datamodel(datafile, loader)
            # Here we load the spatialite data using the model that was created
            # by generate_datamodel.  We need to use this to get the range
            # and type information for each field...
            try:
                field_attributes={}
                qs=getQuerySet(datafile)
                field_mappings=[(django_model_fields.IntegerField, 'integer',),
                                (django_model_fields.AutoField, 'integer',), # Required because nmtk_id is an autofield..
                                (django_model_fields.BooleanField, 'boolean',),
                                (django_model_fields.DecimalField, 'float',), # Special case holding FIPS
                                (django_model_fields.TextField, 'text',),
                                (django_model_fields.FloatField,'float'),
                                (django_model_fields.DateField, 'date',),
                                (django_model_fields.TimeField, 'time'),
                                (django_model_fields.DateTimeField, 'datetime')]
                if qs.count() > 0:
                    # Get a single row so that we can try to work with the fields.
                    sample_row=qs[0]
                    for field in sample_row._meta.fields:
                        field_name=field.name
                        db_column=field.db_column or field.name
                        # convert the django field type to a text string.
                        for ftype, field_type in field_mappings:
                            if isinstance(field, (ftype,)):
                                break
                        else:
                            logger.info('Unable to map field of type %s (this is expected for GIS fields)', type(field,))
                            continue
                        values_aggregates=qs.aggregate(Count(field_name, distinct=True))
                        field_attributes[db_column]={'type': field_type, 
                                                     'field_name': field_name,
                                                     'distinct': values_aggregates['{0}__count'.format(field_name)]}
                        if field_attributes[db_column]['distinct'] < 10:
                            distinct_values=list(qs.order_by().values_list(field_name, flat=True).distinct())
                            field_attributes[db_column]['values']=distinct_values
                        else:
                            logger.debug('There are more than 10 values for %s (%s), enumerating..', db_column, 
                                         field_attributes[db_column]['distinct'])
                            # formerly the aggregates happened above - with the count. However, Django doesn't
                            # allow those aggregates with boolean fields - so here we split it up to only do the
                            # aggregates in the cases where we have to (i.e., the distinct values is above the threshold.)
                            values_aggregates=qs.aggregate(Max(field_name), Min(field_name), )
                            field_attributes[db_column]['min']= values_aggregates['{0}__min'.format(field_name)]
                            field_attributes[db_column]['max']= values_aggregates['{0}__max'.format(field_name)]
                    datafile.field_attributes=field_attributes
            except Exception, e:
                logger.exception('Failed to get range for model %s',
                                 datafile.pk)
        if job_id:
            try:
                job=models.Job.objects.get(pk=job_id)
                # There might be multiple results files from this job, so we will only
                # mark the job as complete if all the results files are processed.
                if job.status != job.COMPLETE:
                    results_left=job.job_files.filter(status=models.DataFile.PROCESSING_RESULTS).count()
                    if results_left == 0:
                        job.status=job.COMPLETE
                        models.JobStatus(message='Job Completed',
                                         timestamp=timezone.now(),
                                         job=job).save()
                    elif results_left == 1:
                        # Handle the potential race condition here - do we really need this?
                        # sort of.  Since it's possible that two files finish post-processing
                        # at the same time.  In such cases, a second should be more than enough
                        # time to get both committed as complete.
                        time.sleep(1)
                        job=models.Job.objects.get(pk=job_id)
                        if job.status != job.COMPLETE:
                            results_left=job.job_files.filter(status=models.DataFile.PROCESSING_RESULTS).count()
                            if results_left == 0:
                                job.status=job.COMPLETE
                                models.JobStatus(message='Job Completed',
                                                 timestamp=timezone.now(),
                                                 job=job).save()
                    
                    
            except: 
                logger.exception('Failed to update job status to complete?!!')
    except Exception, e:
        logger.exception('Failed import process!')
        datafile.processed_file=None
        if not job_id:
            datafile.status=datafile.IMPORT_FAILED
        else:
            datafile.status=datafile.IMPORT_RESULTS_FAILED
        datafile.status_message="%s" % (e,)
        if job_id:
            try:
                job=models.Job.objects.get(pk=job_id)
                job.status=job.POST_PROCESSING_FAILED
            except:
                logger.exception('Failed to update job status to failed?!!')
    
    
    
    if job_id:
        job.save()
    # Now we need to create the spatialite version of this thing.
    datafile.save()
    
    
