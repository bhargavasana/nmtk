# Create your views here.
from django.shortcuts import render
from NMTK_server import forms
from NMTK_server import models
from NMTK_server.decorators import authentication
from django.http import HttpResponse, Http404, HttpResponseRedirect, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.contrib.sites.models import get_current_site
import requests
import json
import os.path
import logging
import collections
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
import tempfile
from django.core.servers.basehttp import FileWrapper
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.utils import timezone
from django.conf import settings
import hashlib
import random
from registration import models as registration_models

logger=logging.getLogger(__name__)

def terms_of_service(request):
    template='NMTK_server/terms_of_service.html'
    site=get_current_site(request) 
    terms_of_service=models.PageContent.objects.filter(page__name='terms_of_service')
    if terms_of_service:
        return render(request, template,
                      {'page_data': terms_of_service,
                       'site': site })    
    else:
        raise Http404('Page does not exist!')

def registerUser(request):
    if settings.REGISTRATION_OPEN==False:
        return HttpResponseRedirect(reverse('registration_disallowed'))
        return render(request, 
                      'NMTK_server/registration_closed.html')
    template='NMTK_server/registration_form.html'
    site=get_current_site(request) 
    # Returns 0 if there is no terms of service page content...
    terms_of_service=models.PageContent.objects.filter(page__name='terms_of_service').count()
    if request.method == 'POST':
        userform=forms.NMTKRegistrationForm(request.POST, tos=terms_of_service)
        if userform.is_valid():
            user=userform.save()
            salt=hashlib.sha1(str(random.random())).hexdigest()[:5]
            username=user.username
            if isinstance(user.username, unicode):
                username=username.encode('utf-8')
            activation_key=hashlib.sha1(salt+username).hexdigest()
            profile=registration_models.RegistrationProfile(user=user,
                                                            activation_key=activation_key)
            profile.save()
            profile.send_activation_email(site)
            return render(request, 
                          'NMTK_server/registration_complete.html')
    else:
        
        userform=forms.NMTKRegistrationForm(tos=terms_of_service)
    return render(request, template,
                  {'form': userform,
                   'site': site })    

def nmtk_index(request, page_name='nmtk_index'):
    '''
    The function to display the NMTK Index page.  This is goverened by
    the NMTK_BANNER_OVERRIDE_URL setting - which might cause the 
    splash page to be ignored.
    '''
    override_setting=getattr(settings, 'NMTK_BANNER_OVERRIDE_URL', None)
    if override_setting is None:
        data=models.PageContent.objects.filter(page__name='nmtk_index',
                                               enabled=True)
        
        return render(request, 'NMTK_server/index.html',
                      {'registration_open': settings.REGISTRATION_OPEN,
                       'ui_installed': 'NMTK_ui' in settings.INSTALLED_APPS,
                       'page_data': data})
    elif override_setting == '':
        return nmtk_ui(request)
    else:
        return HttpResponseRedirect(override_setting)

def nmtk_ui(request):
    '''
    It's possible that the NMTK_ui is not enabled, but NMTK_server is
    - in such cases we cannot properly redirect the user from admin pages
    and the link to the UI, so instead we'll just give them the index page
    again - since that's all we can provide in this case.
    
    With this in mind, all the NMTK_server pages that refer to the UI use the
    nmtk_server_nmtk_ui named urlpattern, which is tied to this view, which
    redirects to the UI if it is installed/enabled.
    '''
    if 'NMTK_ui' in settings.INSTALLED_APPS:
        try:
            return HttpResponseRedirect(reverse('nmtk_ui_nmtk_ui'))
        except Exception, e:
            pass
    logger.info('NMTK_ui application is not enabled')
    return nmtk_index(request)


# Methods below are methods that are called by the tool to send results
# back to the server.  As a result, they are not user-facing, and do not
# need things like the login_required decorator.
    
