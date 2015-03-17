from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

class Command(BaseCommand):
    help = 'Exit 0 if the tool server is enabled'
    def handle(self, *args, **options):  
        exit(0)
