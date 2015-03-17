from django.conf import settings
import imp
import xlwt
import csv
import cStringIO as StringIO
from django.http import HttpResponse
import simplejson as json
from django.db.models import Q
from django.contrib.gis.geos import Polygon, Point
import math
import logging
logger=logging.getLogger(__name__)



def getBbox(long, lat, zoom_level, pixels=5):
    '''
    Given a point (lat/lon), zoom number (in spherical mercator) and pixel 
    tolerance, compute and return a BBOX geometry
    '''
    try:
        p=Point(long, lat, srid=4326)
        logger.debug('Got point of %s', p.coords)
        p.transform(3857)
        x,y=p.coords
        logger.debug('Transformed %s to 3857', p.coords)
        # Get the number of meters per pixel...
        # At zoom level 0 (at the equator) there are ~156413 m/pixel, then it halves for
        # each zoom level beyond that...
        resolution=156543.03392804062/(2**zoom_level)
        spacing=pixels*resolution

        p=Point(x-spacing, y-spacing, srid=3857)
        p.transform(4326)
        xv1,yv1=p.coords
        p=Point(x+spacing, y+spacing, srid=3857)
        p.transform(4326)
        xv2,yv2=p.coords

        xmin=min(xv1,xv2)
        xmax=max(xv1,xv2)
        ymin=min(yv1, yv2)
        ymax=max(yv1,yv2)
        return Polygon.from_bbox((xmin,ymin,xmax,ymax))
    except OverflowError, e:
        logger.exception('Overflow reverse-mapping from mercator to lat/long')
        return None
        

def getQuerySet(datafile):
    '''
    Given a datafile record, return a spatialite queryset representing the datafile results.
    '''
    model=imp.load_source('%s.models' % (datafile.pk,),datafile.model.path)
    # In this case we need to use the model stored inside the PostGIS database,
    # so we omit the using() and instead go right for the data...
    qs=getattr(model, 'Results_{0}'.format(datafile.pk)).objects.all()
    return qs

def stream_csv(datafile):
    csvfile=StringIO.StringIO()
    csvwriter=csv.writer(csvfile)
    qs=getQuerySet(datafile)
    row=qs[0]
    db_map=[(field.db_column or field.name, field.name) for
             field in row._meta.fields if field.name and field.name not in ('nmtk_id',
                                                                            'nmtk_geometry',
                                                                            'nmtk_feature_id')]
    def read_and_flush():
        csvfile.seek(0)
        data=csvfile.read()
        csvfile.seek(0)
        csvfile.truncate()
        return data
    
    def data():
        # Output the CSV headings
        csvwriter.writerow([i[0] for i in db_map])
        for row in qs:
            csvwriter.writerow([getattr(row, mf) for dbf, mf in db_map])
        data=read_and_flush()
        yield data
        
    response=HttpResponse(data(), mimetype="text/csv")
    response.streaming=True
    response['Content-Disposition']="attachment; filename=results.csv"
    return response

def stream_xls(datafile):
    try:
        qs=getQuerySet(datafile)
        row=qs[0]
        db_map=[(field.db_column or field.name, field.name) for
                 field in row._meta.fields if field.name not in ('nmtk_id','nmtk_geometry',
                                                                 'nmtk_feature_id')]
        font0 = xlwt.Font()
        font0.name = 'Times New Roman'
        font0.colour_index = 2
        font0.bold = True
        font1=xlwt.Font()
        font1.name='Times New Roman'
        style0 = xlwt.XFStyle()
        style0.font = font0
        style1 = xlwt.XFStyle()
        style1.font = font1
        wb = xlwt.Workbook()
        ws = wb.add_sheet('NMTK Results')
        rowid=0
        for i, v in enumerate(db_map):
            ws.write(rowid, i, v[0], style0)
        for row in qs:
            rowid += 1
            for i, v in enumerate(db_map):
                ws.write(rowid, i, getattr(row, v[1]), style1)
        logger.debug('Getting ready to return XLS response...')
        response=HttpResponse(mimetype="application/ms-excel")
        response.streaming=True
        response['Content-Disposition']="attachment; filename=results.xls"
        wb.save(response)
        return response
    except:
        logger.exception('Something went wrong!')
    
