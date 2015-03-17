from django.contrib.gis.db import models
from uuidfield import UUIDField
from jsonfield import JSONField
from random import choice
from django.conf import settings
from django.utils import timezone
import os
from django.core.urlresolvers import reverse
import hashlib
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import InMemoryUploadedFile
import cStringIO as StringIO
from django.db import connections, transaction
from django.conf import settings
from django.utils.safestring import mark_safe
from osgeo import ogr
from django.contrib.gis.gdal import OGRGeometry
from NMTK_server import tasks
from NMTK_server import signals
from NMTK_server.wms.legend import LegendGenerator
from django.core.validators import MaxValueValidator, MinValueValidator
import logging
from django.contrib.auth.models import AbstractUser
logger=logging.getLogger(__name__)

class IPAddressFieldNullable(models.IPAddressField) :
    def get_db_prep_save(self, value, connection):
        return value or None

class NMTKDataFileSystemStorage(FileSystemStorage):
    def url(self, name):
        raise NotImplementedError
        return reverse('NMTK_server.download_datafile',
                       kwargs={'file_id': name})
        
class NMTKGeoJSONFileSystemStorage(FileSystemStorage):
    def url(self, name):
        raise NotImplementedError
        return reverse('NMTK_server.download_geojson_datafile',
                       kwargs={'file_id': name})
        
        
class NMTKResultsFileSystemStorage(FileSystemStorage):
    '''
    Kind of hokey here, but we will use the filename to determine the job
    id, and thereby figure out how to generate the download link.
    '''
#     def url(self, name):
# #        raise NotImplementedError
#         return reverse('downloadResults',
#                        kwargs={'job_id': name.rsplit('/',2)[-1].split('.')[0]})
        
location=os.path.join(settings.FILES_PATH, 'NMTK_server', 'files')
fs = NMTKDataFileSystemStorage(location=location)
fs_geojson = NMTKGeoJSONFileSystemStorage(location=location)
fs_results = NMTKResultsFileSystemStorage(location=location)


class PageName(models.Model):
    '''
    Valid page names (current valid value is nmtk_index, and nmtk_tos)
    '''
    name=models.CharField(max_length=16, null=False,
                          blank=False, help_text='The name for the page this text belongs to')
    class Meta:
        db_table='nmtk_pagename'
        
    def __str__(self):
        return self.name


class PageContent(models.Model):
    page=models.ForeignKey(PageName)
    order=models.IntegerField(default=0)
    content=models.TextField()
    enabled=models.BooleanField(default=True)
    created=models.DateTimeField(editable=False)
    modified=models.DateTimeField(editable=False)
    class Meta:
        db_table='nmtk_content'
        ordering=['order',]
        
    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if not self.id:
            self.created = timezone.now()
        self.modified = timezone.now()
        return super(PageContent, self).save(*args, **kwargs)
        
