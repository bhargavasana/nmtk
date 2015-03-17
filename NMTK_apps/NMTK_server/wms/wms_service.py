from django.http import HttpResponse, HttpResponseBadRequest
import subprocess
from django.conf import settings

from NMTK_server.wms import djpaste
import logging
# from lockfile import LockFile, AlreadyLocked
import os
from NMTK_server.wms.legend import LegendGenerator
import time
from NMTK_server import tasks
from django.template.loader import render_to_string
from NMTK_server import models

logger=logging.getLogger(__name__)


def generateMapfile(datafile, style_field,
                    color_values):
    dbtype='postgis'
    data={'datafile': datafile,
          'dbtype': dbtype,
          'result_field': style_field,
          'colors': color_values,
          'unmatched_color': color_values.unmatched(),
          'mapserver_template': settings.MAPSERVER_TEMPLATE }
    data['connectiontype']='POSTGIS'
    dbs=settings.DATABASES['default']
    data['connection']='''host={0} dbname={1} user={2} password={3} port={4}'''.format(dbs.get('HOST', None) or 'localhost',
                                                                                       dbs.get('NAME'),
                                                                                       dbs.get('USER'),
                                                                                       dbs.get('PASSWORD'),
                                                                                       dbs.get('PORT', None) or '5432')
    data['data']='nmtk_geometry from userdata_results_{0}'.format(datafile.id)
    data['highlight_data']='''nmtk_geometry from (select * from userdata_results_{0} where nmtk_id in (%ids%)) as subquery
                              using unique nmtk_id'''.format(datafile.id)
    
    # Determine which of the mapfile types to use (point, line, polygon...)
    for geom_type in ['point','line','polygon']:
        if geom_type in datafile.get_geom_type_display().lower():
            break
    data['geom_type']=geom_type
    res=render_to_string('NMTK_server/mapfile_common.map', 
                         data)
    return res

def handleWMSRequest(request, datafile):
    get_uc=dict((k.upper(),v) for k,v in request.GET.iteritems())
    style_field=get_uc.get('STYLE_FIELD', datafile.result_field or None)
    legend_units=get_uc.get('LEGEND_UNITS', None)
    reverse=get_uc.get('REVERSE', 'false')
    if reverse.lower() in ('true','t','1'):
        reverse=True
    else:
        reverse=False
    ramp=get_uc.get('RAMP', 0)
    attributes=datafile.field_attributes
    if style_field == datafile.result_field:
        legend_units=datafile.result_field_units
    if style_field and style_field not in attributes:
        logger.error('Field specified (%s) does not exist.', style_field)
        return HttpResponseBadRequest('Specified style field ({0}) does not exist'.format(style_field))
    if style_field:  
        field_attributes=attributes[style_field]
        logger.debug('Field attributes for %s are %s', style_field, field_attributes)
    else:
        field_attributes={}
    min_result=max_result=None
    values_list=field_attributes.get('values',[])
    if (field_attributes.has_key('type') and 
        field_attributes.get('type', None) not in ('text','date',)
        and not field_attributes.has_key('values')):
        min_result=field_attributes['min']
        max_result=field_attributes['max']

    other_features_color=None
    try:
        ramp=int(ramp)
    except Exception, e:
        return HttpResponseBadRequest('Invalid color ramp specified (integer value is required)')
    if ramp: # Note that 0 means the default ramp
        ramp_lookup_kwargs={'pk': ramp}  
    else:
        ramp_lookup_kwargs={'default': True}
    try:
        color_ramp_identifier=models.MapColorStyle.objects.get(**ramp_lookup_kwargs)
        ramp_id=color_ramp_identifier.pk
        # If we have an enumerated set of values then there is no "other color"
        if not field_attributes.has_key('values'):
            other_features_color=color_ramp_identifier.other_color
    except Exception, e:
        return HttpResponseBadRequest('Invalid color ramp specified {0}'.format(ramp))
    
    legend=LegendGenerator(color_ramp_identifier.name, 
                           min_value=min_result, max_value=max_result, 
                           reverse=reverse,
                           values_list=values_list,
                           units=legend_units,
                           other_features_color=other_features_color,
                           column_type=field_attributes.get('type', None))

    # If there's a values_list then we'll let the WMS server generate the 
    # legend, since it would be using discrete colors anyway, and would be better
    # at creating the legend.
    if get_uc.get('REQUEST', '').lower() == 'getlegendgraphic':
        # Round the value to 4 significant digits.
        im=legend.generateLegendGraphic(width=410)
        response=HttpResponse(content_type='image/png')
        im.save(response, 'png')
        return response
    try:
        # Assume that the ramp won't change once it is made, so here we will 
        # just use the ramp id and datafile pk to specify a unique WMS
        # service, so we don't need to keep creating WMS services.
        if reverse:
            base_name='wms_r_'
        else:
            base_name='wms_'
        if 'field_name' in field_attributes:
            mapfile_path=os.path.join(datafile.mapfile_path, 
                                      "{0}{1}_ramp_{2}_{3}.map".format(base_name, 
                                                                       datafile.pk,
                                                                       ramp_id,
                                                                       field_attributes['field_name']) )
        else:
             mapfile_path=os.path.join(datafile.mapfile_path, 
                                       "{0}{1}_ramp_{2}.map".format(base_name,
                                                                    datafile.pk,
                                                                    ramp_id))
        if not os.path.exists(mapfile_path):
            if not os.path.exists(mapfile_path):
#                 lock=LockFile(mapfile_path)
                try:
#                     lock.acquire(0)
                    mf=generateMapfile(datafile, 
                                       style_field=style_field,
                                       # Iterating over the legend object will return the colors
                                       # so we need only pass that into the mapfile gen code.
                                       color_values=legend)
                    with open(mapfile_path, 'w') as mapfile:
                        mapfile.write(mf)
#                 except AlreadyLocked:
#                     logger.debug('Waiting for lock to be released')
#                     start=time.time()
#                     while lock.is_locked() and (time.time()-start) > 5 :
#                         time.sleep(.0025)
                finally: 
                    pass
#                     lock.release()
        # Create the app to call mapserver.
        app=djpaste.CGIApplication(global_conf=None, 
                                   script=settings.MAPSERV_PATH,
                                   include_os_environ=True,
                                   query_string=request.META['QUERY_STRING'],
                                   )
        environ=request.META.copy()
        environ['MS_MAPFILE']=str(mapfile_path)
        return app(request, environ)
    except djpaste.CGIError, e:
        logger.exception(e)
        return HttpResponseBadRequest()
    