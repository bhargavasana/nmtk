from NMTK_server.resources import ModelResource, ALL, ALL_WITH_RELATIONS
from NMTK_server import models
from django.conf.urls import patterns, include, url
from tastypie.exceptions import Unauthorized
from tastypie.authentication import SessionAuthentication
from tastypie.http import HttpForbidden, HttpUnauthorized
from tastypie import fields, utils
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout
from django.core.urlresolvers import reverse
from tastypie.authorization import Authorization
from django.forms.models import model_to_dict
from tastypie.utils import trailing_slash
from django.core.servers.basehttp import FileWrapper
from django.core.exceptions import ObjectDoesNotExist
from tastypie.resources import csrf_exempt
from django.http import HttpResponse, Http404
from NMTK_server import forms
from NMTK_apps.helpers import data_output
from NMTK_server.wms import wms_service
from validation.tool_config_validator import ToolConfigValidator
import simplejson as json
from tastypie.validation import Validation
from PIL import Image
import cStringIO as StringIO
import logging
import re
import os
logger=logging.getLogger(__name__)

User=get_user_model()

class CSRFBypassSessionAuthentication(SessionAuthentication):
    def is_authenticated(self, request, **kwargs):
        request._dont_enforce_csrf_checks=True
        return super(CSRFBypassSessionAuthentication, self).is_authenticated(request, **kwargs)
 

class UserResourceValidation(Validation):
    def is_valid(self, bundle, request=None):
        errors = {}
        if bundle.request.method == 'POST':
            if not bundle.data:
                return {'__all__': 'Invalid Data'}
            if bundle.data.has_key('username'):
                count=models.User.objects.filter(username=bundle.data['username']).count()
            if count > 0:
                errors['username']='Sorry, that username is not available'
        if bundle.request.method in ('PUT','PATCH'):
            if (bundle.data.has_key('password') and not bundle.request.user.is_superuser):
                if not bundle.data.has_key('current_password'):
                    errors['__all__']='current_password must be supplied when changing password'
                elif not bundle.request.user.check_password(bundle.data['current_password']):
                    errors['__all__']='Old password supplied is invalid'                
        return errors

class UserResourceAuthorization(Authorization):
    def read_list(self, object_list, bundle):
        '''
        This gets a queryset (object_list) and returns a new one.  The key
        here is that we are apply *additional* filters to the default 
        queryset to restrict the output back to the user.
        
        In this case, we check to see if the user is a site admin, if they are
        then they are able to see *all* the records for active users.
        
        If they are *not* a site admin, we restrict viewing of data to the
        username that matches the current logged in user.  In short, you 
        can see your information, but noone elses.
        '''
        if ((bundle.request.user.is_superuser or bundle.request.user.is_staff) 
            and bundle.request.GET.get('all', False)):
            return object_list
        return object_list.filter(pk=bundle.request.user.pk)

    def read_detail(self, object_list, bundle):
        '''
        This should get a list (containing a single record).  It should
        either return an error indicating the record is not accessible by
        the user, or it should simply return.
        
        In this case, raising NotFound seems to be the only option that 
        causes the server to continue to function without an exception.  Other
        things (like not authorized) cause a 500
        '''
        if bundle.request.user.is_superuser or bundle.request.user.is_staff:
            return True
        elif bundle.obj.pk <> bundle.request.user.pk:
            raise Unauthorized('You lack the privilege to access this resource')
        return True

    def create_list(self, object_list, bundle):
        '''
        This method should, when given a list of objects, return a new list
        of objects representing the objects that are to be created.  In the case
        of this model, only superusers can create new users, so we simply return
        the empty list when they try to add objects.
        '''
        if bundle.request.user.is_superuser:
            return object_list
        raise Unauthorized('You lack the privilege to create this resource')

    def create_detail(self, object_list, bundle):
        '''
        Each record being created is passed through this method, which is
        used to determine if the object can be created - an exception means
        that it cannot, a True (or anything else for that matter) means that it
        can be created.  In our case, we only allow this record to be created
        when the user is an admin user.
        '''
        if not bundle.request.user.is_superuser:
            raise Unauthorized('You lack the privilege to create this resource')
        return True

    def update_list(self, object_list, bundle):
        '''
        A list of objects to be updated.  In the case of a superuser, we let
        them do what they want.  In the case of any other user, they can only
        modify their user record - noone elses.  Elsewhere we will limit what 
        they can modify about this record - and limit them to only changing
        their password.
        '''
        # Superusers can do what they want.
        if bundle.request.user.is_superuser:
            return object_list
        raise Unauthorized('You lack the privilege to update resources this way')
    

    def update_detail(self, object_list, bundle):
        '''
        In this case, we simply force updates to the model to occur
        '''
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.pk == bundle.request.user.pk:
            if bundle.data.has_key('password'):
                return True
            else:
                raise Unauthorized('You may only change your own password')
        
        raise Unauthorized('You lack the privilege to access this resource')

    def delete_list(self, object_list, bundle):
        # Sorry user, no deletes for you

        if bundle.request.user.is_superuser:
            return object_list
        raise Unauthorized("This resource does not allow deletes.")

    def delete_detail(self, object_list, bundle):
        if bundle.request.user.is_superuser:
            return True
        raise Unauthorized('You lack the privilege to access this resource')

