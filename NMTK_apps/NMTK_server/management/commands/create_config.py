from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib import sites
from django.conf import settings
import hashlib
import simplejson as json
import string
import random
import sys
User=get_user_model()


class Command(BaseCommand):
    help = '''Create a JSON configuration usable by the test infrastructure.
              Note: This requires the NMTK_BASE_URL setting in settings.py to 
              function.'''
    def handle(self, *args, **options):
        if not settings.NMTK_SERVER:
            raise CommandError('The NMTK Server is not currently enabled')
        # Get the current
        site_id=getattr(settings, 'SITE_ID', 1)
        site_domain = sites.models.Site.objects.get(pk=site_id).domain
        username=self.id_generator()
        password=self.id_generator(size=13)
        email='test_user@%s' % (site_domain,)

        user=User.objects.create_user(username, email, password)
        user.first_name='TEST'
        user.last_name='USER'
        user.is_superuser=True
        user.is_staff=True
        user.save()
        site_url='http://%s' % (site_domain,)
        config={'username': username,
                'password': password,
                'site_url': site_url,}
        print "**NOTE: Configuration output appears on standard error"
        print >>sys.stderr, json.dumps(config)
        
    
    def id_generator(self, size=6, 
                     chars=string.ascii_lowercase + string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for x in range(size))
        
        
