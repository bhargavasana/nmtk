from osgeo import ogr, osr
import logging
import collections
from BaseDataLoader import *

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
        super(OGRLoader, self).__init__(*args, **kwargs)
        for fn in self.filelist:
            self.ogr_obj=ogr.Open(fn)
            try:
                self.data
            except:
                self.ogr_obj=None
            if self.ogr_obj is not None:
                self.spatial=True
                self.format=self.ogr_obj.GetDriver().name
                self.filename=fn
                break
    
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
            data=dict((field, getattr(feature, field)) for field in self.data.fields)
            # Try to use a column name of geometry, but in the case that 
            # is already in use, choose another one numbered from geometry_1-10
            wkt=feature.geometry().ExportToWkt()
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
                if transform:
                    geom=transform(geom)
                if self.data.reprojection:
                    geom.Transform( self.data.reprojection )
                # in theory this makes a copy of the geometry, which
                # feature then copies - but it seems to fix the crashing issue.
                feature.SetGeometry(geom.Clone())
        return feature 
    
    def fields(self):
        return self.data.fields
    
    @property
    def extent(self):
        return self.data.extent
    
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
                
            # Get fields by looping over one row of features.
            fields=[]
            for feat in layer:
                for i in range(feat.GetFieldCount()):
                    field_definition=feat.GetFieldDefnRef(i)
                    fields.append(field_definition.GetNameRef ())
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
                                              'fields','reprojection', 
                                              'dest_srs'])
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
                                 reprojection=reprojection)
        return self._data