class UserResource(ModelResource):
    date_joined=fields.DateTimeField('date_joined',readonly=True)
    last_login=fields.DateTimeField('last_login',readonly=True)
    class Meta:
        queryset=User.objects.filter(is_active=True)
        results_name='user'
        always_return_data = True
        authentication=SessionAuthentication()
        authorization=UserResourceAuthorization()
        validation=UserResourceValidation()
        excludes=('password','groups',)
        filtering= {'username': ALL,
                    'email': ALL}
        
    def pre_save(self,bundle):
        bundle=super(UserResource,self).pre_save(bundle)
        if bundle.data.has_key('password'):
            bundle.obj.set_password(bundle.data['password'])
        return bundle
    
    def dehydrate(self, bundle):
        bundle.data['logout']=reverse("api_%s_logout" % (self._meta.resource_name,),
                                      kwargs={'resource_name': self._meta.resource_name,
                                              'pk': bundle.obj.pk,
                                              'api_name': 'v1'})
        return bundle
        
    
    def override_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/login%s$" % (self._meta.resource_name, 
                                                                     trailing_slash()), 
                                                                     self.wrap_view('login'), 
                                                                     name="api_%s_login" % (self._meta.resource_name,)),
            url(r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/logout%s$" % (self._meta.resource_name, 
                                                                     trailing_slash()), 
                                                                     self.wrap_view('logout'), 
                                                                     name="api_%s_logout" % (self._meta.resource_name,)),
        ]
    
    def logout(self, request, **kwargs):
        self.method_check(request, allowed=['get'])
        logout(request)
        return self.create_response(request, {'success': True})
    
    def login(self, request, **kwargs):
        logger.debug('In the login view')
        self.method_check(request, allowed=['post'])
        data = self.deserialize(request, 
                                request.raw_post_data, 
                                format=request.META.get('CONTENT_TYPE', 
                                                        'application/json'))

        username = data.get('username', '')
        password = data.get('password', '')
        logger.debug('In the login view')
        user = authenticate(username=username, password=password)
        if user:
            if user.is_active:
                login(request, user)
                uri=reverse("api_dispatch_detail",
                            kwargs={'resource_name': self._meta.resource_name,
                                    'pk':user.pk,
                                    'api_name': 'v1'})
                return self.create_response(request, {
                    'success': True,
                    'resource_uri' : uri,
                })
            else:
                return self.create_response(request, {
                    'success': False,
                    'reason': 'Account is disabled',
                    }, HttpForbidden )
        else:
            return self.create_response(request, {
                'success': False,
                'reason': 'Invalid username/password combination',
                }, HttpUnauthorized )
    
    def obj_delete_list(self, bundle, **kwargs):
        """
        Translate a delete via the API to a "set inactive"
        """
        objects_to_delete = self.obj_get_list(bundle=bundle, **kwargs)
        deletable_objects = self.authorized_delete_list(objects_to_delete, bundle)

        for authed_obj in deletable_objects:
            authed_obj.is_active=False
            authed_obj.set_unusable_password()
            authed_obj.save()

    def obj_delete_list_for_update(self, bundle, **kwargs):
        """
        Translate a delete via the API to a "set inactive"
        """
        objects_to_delete = self.obj_get_list(bundle=bundle, **kwargs)
        deletable_objects = self.authorized_update_list(objects_to_delete, bundle)

        for authed_obj in deletable_objects:
            authed_obj.is_active=False
            authed_obj.set_unusable_password()
            authed_obj.save()
            
    def obj_delete(self, bundle, **kwargs):
        """
        Translate a delete via the API to a "set inactive"
        """
        if not hasattr(bundle.obj, 'delete'):
            try:
                bundle.obj = self.obj_get(bundle=bundle, **kwargs)
            except ObjectDoesNotExist:
                raise NotFound("A model instance matching the provided arguments could not be found.")

        self.authorized_delete_detail(self.get_object_list(bundle.request), bundle)
        bundle.obj.is_active=False
        bundle.obj.set_unusable_password()
        bundle.obj.save()

    def hydrate(self, bundle):
        if not bundle.request.user.is_superuser:
#             logger.debug(model_to_dict(bundle.obj))
            if bundle.obj.pk:
                data=model_to_dict(bundle.obj)
                del data['password']
                bundle.data.update(data)

        return super(UserResource, self).hydrate(bundle)


class FeedbackResourceAuthorization(Authorization):
    def read_list(self, object_list, bundle):
        '''
        This gets a queryset (object_list) and returns a new one.  The key
        here is that we are apply *additional* filters to the default 
        queryset to restrict the output back to the user.
        
        In this case, we check to see if the user is a site admin, if they are
        then they are able to see *all* the records for active users.
        
        If they are *not* a site admin, we restrict viewing of data to the
        username that matches the current logged in user.  In short, you 
        can see your information, but noone elses.
        '''
        if bundle.request.user.is_staff or  bundle.request.user.is_superuser:
            return object_list
        else:
            return [row for row in object_list if row.user == bundle.request.user]

    def read_detail(self, object_list, bundle):
        '''
        This should get a list (containing a single record).  It should
        either return an error indicating the record is not accessible by
        the user, or it should simply return.
        
        In this case, raising NotFound seems to be the only option that 
        causes the server to continue to function without an exception.  Other
        things (like not authorized) cause a 500
        '''
        if bundle.obj.user <> bundle.request.user:
            raise Unauthorized('You lack the privilege to access this resource')
        return True

    def create_list(self, object_list, bundle):
        '''
        This method should, when given a list of objects, return a new list
        of objects representing the objects that are to be created.  In the case
        of this model, only superusers can create new users, so we simply return
        the empty list when they try to add objects.
        '''
        raise Unauthorized('You lack the privilege to create this resource')

    def create_detail(self, object_list, bundle):
        '''
        Each record being created is passed through this method, which is
        used to determine if the object can be created - an exception means
        that it cannot, a True (or anything else for that matter) means that it
        can be created.  In our case, we only allow this record to be created
        when the user is an admin user.
        '''
        return True
    
class FeedbackResource(ModelResource):
    user=fields.ToOneField(UserResource,'user')
    class Meta:
        queryset = models.Feedback.objects.all()
        authorization=FeedbackResourceAuthorization()
        always_return_data = True
        resource_name = 'feedback'
        allowed_methods=['get','post']
        authentication=SessionAuthentication()
        validation=Validation()
        filtering= {'uri': ALL}
        
    def pre_save(self, bundle):
        bundle.obj.user=bundle.request.user
        return bundle 
    
    def get_object_list(self, request):
        '''
        Ensure a user only sees their own feedback. Note that passing "all=True"
        allows a superuser/staff member to view all feedback via the API.  The check
        for permission is in the FeedbackResourceAuthorization object.
        '''
        if request.GET.get('all', False):
            return super(FeedbackResource, self).get_object_list(request)
        else:
            return super(FeedbackResource, self).get_object_list(request).filter(user=request.user)

