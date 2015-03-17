from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from NMTK_apps.helpers import data_output
from NMTK_server import models
from django.contrib.gis.geos import Polygon


class Command(BaseCommand):
    help = '''Recompute extents for spatial data tables to ensure things are correct.'''
    def handle(self, *args, **options):
        if not settings.NMTK_SERVER:
            raise CommandError('The NMTK Server is not currently enabled')

        for m in models.DataFile.objects.filter(srid__gte=0):
            data_qs=data_output.getQuerySet(m)
            extent=data_qs.extent()
            geometry=Polygon.from_bbox(extent)
            m.extent=str(geometry)
            m.save()
        
        
