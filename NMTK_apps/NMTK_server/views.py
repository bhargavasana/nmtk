# Create your views here.
from django.shortcuts import render
from NMTK_server import forms
from NMTK_server import models
from NMTK_server.decorators import authentication
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.contrib.sites.models import get_current_site
import requests
import json
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

def registerUser(request):
    if settings.REGISTRATION_OPEN==False:
        return HttpResponseRedirect(reverse('registration_disallowed'))
        return render(request, 
                      'NMTK_server/registration_closed.html')
    template='NMTK_server/registration_form.html'
    site=get_current_site(request) 
    if request.method == 'POST':
        userform=forms.NMTKRegistrationForm(request.POST)
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
        userform=forms.NMTKRegistrationForm()
    return render(request, template,
                  {'form': userform,
                   'site': site })    

def nmtk_index(request):
    return render(request, 'NMTK_server/index.html',
                  {'registration_open': settings.REGISTRATION_OPEN,
                   'ui_installed': 'NMTK_ui' in settings.INSTALLED_APPS})

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
    data=ContentFile(request.FILES['data'].read())
    description="Results from '{0}'".format(request.NMTK_JOB.description)
    if config['status'] == 'results':
        result=models.DataFile(user=request.NMTK_JOB.user,
                               name="job_%s_results" % (request.NMTK_JOB.pk,),
                               description=description,
                               result_field=config.get('result_field', 'result'),
                               content_type=config.get('content_type', 'application/json'),
                               type=models.DataFile.JOB_RESULT)
        result.file.save('results', data, save=False)
        request.NMTK_JOB.status=request.NMTK_JOB.POST_PROCESSING
        # Pass in the job here so that the data file processor knows to
        # update the job when this is done.
        result.save(job=request.NMTK_JOB)
        request.NMTK_JOB.results=result
    elif config['status'] == 'error':
        request.NMTK_JOB.status=request.NMTK_JOB.FAILED
    # The tool should indicate which field contains its result.
    request.NMTK_JOB.save()
    models.JobStatus(message='COMPLETE',
                     timestamp=timezone.now(),
                     job=request.NMTK_JOB).save()
    return HttpResponse(json.dumps({'status': 'Results saved'}),
                        content_type='application/json')
    
def logout_page(request):
    """
    Log users out and re-direct them to the main page.
    """
    logout(request)
    return HttpResponseRedirect('/')