class ToolServer(models.Model):
    name=models.CharField(max_length=64,
                          help_text='A descriptive name for this tool server.')
    tool_server_id = UUIDField(auto=True, primary_key=True)
    auth_token=models.CharField(max_length=50,
                             default=lambda: ''.join([choice('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)') for i in range(50)]))
    remote_ip=IPAddressFieldNullable(blank=True,null=True,
                                     help_text=('The IP where the tool resides' +
                                                ' so we can verify the request' +
                                                ' source IP as well if needed'))
    active=models.BooleanField(default=True)
    last_modified=models.DateTimeField(auto_now=True)
    server_url=models.URLField()
    date_created=models.DateTimeField(auto_now_add=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    objects=models.GeoManager()
    def __str__(self):
        return "%s" % (self.name,)
    
    def save(self, *args, **kwargs):
        '''
        Whenever a toolserver record is saved (and it's not a new record) we will
        go out and discover its tools.
        '''
        result=super(ToolServer, self).save(*args, **kwargs)
        logger.debug('Detected a save of the ToolServer model, adding/updating tools.')
        tasks.discover_tools.delay(self)
        return result
    
    class Meta:
        db_table='nmtk_tool_server'
        verbose_name='Tool Server'
        verbose_name_plural='Tool Servers'
    
# Create your models here.       
class Tool(models.Model):
    '''
    For the NMTK server, the tool model will contain information about registered
    tools.
    '''
    name=models.CharField(max_length=64,
                          help_text='The name of the tool')
    tool_path=models.CharField(max_length=64,
                               help_text='The URL path for the tool')
    tool_server=models.ForeignKey(ToolServer)
    active=models.BooleanField(default=True)
    last_modified=models.DateTimeField(auto_now=True)
    objects=models.GeoManager()

    @property
    def analyze_url(self):
        return "%s/%s/analyze" % (self.tool_server.server_url.rstrip('/'), 
                                  self.tool_path.strip('/'))
    @property
    def config_url(self):
        return "%s/%s/config" % (self.tool_server.server_url.rstrip('/'),
                                 self.tool_path.strip('/'))    
        
    def save(self, *args, **kwargs):
        result=super(Tool, self).save(*args, **kwargs)
        if self.active and not kwargs.get('bypass_refresh', False):
            logger.debug('Detected a save of the Tool model, updating configs.')
            tasks.updateToolConfig.delay(self)
        return result
    
    def __unicode__(self):
        return self.name
    
    class Meta:
        verbose_name='Tool'
        verbose_name_plural='Tools'
        db_table='nmtk_tool'
        
    
class ToolConfig(models.Model):
    '''
    Each tool has a single configuration, which is stored as a configuration
    object (json encoded structure.)
    '''
    tool=models.OneToOneField(Tool, on_delete=models.CASCADE)
    json_config=JSONField()
    objects=models.GeoManager()

    class Meta:
        verbose_name='Tool Configuration'
        verbose_name_plural='Tool Configurations'
        db_table='nmtk_tool_config'

        
class ToolSampleConfig(models.Model):
    tool=models.OneToOneField(Tool, on_delete=models.CASCADE)
    sample_config=JSONField()
    objects=models.GeoManager()
    
    class Meta:
        verbose_name='Tool Sample Configuration'
        verbose_name_plural='Tool Sample Configurations'
        db_table='nmtk_tool_sample_config'

class ToolSampleFile(models.Model):
    '''
    When we load up a tool we download it's data file and cache it on the
    server.  Using this, a user can load the tool sample file into his/her
    data library, and then use it.  The caching ensures that we only need to
    download/manage the file once.
    '''
    tool=models.ForeignKey(Tool, on_delete=models.CASCADE)
    namespace=models.CharField(max_length=32, null=False)
    file=models.FileField(storage=fs, upload_to=lambda instance, 
                          filename: 'tool_files/%s/%s' % (instance.tool.pk, filename,))
    checksum=models.CharField(max_length=50, null=False)
    content_type=models.CharField(max_length=64, null=True)
    objects=models.GeoManager()
    
    class Meta:
        verbose_name='Tool Sample File'
        verbose_name_plural='Tool Sample Files'
        db_table='nmtk_tool_sample_file'

    
    def delete(self):
        '''
        Ensure files are deleted when the model instance is removed.
        '''
        delete_candidates=[]
        delete_fields=['file',]
                      
        for field in delete_fields:
            try:
                if getattr(self, field, None):
                    delete_candidates.append(getattr(self, field).path)
            except Exception, e:
                logger.exception('Failed to process delete for %s (%s)', 
                                 field, self.pk)
        r=super(ToolSampleFile, self).delete()
        for f in delete_candidates:
            if os.path.exists(f):
                os.unlink(f)
        return r
        
class Job(models.Model):
    UNCONFIGURED='U'
    ACTIVE='A'
    FAILED='F'
    COMPLETE='C'
    TOOL_FAILED='TF'
    POST_PROCESSING='PP'
    POST_PROCESSING_FAILED='PF'
    STATUS_CHOICES=((UNCONFIGURED,'Configuration Pending'),
                    (ACTIVE,'Active',),
                    (FAILED,'Failed',),
                    (TOOL_FAILED,'Tool Failed to Accept Job',),
                    (POST_PROCESSING, 'Post-processing results',),
                    (POST_PROCESSING_FAILED, 'Post-processing of results failed'),
                    (COMPLETE,'Complete'),
                    )
    
    def __init__(self, *args, **kwargs):
        super(Job, self).__init__(*args, **kwargs)
        self._old_status=self.status
        self._old_tool=self.tool if hasattr(self,'tool') else None
    job_id=UUIDField(auto=True, primary_key=True)
    tool=models.ForeignKey(Tool, on_delete=models.PROTECT)
    date_created=models.DateTimeField(auto_now_add=True)
    status=models.CharField(max_length=32, choices=STATUS_CHOICES, default=UNCONFIGURED)
#     file=models.FileField(storage=fs, upload_to=lambda instance, filename: 'data_files/%s.geojson' % (instance.job_id,))
#     data_file=models.ForeignKey('DataFile', null=True, related_name='job_source',
#                                 blank=True, on_delete=models.PROTECT)
    # The result could contain multiple datafiles as well, so we will deal with 
    # that via a separate model.
    results_files=models.ManyToManyField('DataFile', null=True, through='ResultsFile',
                                         related_name='results')
    # Now each job could have numerous data files, prevent deletion of a data file
    # if a job still requires it.
    job_files=models.ManyToManyField('DataFile', null=True, through='JobFile',
                                     related_name='job_files')
    # This will contain the config data to be sent along with the job, in 
    # a JSON format of a multi-post operation.
    config=JSONField(null=True)
    description=models.CharField(max_length=2048, null=False, blank=False,
                                 help_text='A free-form description of this job')
    # The user that created the job (used to restrict who can view the job.)
    user=models.ForeignKey(settings.AUTH_USER_MODEL, null=False)
    email=models.BooleanField(default=False, help_text='Email user upon job completion')
    objects=models.GeoManager()

    def delete(self, *args, **kwargs):
        result=super(Job, self).delete(*args, **kwargs)
        if self.status == self.ACTIVE:
            logger.error('TODO: Send cancel request to tool server')
            tasks.cancelJob.delay(str(self.pk), self.tool.pk)
        return result
    
    @property
    def results_link(self):
        return reverse('viewResults', kwargs={'job_id': self.job_id})
    
    def __str__(self):
        return "%s for %s" % (self.pk, self.user.username)

    def save(self, *args, **kwargs):    
        '''
        Rather than have the view code have to submit the job, we'll just 
        monitor the job table.  Whenever a job gets configured, the
        state change from unconfigured to configured will trigger 
        sending the job to the client - so we have a single entry point
        for sending jobs to the client.
        
        In the interest of speed, the job execution work (which might take 
        some time to submit) is passed off as a celery task, so the client gets
        it's response(s) back immediately.
        '''
        result=super(Job, self).save(*args, **kwargs)
        if self._old_status == self.UNCONFIGURED:
            if hasattr(self, 'job_files_pending'):
                logger.debug('Saving Job file entries for this job')
                # Save all the job files.
                map(lambda f: f.save(), self.job_files_pending)
            if self.status == self.ACTIVE:
                logger.debug('Detected a state change from Unconfigured to ' + 
                             'Active for job (%s.)', self.pk)
                logger.debug('Sending job to tool for processing.')
                status_m=JobStatus(message='NMTK Server received job for processing.',
                              timestamp=timezone.now(),
                              job=self)
                status_m.save()
                # Submit the task to the client, passing in the job identifier.
                tasks.submitJob.delay(str(self.pk))
        elif (self.email and self._old_status <> self.status and
              self.status in (self.FAILED, self.TOOL_FAILED, 
                              self.COMPLETE, self.POST_PROCESSING_FAILED)):
            tasks.email_user_job_done.delay(self)
        return result
    
    class Meta:
        ordering=['-date_created']
        verbose_name='Job'
        verbose_name_plural='Jobs'
        db_table='nmtk_job'



class ResultsFile(models.Model):
    '''
    Since it is possible for a job to return multiple results now, we need to 
    tie the job to its results.  This is done via this model.  Only one
    of the result files is considered the "primary" result though, and it's
    the one that can be used for display using the result field from the models
    config.
    '''
    job=models.ForeignKey('Job', on_delete=models.CASCADE)
    datafile=models.ForeignKey('DataFile', on_delete=models.PROTECT)
    primary=models.BooleanField(default=False)
    class Meta:
        db_table='nmtk_results_file'


class JobFile(models.Model):
    job = models.ForeignKey('Job', on_delete=models.CASCADE)
    datafile = models.ForeignKey('DataFile', on_delete=models.PROTECT)
    namespace=models.CharField(max_length=255, null=False);
    
    def json(self):
        return {'job': str(self.job.pk),
                'datafile': self.datafile.pk,
                'namespace': self.namespace}
    class Meta:
        db_table='nmtk_job_file'
  
class DataFile(models.Model):
    PENDING=1
    PROCESSING=2
    IMPORTED=3
    IMPORT_FAILED=4
    PROCESSING_RESULTS=5
    IMPORT_RESULTS_FAILED=6
    IMPORT_RESULTS_COMPLETE=7
    
    STATUSES=((PENDING,'Import Pending',),
              (PROCESSING,'File submitted for processing',),
              (IMPORTED,'Import Complete',),
              (IMPORT_FAILED, 'Unrecognized Type',),
              (PROCESSING_RESULTS,'Import of Job Results Pending',),
              (IMPORT_RESULTS_FAILED,'Import of Job Results Failed',),
              (IMPORT_RESULTS_COMPLETE,'Import of Job Results Complete',),
              )
    # The supported geometry types
    GEOM_TYPES=((ogr.wkbPoint, 'POINT'),
                (ogr.wkbGeometryCollection, 'GEOMETRYCOLLECTION'),
                (ogr.wkbLineString, 'LINESTRING'),
                (ogr.wkbMultiPoint, 'MULTIPOINT'),
                (ogr.wkbMultiPolygon, 'MULTIPOLYGON'),
                (ogr.wkbPolygon, 'POLYGON'),
                (ogr.wkbMultiLineString, 'MULTILINESTRING'),
                )
    # File Types
    JOB_INPUT='source'
    JOB_RESULT='result'
    JOB_BOTH='both'
    FILE_TYPES=((JOB_INPUT, 'Candidate for Input',),
                (JOB_RESULT, 'Results from Job',),
                (JOB_BOTH, 'Result from Job, can be used for input',)
                )
    file=models.FileField(storage=fs, 
                          upload_to=lambda instance, filename: '%s/data_files/%s' % (instance.user.pk, filename,))
    processed_file=models.FileField(storage=fs_geojson, 
                                    upload_to=lambda instance, filename: '%s/data_files/converted/%s' % (instance.user.pk, filename,))
    name=models.CharField(max_length=64)
    type=models.CharField(choices=FILE_TYPES, max_length=10,
                          default=JOB_INPUT)
    status=models.IntegerField(choices=STATUSES, default=PENDING)
    status_message=models.TextField(blank=True, null=True)
    srid=models.IntegerField(null=True, blank=True)
    srs=models.TextField(null=True, blank=True)
    feature_count=models.IntegerField(null=True, blank=True)
    extent=models.PolygonField(srid=4326, null=True, blank=True)  
    geom_type=models.IntegerField(choices=GEOM_TYPES, blank=True, null=True)                                                                                                                                   
    description=models.TextField(null=True, blank=True)
    content_type=models.CharField(max_length=128)
    date_created=models.DateTimeField(auto_now_add=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL, null=False)
    fields=JSONField(null=True, blank=True)
    field_attributes=JSONField(null=True, blank=True)
    deleted=models.BooleanField(default=False)
    result_field=models.CharField(null=True, blank=True, max_length=32)
    result_field_units=models.CharField(null=True, blank=True, max_length=64)
#     mapfile=models.FileField(storage=fs_results,
#                              upload_to=lambda instance, filename: '%s/data_files/wms/%s.map' % (instance.user.pk,
#                                                                                                 instance.pk,),
#                              blank=True, null=True)
#     legendgraphic=models.FileField(storage=fs_results,
#                                    upload_to=lambda instance, filename: '%s/data_files/wms/%s_legend.png' % (instance.user.pk,
#                                                                                                              instance.pk))
    model=models.FileField(storage=fs_results,
                           upload_to=lambda instance, filename: '%s/data_files/%s.py' % (instance.user.pk,
                                                                                         instance.pk,),
                           blank=True, null=True)
    checksum=models.CharField(max_length=50, null=False)
    objects=models.GeoManager()
    
    @property
    def mapfile_path(self):
         path=fs_results.path('{0}/data_files/wms/{1}'.format(self.user.pk, 
                                                              self.pk))
         if not os.path.exists(path):
             try:
                 os.makedirs(path)
             except OSError as e:
                 if e.errno == 17:
                     # Dir already exists. Ignore...
                     pass
         return path
     
    @property
    def bbox(self):
        extent=None
        if not hasattr(self, '_bbox'):
            if self.srid:
                extent=list(self.extent.extent)
            self._bbox=extent
        return self._bbox
    
    @property
    def spatial(self):
        if not self.srid:
            return False
    
    def __init__(self, *args, **kwargs):
        super(DataFile, self).__init__(*args, **kwargs)
        if self.pk:
            self._old_srid=self.srid
        else: self._old_srid=None
    
    @property
    def geojson_name(self):
        return '%s.geojson' % (os.path.splitext(self.name)[0],)
    
    def save(self, *args, **kwargs):
        '''
        Default is pending, but we update that to processing on save - this
        prevents multiple jobs from being submitted.
        '''
        import_datafile=False
        job=kwargs.pop('job', None)
        if self.status==self.PENDING:
            import_datafile=True
            if not job:
                self.status=self.PROCESSING
            else:
                self.status=self.PROCESSING_RESULTS
        if self.file and not self.checksum:
            cs=hashlib.sha1()
            for line in self.file.chunks():
                cs.update(line)
            self.checksum=cs.hexdigest()
        result=super(DataFile, self).save(*args, **kwargs)
        if import_datafile:
            '''
            If the file was just uploaded (status PENDING) then we kick off
            the job to import the file (and set the status to PROCESSING)
            '''
            logger.debug('Dispatching task for %s', self.pk)
            tasks.importDataFile.delay(self, getattr(job,'pk',None))
        return result
    
    def delete(self):
        '''
        Ensure files are deleted when the model instance is removed.
        '''
        delete_candidates=[]
        delete_fields=['processed_file','file',
                      'mapfile', 'legendgraphic']
        # we run into import issues.
        connection=delete_sql=None
        # If we are using PostGIS we need to also delete the table from the database.
    
        delete_fields.append('model')
        connection=connections['default']
        delete_sql='''drop table if exists userdata_results_{0};'''.format(self.pk)
        for field in delete_fields:
            try:
                if getattr(self, field, None):
                    delete_candidates.append(getattr(self, field).path)
                    if field == 'model':
                        compiled_module="{0}s".format(self.model.path)
                        delete_candidates.append(compiled_module)
            except Exception, e:
                logger.exception('Failed to process delete for %s (%s)', 
                                 field, self.pk)
        r=super(DataFile, self).delete()
        for f in delete_candidates:
            if os.path.exists(f):
                os.unlink(f)
        ''' Drop the PostgreSQL table '''
        if delete_sql:
            cursor=connection.cursor()
            cursor.execute(delete_sql)
        return r
        
    def __str__(self):
        return '%s' % (self.name,)
    
    class Meta:
        ordering=['-date_created']
        verbose_name='Data File'
        verbose_name_plural='Data Files'
        db_table='nmtk_data_file'
    
class JobStatus(models.Model):
    '''
    This model holds status updates that are returned by the tool.  It can
    probably be removed at some point after the job completes (or at least
    all but the most recent one can be removed.)
    '''
    job=models.ForeignKey(Job)
    timestamp=models.DateTimeField(auto_now_add=True)
    message=models.CharField(max_length=1024)
    objects=models.GeoManager()
    class Meta:
        ordering=['job__pk','-timestamp']
        verbose_name='Job Status'
        verbose_name_plural='Job Status'
        db_table='nmtk_job_status'
    
class Feedback(models.Model):
    CHOICES=('No Opinion', 'Works', 'Needs Help', 'No Way');
    CHOICES=zip(CHOICES, CHOICES);
    date_created=models.DateTimeField(auto_now_add=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL, null=False)
    uri=models.CharField(max_length=255, null=False, blank=False)
    comments=models.TextField()
    transparency=models.CharField(max_length=16, null=True, choices=CHOICES)
    functionality=models.CharField(max_length=16, null=True, choices=CHOICES)
    usability=models.CharField(max_length=16, null=True, choices=CHOICES)
    performance=models.CharField(max_length=16, null=True, choices=CHOICES)
    class Meta:
        ordering=['-date_created']
        verbose_name='Feedback'
        verbose_name_plural='Feedback Items'
        db_table='nmtk_feedback'

class UserPreference(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL, null=False)
#     divs=models.CharField(null=True, blank=True, max_length=1024,
#                           help_text='A JSON list of divs that are "enabled" in the UI')
    config=models.TextField(null=False, blank=False,
                            help_text='A JSON encoded string containing user preferences')
    class Meta:
        verbose_name='User Preference'
        verbose_name_plural='User Preferences'
        db_table='nmtk_user_preference'

class MapColorStyle(models.Model):
    '''
    A table to hold the available color ramps/colors that we support for
    various things.
    The start and end tuple values should be three-tuples containing an r, g, and b value - limited to an integer
    between 0 and 255
    '''
    description=models.CharField(max_length=255)
    name=models.CharField(max_length=16, null=False)
    other_r=models.IntegerField(null=False, validators=[MaxValueValidator(255),
                                                        MinValueValidator(0),],
                                verbose_name="R")
    other_g=models.IntegerField(null=False, validators=[MaxValueValidator(255),
                                                        MinValueValidator(0),],
                                verbose_name="G")
    other_b=models.IntegerField(null=False, validators=[MaxValueValidator(255),
                                                        MinValueValidator(0),],
                                verbose_name="B")
    default=models.BooleanField(default=False)
    category=models.CharField(max_length=20, null=True)
    ramp_graphic=models.ImageField(storage=fs, upload_to=lambda instance, 
                                   filename: 'color_ramps/%s' % (filename,),
                                   null=True, blank=True)
    
    def ramp_graphic_tag(self):
        '''
        For the admin interface we need to be able to return the Image tag
        for this - which is sent out via the API - so here we reverse the API
        provided url to get it.  Note that if the API version changes then
        this needs to change as well.
        '''
        url=reverse("api_%s_download_ramp_graphic" % ('color_style',),
                    kwargs={'resource_name': 'color_style',
                            'pk': self.pk,
                            'api_name': 'v1'})
        return u'<img src="{0}" />'.format(url)
    ramp_graphic_tag.short_description = 'Image'
    ramp_graphic_tag.allow_tags = True
        
    class Meta:
        verbose_name='Map Color Style'
        verbose_name_plural='Map Color Styles'
        db_table='nmtk_map_color_styles'

    
    @property
    def other_color(self):
        return (self.other_r, self.other_g, self.other_b)

    def save(self, *args, **kwargs):
        '''
        Save the model and then create the image that we need.
        '''
        if self.default:
            # If this one has default checked, turn off the default for
            # other instances - there can be only one!
            for m in MapColorStyle.objects.filter(default=True):
                if m.pk != self.pk:
                    m.default=False
                    m.save()
        if not self.pk:
            super(MapColorStyle, self).save(*args, **kwargs)
        
        legend=LegendGenerator(color_format=self.name,
                               min_value=0, max_value=255)
        im=legend.generateSampleRamp()
        image_file=StringIO.StringIO()
        im.save(image_file, format='png')
        image_file.seek(0, os.SEEK_END)
        len=image_file.tell()
        image_file.seek(0)
        if self.ramp_graphic:
            if os.path.exists(self.ramp_graphic.path):
                os.unlink(self.ramp_graphic.path)
        self.ramp_graphic=InMemoryUploadedFile(image_file, None, 
                                               'ramp_graphic_{0}.png'.format(self.pk,),
                                               'image/png', len, None)
        super(MapColorStyle, self).save(*args, **kwargs)

        
        