class UserPreferenceAuthorization(Authorization):
    def read_list(self, object_list, bundle):
        '''
        This gets a queryset (object_list) and returns a new one.  The key
        here is that we are apply *additional* filters to the default 
        queryset to restrict the output back to the user.
        
        In this case, we check to see if the user is a site admin, if they are
        then they are able to see *all* the records for active users.
        
        If they are *not* a site admin, we restrict viewing of data to the
        username that matches the current logged in user.  In short, you 
        can see your information, but noone elses.
        '''
        return object_list
    
    def read_detail(self, object_list, bundle):
        '''
        This should get a list (containing a single record).  It should
        either return an error indicating the record is not accessible by
        the user, or it should simply return.
        
        In this case, raising NotFound seems to be the only option that 
        causes the server to continue to function without an exception.  Other
        things (like not authorized) cause a 500
        '''
        if bundle.obj.user <> bundle.request.user:
            raise Unauthorized('You lack the privilege to access this resource')
        return True
    
    def update_detail(self, object_list, bundle):
        if bundle.obj.user <> bundle.request.user:
            raise Unauthorized('You lack the privilege to access this resource')
        return True

    def create_list(self, object_list, bundle):
        '''
        This method should, when given a list of objects, return a new list
        of objects representing the objects that are to be created.  In the case
        of this model, only superusers can create new users, so we simply return
        the empty list when they try to add objects.
        '''
        raise Unauthorized('You lack the privilege to create this resource')

    create_detail=create_list
 
    
class UserPreference(ModelResource):
    class Meta:
        queryset = models.UserPreference.objects.all()
        authorization=UserPreferenceAuthorization()
        always_return_data = True
        resource_name = 'preference'
        allowed_methods=['get','put']
        excludes=['user']
        authentication=SessionAuthentication()
        validation=Validation()
        
    def get_object_list(self, request):
        '''
        Ensure a user only sees their own feedback.
        '''
        return super(UserPreference, self).get_object_list(request).filter(user=request.user)

class DataFileResourceAuthorization(Authorization):
    def read_list(self, object_list, bundle):
        '''
        This gets a queryset (object_list) and returns a new one.  The key
        here is that we are apply *additional* filters to the default 
        queryset to restrict the output back to the user.
        
        In this case, we check to see if the user is a site admin, if they are
        then they are able to see *all* the records for active users.
        
        If they are *not* a site admin, we restrict viewing of data to the
        username that matches the current logged in user.  In short, you 
        can see your information, but noone elses.
        '''
        return object_list.filter(user=bundle.request.user.pk)

    def read_detail(self, object_list, bundle):
        '''
        This should get a list (containing a single record).  It should
        either return an error indicating the record is not accessible by
        the user, or it should simply return.
        
        In this case, raising NotFound seems to be the only option that 
        causes the server to continue to function without an exception.  Other
        things (like not authorized) cause a 500
        '''
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.user.pk <> bundle.request.user.pk:
            raise Unauthorized('You lack the privilege to access this resource')
        return True

    def create_list(self, object_list, bundle):
        '''
        This method should, when given a list of objects, return a new list
        of objects representing the objects that are to be created.  In the case
        of this model, only superusers can create new users, so we simply return
        the empty list when they try to add objects.
        '''
        logger.debug('Creating a new object')
        return object_list        

    def create_detail(self, object_list, bundle):
        '''
        Each record being created is passed through this method, which is
        used to determine if the object can be created - an exception means
        that it cannot, a True (or anything else for that matter) means that it
        can be created.  In our case, we only allow this record to be created
        when the user is an admin user.
        '''
        logger.debug('in create_detail')
        return True

    def update_list(self, object_list, bundle):
        '''
        A list of objects to be updated.  In the case of a superuser, we let
        them do what they want.  In the case of any other user, they can only
        modify their user record - noone elses.  Elsewhere we will limit what 
        they can modify about this record - and limit them to only changing
        their password.
        '''
        # Superusers can do what they want.
        if bundle.request.user.is_superuser:
            return object_list
        else:
            return [obj for obj in object_list 
                    if obj.user == bundle.request.user]    

    def update_detail(self, object_list, bundle):
        '''
        In this case, we simply force updates to the model to occur
        '''
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.pk == bundle.request.user.pk:
            return True
        
        raise Unauthorized('You lack the privilege to access this resource')

    def delete_list(self, object_list, bundle):
        # Sorry user, no deletes for you
        if bundle.request.user.is_superuser:
            return object_list
        else:
            return [obj for obj in object_list 
                    if obj.user == bundle.request.user] 

    def delete_detail(self, object_list, bundle):
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.user == bundle.request.user:
            return True
        raise Unauthorized('You lack the privilege to access this resource')

class DataFileResourceValidation(Validation):
    def is_valid(self, bundle, request=None):
        errors = {}
        if (not bundle.obj.pk and 
            not bundle.request.FILES.has_key('file')):
            errors['file']='A file must be provided when creating this resource'
        if (bundle.obj.pk and bundle.data.get('srid', False) and
            bundle.data['srid'] != bundle.obj.srid and
            bundle.obj.status not in 
            (bundle.obj.IMPORT_FAILED,bundle.obj.PENDING)):
            errors['srid']='SRID can only be provided initially, ' + \
                           'or after a failed import'
        if bundle.obj.status == bundle.obj.IMPORT_FAILED:
            logger.debug('Got a failed job! (%s), srid: %s; %s', bundle.obj.pk,
                         bundle.data.get('srid', False),
                         bundle.obj._old_srid
                         )
            if (bundle.data.get('srid', False) and 
                bundle.data['srid'] != bundle.obj._old_srid):
                logger.debug('Attempting to change SRID!')
                bundle.data['status']=bundle.obj.PENDING
                bundle.obj.status=bundle.obj.PENDING
        return errors

