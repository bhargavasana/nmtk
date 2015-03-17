from django.conf.urls import patterns, include, url
from django.core.urlresolvers import reverse
import registration.backends.default.urls
import django.contrib.auth.urls
from NMTK_server import api
from tastypie.api import Api
# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

v1_api = Api(api_name='v1')
v1_api.register(api.DataFileResource())
v1_api.register(api.UserResource())
v1_api.register(api.ToolResource())
#v1_api.register(api.ToolConfigResource())
v1_api.register(api.JobResource())
v1_api.register(api.JobFileResource())
v1_api.register(api.ResultsFileResource())
v1_api.register(api.JobStatusResource())
v1_api.register(api.FeedbackResource())
v1_api.register(api.UserPreference())
v1_api.register(api.ToolSampleFileResource())
v1_api.register(api.MapColorStyleResource())
v1_api.register(api.PageNameResource())
v1_api.register(api.PageContentResource())
    

urlpatterns = patterns('',
   url('^ui/$', 'NMTK_server.views.nmtk_ui', {}, name='nmtk_server_nmtk_ui'),
   url('^$', 'NMTK_server.views.nmtk_index', {}, name='nmtk_server_nmtk_index'),
   url('^terms_of_service/$', 'NMTK_server.views.terms_of_service', {}, name='terms_of_service'),
   url('^tools/result$', 'NMTK_server.views.processResults', {}, name='processSuccessResults'),
   url('^tools/update$', 'NMTK_server.views.updateStatus', {}, name='updateStatus'),
#   url('^submit-job-to-tool$', 'NMTK_server.views.configureJob', {}, name='configureJob'),
#   url('^refresh-status/(?P<job_id>[^/]*)$', 'NMTK_server.views.refreshStatus', {}, name='refreshStatus'),
#   url('^results/(?P<job_id>[^/]*)$', 'NMTK_server.views.viewResults', {}, name='viewResults'),   
#   url('^download_results/(?P<job_id>[^/]*)$', 'NMTK_server.views.downloadResults', {}, name='downloadResults'),   
#   url('^downloadDataFile/(?P<file_id>[^/]*)$', 'NMTK_server.views.downloadDataFile', {}, name='NMTK_server.download_datafile'),
#   url('^downloadGeoJsonFile/(?P<file_id>[^/]*)$', 'NMTK_server.views.downloadGeoJsonFile', {}, name='NMTK_server.download_geojson_datafile'),
   # Uncomment the admin/doc line below to enable admin documentation:
   # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
   # Uncomment the next line to enable the admin:
#   url(r'^login/$', 'django.contrib.auth.views.login'),
   url(r'^logout/$', 'django.contrib.auth.views.logout',
       {'next_page': '/server/'}, name='auth_logout'), # This needs to match the nmtk_server_nmtk_index URL 
   url(r'^register/$', 'NMTK_server.views.registerUser', {}, name='nmtk_register'),
   url(r'^admin/', include(admin.site.urls)),
   url(r'^api/', include(v1_api.urls)),
   url(r'', include(django.contrib.auth.urls)),
   url(r'', include(registration.backends.default.urls))
)
