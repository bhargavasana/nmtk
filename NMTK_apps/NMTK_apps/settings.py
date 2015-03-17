#!/usr/bin/env python
# Non-Motorized Toolkit
# Copyright (c) 2014 Open Technology Group Inc. (A North Carolina Corporation)
# Developed under Federal Highway Administration (FHWA) Contracts:
# DTFH61-12-P-00147 and DTFH61-14-P-00108
# 
# Redistribution and use in source and binary forms, with or without modification, 
# are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright notice, 
#       this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright 
#       notice, this list of conditions and the following disclaimer 
#       in the documentation and/or other materials provided with the distribution.
#     * Neither the name of the Open Technology Group, the name of the 
#       Federal Highway Administration (FHWA), nor the names of any 
#       other contributors may be used to endorse or promote products 
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL 
# Open Technology Group Inc BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, 
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT 
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF 
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED 
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, 
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT 
# OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# Django settings for NMTK_apps project.
import os
import djcelery
import socket
import warnings 
import platform

BASE_PATH=os.path.dirname(__file__)

# Used to initialize the sites model (see: NMTK_server/management/__init__.py)
# This should be overridden by the VHOST name, but it is defaulted to the FQDN
# since in most cases that will be the same.
# It should be noted that if you use any kind of vhost setup, then this
# probably won't work, and will result in all kinds of broken-ness :-) 


DEBUG = False
TEMPLATE_DEBUG = TASTYPIE_FULL_DEBUG = DEBUG
from local_settings import *
warnings.filterwarnings('ignore',r"'NoneType' object has no attribute 'finishGEOS_r'")
warnings.filterwarnings('ignore',r"'NoneType' object has no attribute 'destroy_geom'")
djcelery.setup_loader()

MANAGERS = ADMINS
ALLOWED_HOSTS=[SITE_DOMAIN,'127.0.0.1']


# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT=os.path.abspath(os.path.join('..', 'htdocs/static'))

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)



# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'NMTK_server.middleware.strict_authentication.StrictAuthentication',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'NMTK_apps.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'NMTK_apps.wsgi.application'
TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.

    # This directory adds the templates that are stored in the NMTK_apps directory,
    # Which is not an app - but the underpinnings for everything else.
    os.path.join(BASE_PATH,'templates'),
)




TEMPLATE_CONTEXT_PROCESSORS=("django.contrib.auth.context_processors.auth",
                             "django.core.context_processors.debug",
                             "django.core.context_processors.i18n",
                             "django.core.context_processors.media",
                             "django.core.context_processors.static",
                             "django.core.context_processors.tz",
                             "django.contrib.messages.context_processors.messages",
                             "django.core.context_processors.request", 
                              )

INSTALLED_APPS = (
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'djcelery',
    'kombu.transport.django',
    )

TASTYPIE_DEFAULT_FORMATS = ['json',]

if TOOL_SERVER:
    INSTALLED_APPS = INSTALLED_APPS + ('NMTK_tools', # An app used to generate a list of tools.
                                       ) + NMTK_TOOL_APPS
if NMTK_SERVER:
    INSTALLED_APPS = INSTALLED_APPS + ('django.contrib.auth',
                                       'registration',
                                       'widget_tweaks',
                                       'NMTK_server', # The NMTK Server
                                       'django.contrib.admin',
                                       'NMTK_ui', # the UI components for NMTK server
                                       'tastypie',
                                       )

# The test tool only gets installed if debug is set to true.
# if not PRODUCTION and TOOL_SERVER:
#     INSTALLED_APPS=INSTALLED_APPS + (
#                                      'test_tool', # A sample tool designed for testing new stuff.
#                                      )


# Define a GeoJSON serializer so we can serialize and return results of
# various tasks in the GeoJSON format.
SERIALIZATION_MODULES = { 'geojson' : 'NMTK_apps.serializers.geojson' }


# The URL Used for logins
LOGIN_URL='/server/login/'

# if you want to change the logging (to disable debug) do it here..
if DEBUG:
    MIN_LOG_LEVEL='DEBUG' # 'INFO' for non-debug, 'DEBUG' for debugging
else:
    MIN_LOG_LEVEL='INFO'
# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
    
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'null': {
            'level':'DEBUG',
            'class':'django.utils.log.NullHandler',
        },
        'debug': {
            'level':'DEBUG',
            'class':'logging.handlers.WatchedFileHandler',
            'filename': os.path.join(LOGFILE_PATH,'django-debug.log'),
            'formatter':'standard',
        },  
        'default': {
            'level':'INFO',
            'class':'logging.handlers.WatchedFileHandler',
            'filename': os.path.join(LOGFILE_PATH,'django-request.log'),
            'formatter':'standard',
        },
        'apache': {
            'level':'INFO',
            'class':'logging.StreamHandler',
            'formatter':'standard',
        },
    },
    'loggers': {    
        '': {
            'handlers': ['debug', 'default'],
            'level': MIN_LOG_LEVEL,
            'propagate': True,
        },
        'django.request': { # Stop request debug from logging to main logger
            'handlers': ['apache'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db': { # We can turn on db logging by switching the handler to debug
            'handlers': ['null'],
            'level': MIN_LOG_LEVEL,
            'propagate': False,
        },
    }
}


BROKER_URL = 'django://'

# Make our session keys stay for 14 days since the last access.
# because the default SESSION_COOKIE_AGE is 1209600 (60*60*24*14)=14 days in seconds
SESSION_SAVE_EVERY_REQUEST=True


# A list of modules used by the data loader, note that order is important here
# Since the first loader that recognizes a file will process it.
DATA_LOADERS=['NMTK_server.data_loaders.ogr.OGRLoader',
              'NMTK_server.data_loaders.csv.CSVLoader']