class DataFileResource(ModelResource):
    id=fields.IntegerField('id', readonly=True)
    status_message=fields.CharField('status_message', readonly=True,
                                    null=True)
    feature_count=fields.IntegerField('feature_count', readonly=True,
                                      null=True)
    content_type=fields.CharField('content_type', readonly=True,
                                  null=True)
    date_created=fields.DateTimeField('date_created', readonly=True,
                                      null=True)
    extent=fields.CharField('extent', readonly=True, null=True)
    srs=fields.CharField('srs', readonly=True, null=True)
    status=fields.CharField('status', readonly=True, null=True)
    checksum=fields.CharField('checksum',readonly=True, null=True)
    geom_type=fields.CharField('geom_type', readonly=True, null=True)
    file=fields.CharField('file', readonly=True, null=True)
    
    field_attributes=fields.CharField('field_attributes', readonly=True, null=True)
    result_field=fields.CharField('result_field', readonly=True, null=True)
    result_field_units=fields.CharField('result_field_units', readonly=True, null=True)
    type=fields.CharField('type', readonly=True, null=True)
#     job=fields.ToOneField('NMTK_server.api.JobResource','job_result',
#                            readonly=True, null=True)
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/download%s$" % (self._meta.resource_name, 
                                                                           trailing_slash()), 
                                                                           self.wrap_view('download_detail_file'), 
                name="api_%s_download_detail_file" % (self._meta.resource_name,)),
            url(r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/results%s$" % (self._meta.resource_name, 
                                                                           trailing_slash()), 
                                                                           self.wrap_view('download_detail'), 
                name="api_%s_download_detail" % (self._meta.resource_name,)),
            url(r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/wms%s$" % (self._meta.resource_name, 
                                                                           trailing_slash()), 
                                                                           self.wrap_view('wms'), 
                name="api_%s_wms" % (self._meta.resource_name,)),
#             url(r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/legend%s$" % (self._meta.resource_name, 
#                                                                          trailing_slash()), 
#                                                                          self.wrap_view('legend'), 
#                 name="api_%s_legend" % (self._meta.resource_name,)),
            ]
 
#     def legend(self, request, **kwargs):
#         rec=None
#         try:
#             if request.user.is_superuser:
#                 rec = self._meta.queryset.get(pk=kwargs['pk'])
#             elif request.user.is_authenticated():
#                 rec = self._meta.queryset.get(pk=kwargs['pk'],
#                                               user=request.user)
#         except ObjectDoesNotExist:
#             raise Http404
#         if rec and rec.geom_type:
#             response = HttpResponse(rec.legendgraphic, content_type='image/png')
#             return response
#         else:
#             raise Http404
        
    def wms(self, request, **kwargs):
        '''
        Act like a WMS by passing the request into mapserver using the 
        provided data set.
        '''
        rec=None
        try:
            if request.user.is_superuser:
                rec = self._meta.queryset.get(pk=kwargs['pk'])
            elif request.user.is_authenticated():
                rec = self._meta.queryset.get(pk=kwargs['pk'],
                                              user=request.user)
        except ObjectDoesNotExist:
            raise Http404
        if rec and rec.geom_type:
            return wms_service.handleWMSRequest(request, rec)
        else:
            raise Http404

    def download_detail(self, request, **kwargs):
        """
        Send a file through TastyPie without loading the whole file into
        memory at once. The FileWrapper will turn the file object into an
        iterator for chunks of 8KB.

        No need to build a bundle here only to return a file, lets look into the DB directly
        """
        format=request.GET.get('format', 'json')
        allow_download=False
        logger.debug('In download_detail with %s', kwargs)
        rec=None
        try:
            if request.user.is_superuser:
                rec = self._meta.queryset.get(pk=kwargs['pk'])
            elif request.user.is_authenticated():
                rec = self._meta.queryset.get(pk=kwargs['pk'],
                                              user=request.user)
        except ObjectDoesNotExist:
            raise Http404
        allow_download=True
        if allow_download:
            if format == 'json': 
                wrapper = FileWrapper(open(rec.processed_file.path,'rb'))
                response = HttpResponse(wrapper, content_type='application/json') #or whatever type you want there
                response['Content-Length'] = rec.processed_file.size
                response['Content-Disposition'] = 'attachment; ' + \
                                                  'filename="data.json"'
                return response
            elif format in ('csv','xls'):
                if format == 'csv':
                    return data_output.stream_csv(rec)
                elif format == 'xls':
                    logger.debug('About to call xls output!')
                    return data_output.stream_xls(rec)
            elif format == 'pager':
                return data_output.pager_output(request, rec)
            elif format == 'query':
                # requires lat, lon, zoom and (optionally) pixels GET parameters
                return data_output.data_query(request, rec)
                
            else:
                return HttpResponse('The format %s is not supported' % (format,))
        else:
            raise Unauthorized('You lack the privileges required to download this file')

    def download_detail_file(self, request, **kwargs):
        """
        Send a file through TastyPie without loading the whole file into
        memory at once. The FileWrapper will turn the file object into an
        iterator for chunks of 8KB.

        No need to build a bundle here only to return a file, lets look into the DB directly
        """
        rec=None
        try:
            if request.user.is_superuser:
                rec = self._meta.queryset.get(pk=kwargs['pk'])
            elif request.user.is_authenticated():
                rec = self._meta.queryset.get(pk=kwargs['pk'],
                                              user=request.user)
        except ObjectDoesNotExist:
            raise Http404
        if rec and not rec.file:
            # if there are results, then they can download them
            raise Http404
            
        
        wrapper = FileWrapper(open(rec.file.path,'rb'))
        response = HttpResponse(wrapper, content_type=rec.content_type) #or whatever type you want there
        response['Content-Length'] = rec.file.size
        response['Content-Disposition'] = ('attachment; filename="%s"' % 
                                           (os.path.basename(rec.file.name)))
        return response        
    

    class Meta:
        queryset = models.DataFile.objects.filter(deleted=False)
        authorization=DataFileResourceAuthorization()
        always_return_data = True
        resource_name = 'datafile'
        allowed_methods=['get','post','delete','put',]
        excludes=['file','processed_file','status', 'geom_type','fields',
                  'deleted', 'model',
                  'type',]
        authentication=CSRFBypassSessionAuthentication()
        validation=DataFileResourceValidation()
        filtering= {'status': ALL,
                    'user': ALL,
                    'type': ALL,
                    'checksum': ('exact',)}

    def pre_save(self, bundle):
        '''
        Ensure that we properly store the user information when the object
        is created, and allow for the optional SRID parameter, but only when
        the import is PENDING (new) or has failed in the past.
        '''
        bundle.obj.user=bundle.request.user
        if bundle.request.FILES.has_key('file'):
            bundle.obj.file=bundle.request.FILES['file']
            bundle.obj.type=bundle.obj.JOB_INPUT
            if not bundle.obj.content_type:
                bundle.obj.content_type=bundle.request.FILES['file'].content_type
        if bundle.data.get('srid', False) and not bundle.obj.srid:
            logging.debug('SRID provided for import, storing')
            bundle.obj.srid=bundle.data['srid']
            bundle.obj.status=bundle.obj.PENDING
        if not bundle.obj.name:
            bundle.obj.name=os.path.basename(bundle.obj.file.name)
            
        return bundle
    
    def alter_list_data_to_serialize(self, request, data):
        '''
        Loop over the list of objects and count how many are currently pending,
        this is then used to update the importing count for the UI, so it knows
        how often to update itself (in milliseconds.)
        '''
        count=0
        for item in data['objects']:
            if item.obj.status in (item.obj.PENDING, item.obj.PROCESSING):
                count += 1
        if count:
            data['meta']['refresh_interval']=3000
        else:
            data['meta']['refresh_interval']=60000
        return data
    
    def dehydrate(self,bundle):
        '''
        Provide data for some fields that we return back to the user, making 
        things a bit more usable than the default TastyPie implementation allows.
        Note: These are all read-only fields, so we don't need to worry about  
        them during the hydrate cycle...
        '''
        if bundle.obj.file:
            bundle.data['file']=reverse("api_%s_download_detail_file" % 
                                        (self._meta.resource_name,),
                                        kwargs={'resource_name': self._meta.resource_name,
                                                'pk': bundle.obj.pk,
                                                'api_name': 'v1'})
        if bundle.obj.processed_file:
            bundle.data['download_url']=reverse("api_%s_download_detail" % 
                                                (self._meta.resource_name,),
                                                kwargs={'resource_name': self._meta.resource_name,
                                                        'pk': bundle.obj.pk,
                                                        'api_name': 'v1'})
                
        if bundle.obj.geom_type:
            bundle.data['wms_url']="%swms/" % (bundle.data['resource_uri'],)
            bundle.data['layer']='results'
