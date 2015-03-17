from setuptools import archive_util
import tempfile
from django.conf import settings
import shutil
import os
import logging
from django.utils.importlib import import_module
from django.core import exceptions
import collections
import logging
import io
import simplejson as json
from osgeo import ogr, osr

__all__=['FormatException',]

TYPES={ogr.wkbPoint: 'POINT',
       ogr.wkbGeometryCollection: 'GEOMETRYCOLLECTION',
       ogr.wkbLineString: 'LINESTRING',
       ogr.wkbMultiPoint: 'MULTIPOINT',
       ogr.wkbMultiPolygon: 'MULTIPOLYGON',
       ogr.wkbPolygon: 'POLYGON',
       ogr.wkbMultiLineString: 'MULTILINESTRING',}

logger=logging.getLogger(__name__)
class FormatException(Exception): 
    '''
    An exception raised when the loader was unable to determine the type of the
    input file (or files, in the case of an archive.) or there is some kind
    of format error - such as no provided SRID, too many layers, etc.
    '''
    pass

DEFAULT_LOADERS=['NMTK_server.data_loaders.ogr.OGRLoader',
                 'NMTK_server.data_loaders.csv.CSVLoader']

class NMTKDataLoader(object):
    '''
    A data file loader that accepts a wide range of file types and returns
    several interfaces to them - including an iterator for looping over
    the data.  The idea here is that a wide range of file formats are supported
    using a simplified interface.
    '''
    def __init__(self, filename, srid=None):
        '''
        On init, unpack the directory containing the files and
        generate an inventory of files.  
        '''
        kwargs={}
        if srid:
            kwargs={'srid': srid}
        self.working_dir=tempfile.mkdtemp()
        self.filename=filename
        self.data=None
        self.load_driver(**kwargs)
        
    @property
    def is_spatial(self):
        '''
        Return true if the driver being used returns a spatial result.
        '''
        if hasattr(self, 'dl_instance'):
            return getattr(self.dl_instance, 'spatial', False)
        else:
            return False
    
    def fields(self):
        if hasattr(self, 'dl_instance'):
            return self.dl_instance.fields()
        else:
            return False
    
    def fields_types(self):
        if hasattr(self, 'dl_instance'):
            return self.dl_instance.fields_types()
        else:
            return False

    def ogr_fields_types(self):
        if hasattr(self, 'dl_instance'):
            return self.dl_instance.ogr_fields_types()
        else:
            return False
     
    def __del__(self):
        '''
        Once processing is done, we need to clean up the files that were
        generated when we unpacked the archive (assuming it was an archive.)
        '''
        shutil.rmtree(self.working_dir,
                      ignore_errors=True)
        
    def load_driver(self, *args, **kwargs):
        for dl_path in getattr(settings, 'DATA_LOADERS', DEFAULT_LOADERS):
            try:
                dl_module, dl_classname=dl_path.rsplit('.',1)
                logger.debug('Loadgin module: %s, %s',
                             dl_module, dl_classname)
            except ValueError:
                raise exceptions.ImproperlyConfigured('%s isn\'t a data_loader module' % dl_path)
            try:
                mod=import_module(dl_module)
            except ImportError as e:
                raise exceptions.ImproperlyConfigured('Error importing data_loader %s: "%s"' % (dl_module, e))
            try:
                dl_class=getattr(mod, dl_classname)
            except AttributeError as e:
                raise exceptions.ImproperlyConfigured('DataLoader module "%s" does not define a "%s" class' % (dl_module, dl_classname))
            logger.debug('Loading %s', dl_classname)
            dl_instance=dl_class(self.get_filelist(), *args, **kwargs)
            if dl_instance.is_supported():
                self.dl_instance=dl_instance
                return dl_instance.name
        return None 
             
    @property
    def info(self):
        '''
        Returns an info object which contains all the information that 
        we were able to determine about this particular datafile.
        
        Generally, it's a good idea to get the feature count *after* getting the
        data, since otherwise the loader might need to iterate over all the
        data to count the features.
        '''
        if not getattr(self,'dl_instance', None):
            return None
        if not hasattr(self, '_loader_result'):
            LoaderResult=collections.namedtuple('LoaderResult',
                                                ['spatial',
                                                 'srid',
                                                 'type',
                                                 'feature_count',
                                                 'fields',
                                                 'fields_types',
                                                 'ogr_fields_types',
                                                 'format',
                                                 'loader',
                                                 'extent',
                                                 'srs', 
                                                 'dest_srs',
                                                 'dimensions',])
                                        
            self._loader_result=LoaderResult(self.is_spatial,
                                             getattr(self.dl_instance,'srid', None),
                                             getattr(self.dl_instance,'spatial_type', None),
                                             self.dl_instance.feature_count,
                                             self.fields(),
                                             self.fields_types(),
                                             self.ogr_fields_types(),
                                             self.dl_instance.format,
                                             self.dl_instance.name,
                                             getattr(self.dl_instance,'extent', None),
                                             getattr(self.dl_instance,'srs', None),
                                             getattr(self.dl_instance,'dest_srs', None),
                                             getattr(self.dl_instance,'dimensions', None),
                                             )
        
        return self._loader_result
    
    def export_json(self, filename):
        '''
        For non-spatial data we can output the data to json, for spatial we
        will output as spatial
        '''
        # Handle datetime.date, datetime.time, and datetime.datetime formats.
        date_handler=lambda data: data.isoformat() if hasattr(data, 'isoformat') else data
        if self.is_spatial:
            return self.export_geojson(filename)
        data=[]
        for row, geom in self:
            data.append(row)
        with io.open(filename, 'w', encoding='utf-8') as f:
            f.write(unicode(json.dumps(data, ensure_ascii=False,
                                       default=date_handler)))
    
    def export_geojson(self, filename):
        '''
        This iterates over itself to create a geojson export file.  The file
        will be placed at the specified filename, overwriting whatever is there
        (if anything)
        '''
        # Get the GeoJSON driver and generate the output file.
        driver = ogr.GetDriverByName('GeoJSON')
        # OGR Driver will not overwrite files, so we will delete it if it is there.
        if os.path.exists(filename):
            os.unlink(filename)
        datasource = driver.CreateDataSource(filename)
        
        srs=osr.SpatialReference()
        srs.SetWellKnownGeogCS('EPSG:{0}'.format(self.info.srid))
        layer=datasource.CreateLayer('GeoJSON',
                                     geom_type=self.info.type,
                                     srs=srs)
        # Create the fields in the data file
        for field_name, field_type in self.info.ogr_fields_types:
            logger.debug('Create field - name is %s', field_name)
            field_defn = ogr.FieldDefn(field_name.decode('utf-8').encode('utf-8', 'ignore'), 
                                       field_type )
            if layer.CreateField ( field_defn ) != 0:
                logger.debug("Creating %s field failed.", field_name)
                raise Exception('Failed to create field!')
        
        # Iterate over each of the features and create the elements in the
        # supporting layer.
        for properties, geom_wkt in self:
            feat=ogr.Feature(layer.GetLayerDefn())
            
            for k,v in properties.iteritems():
                if isinstance(k, (str, unicode,)):
                    k=k.decode('utf-8').encode('utf-8', 'ignore')
                if isinstance(v, (str, unicode,)):
                    v=v.decode('utf-8').encode('utf-8', 'ignore')
                feat.SetField(k, v)
            geom=ogr.CreateGeometryFromWkt(geom_wkt)
            feat.SetGeometry(geom)
            layer.CreateFeature(feat)
        
        layer.SyncToDisk()
        datasource.SyncToDisk()
    
    def __iter__(self):
        '''
        When iterating over the data, just use the iterator provided by
        the driver...
        '''    
        return iter(self.dl_instance)
    
    def _progress_filter(self, src, dest):
        return os.path.join(self.working_dir, os.path.basename(src))
       
    def get_filelist(self):
        '''
        Unpack the archive if it is an archive, and return a list of 
        file names that should be examined by OGR to determine if they are
        OGR supported file types.
        
        Cache the result to speed up subsequent calls.
        '''
        if not hasattr(self, '_files'):
            name, extension=os.path.splitext(self.filename)
            # only handle a few types, since some of the others might mess 
            # up some processing...like xlsx (which this will unpack.)
            logger.debug('Extension is %s', extension)
            if extension.lower() in ('.zip','.gz','.tgz'):
                try:
                    # Ensure that the files are output in the working dir, and 
                    # subdirectories are omitted (so it's a flat dir structure)
                    archive_util.unpack_archive(self.filename, self.working_dir,
                                                progress_filter=self._progress_filter)
                    logger.debug('Unpacked archive %s to %s', self.filename, 
                                 self.working_dir)
                    files=[fn for fn in map(lambda dir: os.path.join(self.working_dir, 
                                                                     dir),
                                            os.listdir(self.working_dir)) 
                                            if not os.path.isdir(fn)]
                    self._files=files
                except archive_util.UnrecognizedFormat, e:
                    logger.debug('Specified file (%s) is not a recognized archive',
                                 self.filename)
                    self._files=[self.filename,]
            else:
                self._files=[self.filename,]
        logger.debug('File list is %s', self._files)
        return self._files


if __name__ == '__main__':
    # A local test run to load some data...
    pass
    