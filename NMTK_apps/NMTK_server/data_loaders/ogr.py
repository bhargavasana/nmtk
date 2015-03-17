from osgeo import ogr, osr
import logging
import collections
import datetime
from dateutil.parser import parse
from BaseDataLoader import *
from loaders import FormatException

logger=logging.getLogger(__name__)

class OGRLoader(BaseDataLoader):
    name='OGR'
    
    types={ogr.wkbPoint: 'POINT',
           ogr.wkbGeometryCollection: 'GEOMETRYCOLLECTION',
           ogr.wkbLineString: 'LINESTRING',
           ogr.wkbMultiPoint: 'MULTIPOINT',
           ogr.wkbMultiPolygon: 'MULTIPOLYGON',
           ogr.wkbPolygon: 'POLYGON',
           ogr.wkbMultiLineString: 'MULTILINESTRING',}
    
    type_conversions={ogr.wkbPoint: (ogr.wkbMultiPoint,ogr.ForceToMultiPoint),
                      ogr.wkbLineString: (ogr.wkbMultiLineString,ogr.ForceToMultiLineString),
                      ogr.wkbPolygon: (ogr.wkbMultiPolygon,ogr.ForceToMultiPolygon)}
    
    def __init__(self, *args, **kwargs):
        '''
        A reader for OGR supported file types using Fiona, like the other
        loader this will eventally be iterated over and should return
        a set of tuples that include a field dict and a geometry as WKT
        '''
        self._srid=kwargs.pop('srid',None)
        self._dimensions=kwargs.pop('dimensions',2)
        self.datefields={}
        super(OGRLoader, self).__init__(*args, **kwargs)
        for fn in self.filelist:
            self.ogr_obj=ogr.Open(fn)
            try:
                self.data
            except:
                logger.exception('Failed to open file %s', fn)
                self.ogr_obj=None
            if self.ogr_obj is not None:
                self.spatial=True
                self.format=self.ogr_obj.GetDriver().name
                logger.debug('The format of the file is %s', self.format)
                self.filename=fn
                break
    
    
    @property
    def dimensions(self):
        return self._dimensions
    
    def determineGeometryType(self, layer):
        '''
        In the case of a KML/KMZ file, we need to iterate over the data to determine
        the appropriate geometry type to use.
        '''
        if (not hasattr(self,'_determineGeometryType')):
            self._determineGeometryType=ogr.wkbPoint
            geom_types=set()
            while True:
                feat=layer.GetNextFeature()
                if not feat: break
                try:
                    geom=feat.geometry()
                    if not geom:
                        logger.debug('Skipping apparent null geometry!')
                        continue
                    # Get the dimensions of the geometry.
                    self._dimensions=max(geom.GetCoordinateDimension(), self._dimensions)
                    geom_types.add(geom.GetGeometryName())
                except Exception, e:
                    logger.exception('Failed to get geometry type when iterating over data during ingest')
            layer.ResetReading()
            geom_types_string=' '.join(geom_types)
            if 'POINT' in geom_types_string:
                self._determineGeometryType=ogr.wkbPoint
            elif 'LINE' in geom_types_string:
                self._determineGeometryType=ogr.wkbLine
            elif 'POLY' in geom_types_string:
                self._determineGeometryType=ogr.wkbPolygon
        return self._determineGeometryType
    
    def __iter__(self):
        self.data.layer.ResetReading()
        return self 

    def next(self):
        '''
        The iterator shall return a dictionary of key/value pairs for each
        iteration over a particular feature.  It will always return a two-tuple
        that contains both the attributes and the geometry.
        '''
        geom_column=None
        feature=self.data.layer.GetNextFeature()
        if not feature:
            raise StopIteration
        else:
            feature=self.geomTransform(feature)
            data=dict((field, getattr(feature, field)) for field in self.fields())
            # It seems that sometimes OGR is returning a non-valid (for django) date string
            # rather than a date/datetime/time instance.  Here we check if that is the case,
            # and if it is then we will simply use dateutil's parser to parse the value
            # if that fails, then we just proceed and hope for the best..
            for field,type in self.datefields.iteritems():
                if not isinstance(data[field], (datetime.datetime, datetime.date, datetime.time)):
                    try:
                        if data[field]:
                            v=parse(data[field])
                            data[field]=v
                    except: 
                        logger.exception('Failed to parse field %s, value %s with dateutil\'s parser - wierd!',
                                         field, data[field])
            geom=feature.geometry()
            if geom:
                wkt=geom.ExportToWkt()
            else:
                wkt=None
            return (data, wkt)

    @property
    def spatial_type(self):
        return self.data.type
    
    @property
    def feature_count(self):
        return self.data.feature_count

    @property
    def srs(self):
        return self.data.srs
    
    @property
    def srid(self):
        return self.data.srid

    def is_supported(self):
        '''
        Indicate whether or not this loader is able to process this
        file type.  If it is, return True, otherwise return False.
        
        In this case, we return true if it's an OGR supported file type.
        '''
        if self.ogr_obj:
            return True
        return False
    
    def geomTransform(self, feature):
        if feature:
            transform=getattr(self, '_geomTransform', None)
            if transform or self.data.reprojection:
                geom=feature.geometry()
                if geom:
                    if transform:
                        geom=transform(geom)
                    if self.data.reprojection:
                        geom.Transform( self.data.reprojection )
                    # in theory this makes a copy of the geometry, which
                    # feature then copies - but it seems to fix the crashing issue.
                    feature.SetGeometry(geom.Clone())
        return feature 
    
    def fields(self):
        '''
        This was changed so now our field list is actually a list of fields
        and their respective data types.  So now we need to preserve the support
        of retrieval of fields for backwards compatibility.
        '''
        return [field for field, type, ogr_type in self.data.fields]
    
    def fields_types(self):
        '''
        This returns a list of tuples, with the first being a field name
        and the second element of each being the python type of the field.
        '''
        return [(field, type) for field, type, ogr_type in self.data.fields]            
    
    def ogr_fields_types(self):
        '''
        This returns a list of tuples, with the first being a field name
        and the second element of each being the python type of the field.
        '''
        return [(field, ogr_type) for field, type, ogr_type in self.data.fields] 
    
    @property
    def extent(self):
        return (self.data.extent[0], self.data.extent[2],
                self.data.extent[1], self.data.extent[3],)
    
    @property
    def data(self):
        '''
        Read the output file and provide an iterable result
        '''
        if not hasattr(self, '_data'):
            layer=geom_extent=geom_type=spatial_ref=geom_srid=None
            # If we get here, then we have successfully determined the file type
            # that was provided, using OGR.  ogr_obj contains the OGR DataSource
            # object, and fn contains the name of the file we read to get that.
            
            # We only support single layer uploads, if there is more than one
            # layer then we will raise an exception
            if self.ogr_obj.GetLayerCount() <> 1:
                raise FormatException('Too many (or too few) layers recognized ' +
                                      'in this data source (%s layers)',
                                      self.ogr_obj.GetLayerCount() )
            driver=self.ogr_obj.GetDriver()
            # Deny VRT files, since they can be used to reference any file on the
            # filesystem, and even external URLs.
            if 'vrt' in str(driver).lower():
                raise FormatException('VRT format datafiles are not currently ' +
                                      'supported')
            
            layer=self.ogr_obj.GetLayer()
            geom_extent=layer.GetExtent()
            geom_type=layer.GetGeomType()
            if geom_type == 0: # We can determine it experimentally if possible...
                geom_type=self.determineGeometryType(layer)
            if geom_type not in self.types:
                raise FormatException('Unsupported Geometry Type (%s)' % (geom_type,))
            spatial_ref=layer.GetSpatialRef()
            if spatial_ref and not self._srid:
                spatial_ref.AutoIdentifyEPSG()
                geom_srid=self._srid or spatial_ref.GetAuthorityCode(None)
            elif self._srid:
                geom_srid=self._srid
                srs=osr.SpatialReference()
                epsg=str('EPSG:%s' % (geom_srid,))
                logger.debug('Setting output SRID to %s (%s)', 
                             epsg, type(epsg))
                srs.SetFromUserInput(epsg)
            if (geom_srid <= 0 or geom_srid is None) and not spatial_ref:
                raise FormatException('Unable to determine valid SRID ' + 
                                      'for this data')
                
            # Get fields and their types by looping over one row of features.
            fields=[]
            type_lookups={ogr.OFTReal: float,
                          ogr.OFTInteger: int,
                          ogr.OFTString: str,
                          ogr.OFTIntegerList: None,
                          ogr.OFTRealList: None,
                          ogr.OFTStringList: None,
                          ogr.OFTDate: datetime.date,
                          ogr.OFTTime: datetime.time,
                          ogr.OFTDateTime: datetime.datetime }
            for feat in layer:
                for i in range(feat.GetFieldCount()):
                    field_definition=feat.GetFieldDefnRef(i)
                    field_type=type_lookups.get(field_definition.GetType(), None)
                    field_name=field_definition.GetNameRef()
                    if field_type:
                        fields.append((field_name,
                                       field_type,
                                       field_definition.GetType()))
                        # it appears that sometimes OGR isn't giving us a date type when we iterate
                        # over values, so we will store the date types and convert if needed when we 
                        # iterate over the results.
                        if field_type in (datetime.date, datetime.time, datetime.datetime):
                            self.datefields[field_name]=field_type
                    else: 
                        raise FormatException('The field {0} is of an unsupported type'.format(field_name,))
                break
    #         logger.debug('Fields are %s', fields)
            # Just to be on the safe side..
            layer.ResetReading()
            
            OGRResult=collections.namedtuple('OGRResult',
                                             ['srid',
                                              'extent',
                                              'srs',
                                              'layer',
                                              'feature_count',
                                              'ogr',
                                              'type',
                                              'type_text',
                                              'fields',
                                              'reprojection', 
                                              'dest_srs',
                                              'dim',])
            # Note that we must preserve the OGR object here (even though
            # we do not use it elsewhere), because
            # otherwise it gets garbage collected, and the OGR Layer object
            # will break.
            if geom_type in self.type_conversions:
                logger.debug('Converting geometry from %s to %s (geom_type upgrade)',
                             geom_type, self.type_conversions[geom_type][0])
                geom_type, self._geomTransform=self.type_conversions[geom_type]
            else:
                self._geomTransform=lambda a: a
            
            epsg_4326=osr.SpatialReference()
            epsg_4326.SetWellKnownGeogCS("EPSG:4326")
            if (not spatial_ref.IsSame(epsg_4326)):
                reprojection=osr.CoordinateTransformation( spatial_ref, epsg_4326 )
            else:
                reprojection=None
            self._data=OGRResult(srid=geom_srid,
                                 extent=geom_extent,
                                 ogr=self.ogr_obj,
                                 layer=layer,
                                 srs=spatial_ref,
                                 feature_count=layer.GetFeatureCount(),
                                 type=geom_type,
                                 type_text=self.types[geom_type],
                                 fields=fields,
                                 dest_srs=epsg_4326,
                                 reprojection=reprojection,
                                 dim=self.dimensions)
        return self._data