#             bundle.data['legend']="{0}legend/".format(bundle.data['resource_uri'])
            bundle.data['geom_type']=bundle.obj.get_geom_type_display()
            
        bundle.data['status']=bundle.obj.get_status_display()
        
        bundle.data['user'] = bundle.obj.user.username
        bundle.data['fields']=json.dumps(bundle.obj.fields)
        bundle.data['field_attributes']=json.dumps(bundle.obj.field_attributes)
        if bundle.data['extent']:
            bundle.data['bbox']=bundle.obj.bbox
            
        return bundle

class ToolResource(ModelResource):
    last_modified=fields.DateTimeField('last_modified', readonly=True,
                                       null=True)
    tool_server=fields.CharField('tool_server',readonly=True,
                                 null=True)
    config=fields.CharField(readonly=True, null=True,
                            help_text='Tool Configuration (as JSON)')
    
    class Meta:
        queryset = models.Tool.objects.filter(active=True)
        resource_name = 'tool'
        always_return_data = True
        fields=['name', 'last_modified']
        allowed_methods=['get',]
        
    def dehydrate(self, bundle):
        bundle.data['id']=bundle.obj.pk
        if bundle.obj.toolconfig:
            bundle.data['config']=bundle.obj.toolconfig.json_config
        return bundle
    
class MapColorStyleResource(ModelResource):
    class Meta:
        queryset = models.MapColorStyle.objects.all()
        resource_name = 'color_style'
        always_return_data = True
        fields=['id','default','description', 'category', 'name']
        allowed_methods=['get',]
        
    def dehydrate(self,bundle):
        '''
        Provide data for some fields that we return back to the user, making 
        things a bit more usable than the default TastyPie implementation allows.
        Note: These are all read-only fields, so we don't need to worry about  
        them during the hydrate cycle...
        '''
        if bundle.obj.ramp_graphic:
            bundle.data['ramp_graphic']=reverse("api_%s_download_ramp_graphic" % 
                                                (self._meta.resource_name,),
                                                kwargs={'resource_name': self._meta.resource_name,
                                                        'pk': bundle.obj.pk,
                                                        'api_name': 'v1'})
        return bundle
            
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/ramp_graphic.png$" % (self._meta.resource_name,), 
                self.wrap_view('download_ramp_graphic'), 
                name="api_%s_download_ramp_graphic" % (self._meta.resource_name,)),
            ]


    def download_ramp_graphic(self, request, **kwargs):
        """
        Send a file through TastyPie without loading the whole file into
        memory at once. The FileWrapper will turn the file object into an
        iterator for chunks of 8KB.
        """
        rec=None
        try:
            rec = self._meta.queryset.get(pk=kwargs['pk'])
        except ObjectDoesNotExist:
            raise Http404
        if rec and not rec.ramp_graphic:
            # if there is no graphic, they are out of luck...
            raise Http404
        reverse_graphic=False
        for k, v in  request.GET.iteritems():
            if k.lower() == 'reverse':
                if v.lower() in ('t','true','1'):
                    reverse_graphic=True
                break
            
        image_file=None
        if reverse_graphic:
            im=Image.open(rec.ramp_graphic.path)
            im=im.rotate(180)
            image_file=StringIO.StringIO()
            im.save(image_file, format='png')
            image_file.seek(0)
            
        wrapper = FileWrapper(image_file or open(rec.ramp_graphic.path,'rb'))
        response = HttpResponse(wrapper, content_type='image/png') #or whatever type you want there
        if not image_file:
            response['Content-Length'] = rec.ramp_graphic.size