def data_query(request, datafile):
    '''
    This is the case where we are requesting a paged result set - typically from
    the results view page of the UI.
    '''
    # Get a queryset that is unfiltered.
    qs=getQuerySet(datafile)
   
    # if lat, lon, and zoom were provided, then we can do a bbox generation...
    if min([request.GET.has_key(key) for key in ('lat','lon','zoom')]):
        try:
            lat=float(request.GET.get('lat'))
            long=float(request.GET.get('lon'))
            # Get the zoom and compute the resolution.
            zoom=int(request.GET.get('zoom'))
            pixels=int(request.GET.get('pixels', 5))
            
            bbox=getBbox(long,lat,zoom,pixels)
            if bbox:
                logger.debug('Found BBOx of %s given long: %s, lat: %s, zoom: %s, pixles: %s',
                             bbox, long, lat, zoom, pixels)
                qs=qs.filter(nmtk_geometry__intersects=bbox)
        except:
            logger.exception('Something went wrong with geo_query parameters?')
    ids=request.GET.get('id', None)
    if ids:
        ids=ids.split(',')
        qs=qs.filter(nmtk_id__in=ids)
    qs=qs.order_by('nmtk_id')
    if len(qs):
        row=qs[0]
        db_map=[(field.db_column or field.name, field.name) for
                 field in row._meta.fields if field.name not in ('nmtk_geometry',
                                                                 'nmtk_feature_id')]
    sstring=None
    if request.GET.has_key('search'):
        '''
        Handle the text search against the data fields.
        '''
        sstring=request.GET['search']
        filter=reduce(lambda q, field: q|Q(**{'{0}__icontains'.format(field): sstring}),
                      (field for (db_field, field) in db_map), Q())
        qs=qs.filter(filter)
    result={'data': [],
            'meta': {'total': qs.count(),
                     'order': 'nmtk_id', }
            }
    if sstring:
        result['meta']['search']=sstring
    for row in qs:
        data={}
        for db_col, col in db_map:
            data[db_col]=getattr(row, col)
        result['data'].append(data)
        
    date_handler=lambda data: data.isoformat() if hasattr(data, 'isoformat') else data
    return HttpResponse(json.dumps(result,
                                   default=date_handler), mimetype='application/json')

def pager_output(request, datafile):
    try:
        offset=int(request.GET.get('offset',0))
    except: 
        offset=0
    try:
        limit=int(request.GET.get('limit', 0))
    except: 
        limit=20
    order=request.GET.get('order_by', 'nmtk_id').lower()
    qs=getQuerySet(datafile)
    # Our requests for data come in as GET requests - so we're somewhat
    # limited in terms of filter sizes here.  However, in this case we
    # can do our best.  The assumption is that a JSON string is provided 
    # for the filters GET parameter.  We parse that and get a set of key/value
    # pairs in an object form, that we can then pass in as filter parameters
    # to the ORM.
    filters={}
    if request.GET.has_key('filters'):
        try:
            filters=json.loads(request.GET['filters'])
            logger.info('Got filters of %s', filters)
            for filter_data in filters:
                qs=qs.filter(**{filter_data[0]: filter_data[1]})
        except Exception, e:
            logger.exception('Got invalid JSON string for filters (%s), skipping filters',
                             request.GET['filters'])
    sstring=None
    if qs.count():
        row=qs[0]
        db_map=[(field.db_column or field.name, field.name) for
                 field in row._meta.fields if field.name.lower() not in ('nmtk_geometry',
                                                                         'nmtk_feature_id')]
        # Detect user specified ordering, if provided.
        if order.startswith('-'):
            order_field=order[1:].lower()
        else:
            order_field=order.lower()
        if order_field not in [col.lower() for col, name in db_map]:
            order='nmtk_id'
        qs=qs.order_by(order)
        
        
        if request.GET.get('search', None):
            '''
            Handle the text search against the data fields.
            '''
            sstring=request.GET['search']
            filter=reduce(lambda q, field: q|Q(**{'{0}__icontains'.format(field): sstring}),
                          (field for (db_field, field) in db_map), Q())
            qs=qs.filter(filter)
    
    
    result={'data': [],
            'meta': {'limit': limit,
                     'offset': offset,
                     'total': qs.count(),
                     'order': order,
                     'search': sstring,
                     'filters': filters}
            }
    if result['meta']['total']:
        if limit:
            qs=qs[offset:limit+offset]
        else:
            qs=qs[offset:]
        for row in qs:
            data={}
            for db_col, col in db_map:
                if col != 'nmtk_geometry':
                    data[db_col]=getattr(row, col)
            result['data'].append(data)
    date_handler=lambda data: data.isoformat() if hasattr(data, 'isoformat') else data
    return HttpResponse(json.dumps(result,
                                   default=date_handler), mimetype='application/json')