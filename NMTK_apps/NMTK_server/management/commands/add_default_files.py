from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from NMTK_server.default_data.init_account import setupAccount
from django.conf import settings
User=get_user_model()

class Command(BaseCommand):
    help = 'Add default files to user accounts ' + \
           '(all accounts, or specify space-separate names on the command line).'
    def handle(self, *args, **options):
        if not settings.NMTK_SERVER:
            raise CommandError('The NMTK Server is not currently enabled')
        if args:
            qs = User.objects.filter(username__in=args)
        else:
            qs = User.objects.all()

        if qs.exists():
            for user in qs:
                if user.datafile_set.count() == 0:
                    print "Setting up default files for user '%s'"%(user.username,)
                    setupAccount(user)
                else:
                    print "User '%s' already has files."%(user.username,)
        else:
            print "No users found!"