#         response['Content-Disposition'] = ('attachment; filename="%s"' % 
#                                            (os.path.basename(rec.ramp_graphic.name)))
        return response

         
class ToolSampleFileResource(ModelResource):
    tool=fields.ToOneField(ToolResource,'tool')
    class Meta:
        queryset = models.ToolSampleFile.objects.filter(tool__active=True)
        resource_name = 'tool_sample_file'
        always_return_data = True
        fields=['namespace','checksum','content_type']
        allowed_methods=['get',]
        filtering= {'tool': ('exact',),
                    'checksum': ('exact',),
                    }
        
    def dehydrate(self, bundle):
        bundle.data['id']=bundle.obj.pk
        if bundle.request.user.is_authenticated():
            bundle.data['load_sample_data']=reverse("api_%s_load_sample_data" % 
                                            (self._meta.resource_name,),
                                            kwargs={'resource_name': self._meta.resource_name,
                                                    'pk': bundle.obj.pk,
                                                    'api_name': 'v1'})
        return bundle
    
    def load_sample_data(self, request, **kwargs):
        if request.user.is_authenticated():
            rec = self._meta.queryset.get(pk=kwargs['pk'])
            if models.DataFile.objects.filter(checksum=rec.checksum,
                                              user=request.user).count():
                '''
                Just return OK if the data file is already loaded - no need to
                load it again.
                '''
                return HttpResponse('COMPLETE')
            else:
                fn=os.path.basename(rec.file.name)
                df=models.DataFile(user=request.user,
                                   description='Sample data for {0}'.format(rec.tool.name),
                                   name=fn,
                                   content_type=rec.content_type)
                df.file.save(fn, rec.file)
                return HttpResponse('PENDING')
        else:
            raise Http404
    
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/load%s$" % (self._meta.resource_name, 
                                                                           trailing_slash()), 
                                                                           self.wrap_view('load_sample_data'), 
                name="api_%s_load_sample_data" % (self._meta.resource_name,)),
            ]


class JobResourceAuthorization(Authorization):
    def read_list(self, object_list, bundle):
        '''
        This gets a queryset (object_list) and returns a new one.  The key
        here is that we are apply *additional* filters to the default 
        queryset to restrict the output back to the user.
        
        In this case, we check to see if the user is a site admin, if they are
        then they are able to see *all* the records for active users.
        
        If they are *not* a site admin, we restrict viewing of data to the
        username that matches the current logged in user.  In short, you 
        can see your information, but noone elses.
        '''
        if bundle.request.user.is_superuser and bundle.data.get('all', False):
            return object_list
        return object_list.filter(user=bundle.request.user.pk)

    def read_detail(self, object_list, bundle):
        '''
        This should get a list (containing a single record).  It should
        either return an error indicating the record is not accessible by
        the user, or it should simply return.
        
        In this case, raising NotFound seems to be the only option that 
        causes the server to continue to function without an exception.  Other
        things (like not authorized) cause a 500
        '''
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.user.pk <> bundle.request.user.pk:
            raise Unauthorized('You lack the privilege to access this resource')
        return True
    
    def create_list(self, object_list, bundle):
        '''
        This method should, when given a list of objects, return a new list
        of objects representing the objects that are to be created.  In the case
        of this model, only superusers can create new users, so we simply return
        the empty list when they try to add objects.
        '''
        return object_list        

    def create_detail(self, object_list, bundle):
        '''
        Each record being created is passed through this method, which is
        used to determine if the object can be created - an exception means
        that it cannot, a True (or anything else for that matter) means that it
        can be created.  Any user can create jobs, since they are tied to the
        user account automatically.
        '''
        return True

    def update_list(self, object_list, bundle):
        '''
        A list of objects to be updated.  In the case of a superuser, we let
        them do what they want.  In the case of any other user, they can only
        modify their user record - noone elses.  Elsewhere we will limit what 
        they can modify about this record - and limit them to only changing
        their password.
        '''
        # Superusers can do what they want.
        if bundle.request.user.is_superuser:
            return object_list
        else:
            return [obj for obj in object_list 
                    if obj.user == bundle.request.user]    

    def update_detail(self, object_list, bundle):
        '''
        In this case, we simply force updates to the model to occur
        '''
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.user == bundle.request.user:
            return True
        
        raise Unauthorized('You lack the privilege to access this resource')

    def delete_list(self, object_list, bundle):
        # Sorry user, no deletes for you
        if bundle.request.user.is_superuser:
            return object_list
        else:
            return [obj for obj in object_list 
                    if obj.user == bundle.request.user] 

    def delete_detail(self, object_list, bundle):
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.user == bundle.request.user:
            return True
        raise Unauthorized('You lack the privilege to access this resource')
        