@csrf_exempt
@authentication.requireValidAuthToken
@authentication.requireValidJobId
def updateStatus(request):
    '''
    Update the status of a job in the database.  In this case we 
    expect there to be two keys in the json payload:
     - timestamp - a timestamp as to when the status update was
                   generated by the tool
     - status - a status message (max length 1024 bytes) to use to 
                update the job status.
    '''
    logger.debug('Updating status for job id %s', request.NMTK_JOB.pk)
    data=request.FILES['data'].read()
    logger.debug('Read updated status of %s', data)
    
    status_m=models.JobStatus(message=data,
                              timestamp=timezone.now(),
                              job=request.NMTK_JOB)
    status_m.save()
    return HttpResponse(json.dumps({'status': 'Status added with key of %s' % (status_m.pk)}),
                        content_type='application/json')

@csrf_exempt
@authentication.requireValidAuthToken
@authentication.requireValidJobId
def processResults(request):
    '''
    The idea here is that this URL always posts successful results, though
    in reality it probably ought to be enhanced to accept both success
    results as well as failure results.  We can worry about handling that
    based on content type.
    '''
    config=json.loads(request.FILES['config'].read())

    
    base_description="Results from '{0}'".format(request.NMTK_JOB.description)
    if config['status'] == 'results':
        models.JobStatus(message='Received results from Tool Server',
                         timestamp=timezone.now(),
                         job=request.NMTK_JOB).save()
        if (not config.has_key('results') or 
            not config['results'].has_key('field') or
            not config['results'].has_key('file')):
            logger.error('Results received with no valid results key ' +
                         'in config (old API?) (%s)', config)
            models.JobStatus(message='Unable to authenticate request from tool server.',
                         timestamp=timezone.now(),
                         job=request.NMTK_JOB).save()
            return HttpResponseServerError('Invalid result format')
        result_field=config['results']['field']
        result_field_units=config['results'].get('units', None)

        result_file=config['results']['file']
        
        if config['results']['file'] not in request.FILES:
            logger.error('Specified file for results was not uploaded')
            models.JobStatus(message='Tool server failed to upload required results file.',
                         timestamp=timezone.now(),
                         job=request.NMTK_JOB).save()
            return HttpResponseServerError('Invalid result file specified')
        total=len(request.FILES)-1
        
        i=0
        for namespace in request.FILES.keys():
            i += 1
            if (total > 1):
                description = base_description + '({0}/{1})'.format(i, total)
            else:
                description=base_description
            kwargs={}
            if namespace == 'config':
                continue
            if namespace == result_file:
                primary=True
                field=result_field
            else:
                field=None
                primary=False
            result=models.DataFile(user=request.NMTK_JOB.user,
                                   name="job_{0}_results".format(request.NMTK_JOB.pk),
                                   #name=os.path.basename(request.FILES[result_file].name),
                                   description=description,
                                   content_type=request.FILES[namespace].content_type,
                                   type=models.DataFile.JOB_RESULT, 
                                   result_field=field,
                                   result_field_units=result_field_units)
            filename=os.path.basename(request.FILES[result_file].name)
            result.file.save(filename, ContentFile(request.FILES[result_file].read()), save=False)
            
            if namespace == result_file:
                # Pass in the job here so that the data file processor knows to
                # update the job when this is done (only happens with primary file.)
                result.save(job=request.NMTK_JOB)
            else:
                result.save()
            # Save the linkage back to the job...
            rf=models.ResultsFile(job=request.NMTK_JOB,
                                  datafile=result,
                                  primary=primary)
            rf.save()
            
        request.NMTK_JOB.status=request.NMTK_JOB.POST_PROCESSING
        request.NMTK_JOB.save()
        
        models.JobStatus(message='Post processing results file(s)',
                         timestamp=timezone.now(),
                         job=request.NMTK_JOB).save()
    elif config['status'] == 'error':
        logger.debug('config is %s', config)
        models.JobStatus(message='\n'.join(config['errors']),
                         timestamp=timezone.now(),
                         job=request.NMTK_JOB).save()
        request.NMTK_JOB.status=request.NMTK_JOB.FAILED
        request.NMTK_JOB.save()

   
    return HttpResponse(json.dumps({'status': 'Results saved'}),
                        content_type='application/json')
    
def logout_page(request):
    """
    Log users out and re-direct them to the main page.
    """
    logout(request)
    return HttpResponseRedirect('/')