class JobResourceValidation(Validation):
    def is_valid(self, bundle, request=None):
        '''
        Once we have a job there are a few rules, you cannot change the
        tool or the file once the job is created, since doing so would
        end up possibly invalidating the configuration.  You cannot change the
        status, since it advances on it's own, and changing things once the 
        status has moved to active (for example) wouldn't make sense, so once it
        is active, we'll prevent changes.
        the validation will update the status to active once you send over
        a configuration that seems valid.  Then it's up to the tool to do the
        rest of the work in terms of processing/generating errors.
        '''
        errors={}
        # if there is 
        if bundle.obj.pk and bundle.obj.status==bundle.obj.UNCONFIGURED:
            kwargs={}
            kwargs['job']=bundle.obj
            # Special case with POST is that the data comes in as a unicode string.
            # convert it to the proper Python object.
            for name in ['config','file_config']:
                if isinstance(bundle.data.get(name), (str, unicode)):
                    bundle.data[name]=json.loads(bundle.data[name])
                elif not bundle.data.has_key(name):
                    bundle.data[name]='{}'
            if bundle.obj.pk:
                for field in ['tool',]:
                    if (getattr(bundle.obj, '_old_{0}'.format(field), None) != 
                        getattr(bundle.obj, field, None)):
                        logger.debug('Old value was: %s', 
                                     getattr(bundle.obj, '_old_{0}'.format(field)))
                        errors[field]=('This field cannot be changed, ' +
                                       'please create a new job instead')
            if bundle.obj.status != 'U':
                errors['status']= ('Cannot update a job once it has been ' +
                                   'configured, please create a new job instead (%s)' % (bundle.obj.status))  
            elif bundle.data.get('config', None):
#                 bundle.data['config']['job_id']=str(bundle.obj.pk)
#                 if bundle.obj.config:
#                     kwargs['initial']=bundle.obj.config
                validator=ToolConfigValidator(job=bundle.obj, 
                                              tool_config=bundle.data['config'],
                                              file_config=bundle.data['file_config'])
                # Remove any job files from a previous save
                bundle.obj.jobfile_set.all().delete()
                if validator.is_valid():
                    bundle.obj.config=validator.genToolConfig() # Returns a valid tool config.
                    # Stick the job files here, we can have the model save them.
                    # the model looks at job_files_pending when it sees a state change,
                    # and only then will it save the job files.
                    bundle.obj.job_files_pending=validator.genJobFiles()
                    # Update the job status if the user has set it to active, this
                    # allows us to store a config that isn't complete.
                    if bundle.data['status'] == 'A':
                        logger.debug('Setting job status to ACTIVE')
                        bundle.obj.status=bundle.obj.ACTIVE
                elif bundle.data['status'] == 'A':
                    logger.debug('Validator errors are %s', validator.errors)
                    errors['config']=validator.errors
                else: # here we are just saving an (invalid) config
                    logger.debug('Saving the config only')
                    bundle.obj.config=validator.genToolConfig(force=True) # Returns a valid tool config.
                    # Stick the job files here, we can have the model save them.
                    # the model looks at job_files_pending when it sees a state change,
                    # and only then will it save the job files.
                    bundle.obj.job_files_pending=validator.genJobFiles(force=True)
                    logger.debug('Proposed job files are %s from %s', 
                                 bundle.obj.job_files_pending,
                                 bundle.data['file_config'])
        return errors
         

class JobResource(ModelResource):
    job_id=fields.CharField('job_id', readonly=True)
    tool=fields.ToOneField(ToolResource, 'tool')
    job_files=fields.ToManyField('NMTK_server.api.JobFileResource','jobfile_set',
                                 null=True, full=True)
    results_files=fields.ToManyField('NMTK_server.api.ResultsFileResource','resultsfile_set',
                                 null=True, full=True)
    status=fields.CharField('status', readonly=True, null=True)
    tool_name=fields.CharField('tool_name', readonly=True, null=True)
    config=fields.CharField('config', readonly=True, null=True)
    def save_m2m(self, bundle):
        '''
        We don't use this at all...
        '''
        pass
    
    class Meta:
        queryset = models.Job.objects.select_related('data_file',
                                                     'jobstatus_set').all()
        authorization=JobResourceAuthorization()
        validation=JobResourceValidation()
        always_return_data = True
        resource_name = 'job'
        authentication=SessionAuthentication()
        excludes=[]
        allowed_methods=['get','put','post','delete']
        filtering= {'status': ALL,
                    'user': ALL,
                    'job_id': ALL,
                    'results_files': ALL_WITH_RELATIONS}

    def pre_save(self, bundle):
        bundle.obj.user=bundle.request.user
        return bundle
    
    def dehydrate(self, bundle):
        # Need this for Restangular, or we need to wrangle stuff.
        bundle.data['id']=str(bundle.obj.job_id)
#         if bundle.obj.data_file:
#             kwargs={}
#             if bundle.obj.config:
#                 kwargs={'initial': bundle.obj.config }
#             bundle.data['form']=forms.ToolConfigForm(job=bundle.obj, 
#                                                      **kwargs).as_json()
        bundle.data['user'] = bundle.obj.user.username
        bundle.data['tool_name']=bundle.obj.tool.name
        bundle.data['status']=bundle.obj.get_status_display()
        bundle.data['config']=json.dumps(bundle.obj.config)
#         if len(bundle.obj.jobfile_set.all()) > 0:
#             bundle.data['job_files']=[]
#             for f in bundle.obj.jobfile_set.all():
#                 bundle.data['job_files'].append(f.json())

        try:
            bundle.data['message']=bundle.obj.jobstatus_set.all()[0].message
            bundle.data['last_status']=bundle.obj.jobstatus_set.all()[0].timestamp
        except IndexError:
            pass
        return bundle
   
   
class ResultsFileResourceAuthorization(Authorization):
    def read_list(self, object_list, bundle):
        '''
        This gets a queryset (object_list) and returns a new one.  The key
        here is that we are apply *additional* filters to the default 
        queryset to restrict the output back to the user.
        
        In this case, we check to see if the user is a site admin, if they are
        then they are able to see *all* the records for active users.
        
        If they are *not* a site admin, we restrict viewing of data to the
        username that matches the current logged in user.  In short, you 
        can see your information, but noone elses.
        '''
        if bundle.request.user.is_superuser and bundle.data.get('all', False):
            return object_list
        return object_list.filter(job__user=bundle.request.user.pk)

    def read_detail(self, object_list, bundle):
        '''
        This should get a list (containing a single record).  It should
        either return an error indicating the record is not accessible by
        the user, or it should simply return.
        
        In this case, raising NotFound seems to be the only option that 
        causes the server to continue to function without an exception.  Other
        things (like not authorized) cause a 500
        '''
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.job.user.pk <> bundle.request.user.pk:
            raise Unauthorized('You lack the privilege to access this resource')
        return True

    def delete_list(self, object_list, bundle):
        # Sorry user, no deletes for you
        if bundle.request.user.is_superuser:
            return object_list
        else:
            return [obj for obj in object_list 
                    if obj.job.user == bundle.request.user] 

    def delete_detail(self, object_list, bundle):
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.job.user == bundle.request.user:
            return True
        raise Unauthorized('You lack the privilege to access this resource')

class ResultsFileResource(ModelResource):
    job=fields.ToOneField(JobResource, 'job')
    datafile=fields.ToOneField(DataFileResource, 'datafile')
    primary=fields.BooleanField('primary', readonly=True)
    class Meta:
        queryset = models.ResultsFile.objects.all()
        authorization=ResultsFileResourceAuthorization()
        always_return_data = True
        resource_name = 'job_results'
        authentication=SessionAuthentication()
        excludes=[]
        allowed_methods=['get','delete',]
        filtering= {'job': ALL,
                    'datafile': ALL,
                    'primary': ALL}    
        
class JobFileResourceAuthorization(Authorization):
    def read_list(self, object_list, bundle):
        '''
        This gets a queryset (object_list) and returns a new one.  The key
        here is that we are apply *additional* filters to the default 
        queryset to restrict the output back to the user.
        
        In this case, we check to see if the user is a site admin, if they are
        then they are able to see *all* the records for active users.
        
        If they are *not* a site admin, we restrict viewing of data to the
        username that matches the current logged in user.  In short, you 
        can see your information, but noone elses.
        '''
        if bundle.request.user.is_superuser and bundle.data.get('all', False):
            return object_list
        return object_list.filter(job__user=bundle.request.user.pk)

    def read_detail(self, object_list, bundle):
        '''
        This should get a list (containing a single record).  It should
        either return an error indicating the record is not accessible by
        the user, or it should simply return.
        
        In this case, raising NotFound seems to be the only option that 
        causes the server to continue to function without an exception.  Other
        things (like not authorized) cause a 500
        '''
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.job.user.pk <> bundle.request.user.pk:
            raise Unauthorized('You lack the privilege to access this resource')
        return True

    def delete_list(self, object_list, bundle):
        # Sorry user, no deletes for you
        if bundle.request.user.is_superuser:
            return object_list
        else:
            return [obj for obj in object_list 
                    if obj.job.user == bundle.request.user] 

    def delete_detail(self, object_list, bundle):
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.job.user == bundle.request.user:
            return True
        raise Unauthorized('You lack the privilege to access this resource')

class JobFileResource(ModelResource):
    job=fields.ToOneField(JobResource, 'job')
    datafile=fields.ToOneField(DataFileResource, 'datafile')
    namespace=fields.CharField('namespace', readonly=True)
    class Meta:
        queryset = models.JobFile.objects.all()
        authorization=JobFileResourceAuthorization()
        always_return_data = True
        resource_name = 'job_file'
        authentication=SessionAuthentication()
        excludes=[]
        allowed_methods=['get','delete',]
        filtering= {'job': ALL,
                    'datafile': ALL,
                    'namespace': ALL}

class JobStatusResourceAuthorization(Authorization):
    def read_list(self, object_list, bundle):
        '''
        This gets a queryset (object_list) and returns a new one.  The key
        here is that we are apply *additional* filters to the default 
        queryset to restrict the output back to the user.
        
        In this case, we check to see if the user is a site admin, if they are
        then they are able to see *all* the records for active users.
        
        If they are *not* a site admin, we restrict viewing of data to the
        username that matches the current logged in user.  In short, you 
        can see your information, but noone elses.
        '''
        if bundle.request.user.is_superuser:
            return object_list
        return object_list.filter(job__user=bundle.request.user.pk)

    def read_detail(self, object_list, bundle):
        '''
        This should get a list (containing a single record).  It should
        either return an error indicating the record is not accessible by
        the user, or it should simply return.
        
        In this case, raising NotFound seems to be the only option that 
        causes the server to continue to function without an exception.  Other
        things (like not authorized) cause a 500
        '''
        if bundle.request.user.is_superuser:
            return True
        elif bundle.obj.user.pk <> bundle.request.user.pk:
            raise Unauthorized('You lack the privilege to access this resource')
        return True

class JobStatusResource(ModelResource):
    job=fields.ToOneField(JobResource, 'job')

    class Meta:
        queryset = models.JobStatus.objects.all()
        always_return_data = True
        authorization=JobStatusResourceAuthorization()
        resource_name = 'job_status'
        authentication=SessionAuthentication()
        allowed_methods=['get',]
        filtering= {'job': ALL,
                    'job_id': ALL}


class PageNameResource(ModelResource):
    class Meta:
        queryset = models.PageName.objects.all()
        resource_name = 'page_name'
        always_return_data = True
        allowed_methods=['get',]
        
class PageContentResource(ModelResource):
    
    page=fields.ToOneField(PageNameResource, 'page')
    class Meta:
        queryset = models.PageContent.objects.filter(enabled=True)
        resource_name = 'page_content'
        always_return_data = True
        allowed_methods=['get',]
        filtering= {'page': ALL,}
        

    