from django import forms
from NMTK_server import models
from django.core.urlresolvers import reverse_lazy, reverse
import json
import logging
import re
import collections
from django.utils.html import conditional_escape, format_html
from django.utils.encoding import smart_text, force_text, python_2_unicode_compatible
from django.utils import six
from django.utils.safestring import mark_safe
logger=logging.getLogger(__name__)
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import ugettext, ugettext_lazy as _
from django.contrib.auth import get_user_model
User=get_user_model()


class NMTKRegistrationForm(UserCreationForm):
    error_messages = {
        'duplicate_username': _("A user with that username already exists."),
        'password_mismatch': _("The two password fields didn't match."),
        'duplicate_email': _("An user with that email address already exists."),
    }
    def __init__(self, *args, **kwargs):
        tos=kwargs.pop('tos', False)
        super(NMTKRegistrationForm, self).__init__(*args, **kwargs)
        if tos:
            tos_url=reverse('terms_of_service')
            self.fields['tos'] = forms.BooleanField(widget=forms.CheckboxInput,
                                                    label=mark_safe(_(u'I have read and agree to the <a target="_blank" href="{0}">Terms of Service</a>'.format(tos_url))),
                                                    error_messages={'required': _("You must agree to the terms to register")})
    def clean_email(self):
        # Since User.username is unique, this check is redundant,
        # but it sets a nicer error message than the ORM. See #13147.
        email = self.cleaned_data["email"]
        try:
            User._default_manager.get(email__iexact=email)
        except User.DoesNotExist:
            return email
        raise forms.ValidationError(self.error_messages['duplicate_email'])
    
    class Meta:
        model=User
        fields=('first_name','last_name','email','username')
    
    def save(self, commit=True):
        '''
        Force active to false and superuser to false for the user object.
        '''
        user=super(NMTKRegistrationForm,self).save(commit=False)
        user.is_active=False
        user.is_superuser=False
        if commit:
            user.save()
        return user

class DataFileForm(forms.ModelForm):
    class Meta:
        model=models.DataFile
        fields=('file',)
        

class JobSubmissionFormTool(forms.ModelForm):
    def __init__(self, user, *pargs,**kwargs):
        super(JobSubmissionFormTool, self).__init__(*pargs, **kwargs)
        self.fields["tool"].queryset=models.Tool.objects.filter(active=True)
           
    class Meta:
        model=models.Job
        fields=('tool',)
        
class JobSubmissionForm(forms.ModelForm):
    
    def __init__(self, user, *pargs,**kwargs):
        super(JobSubmissionForm, self).__init__(*pargs, **kwargs)
        self.fields["tool"].queryset=models.Tool.objects.filter(active=True)
           
    class Meta:
        model=models.Job
        fields=('tool',)
      
# class ToolConfigForm(forms.Form):
#     '''
#     Construct a form object using the configuration for
#     a particular tool.  This should allow the user to
#     either provide "field mappings" from the source to the destination 
#     file, or set configuration variables (parameters) (or both.)
#     
#     This form requires two input arguments:
#         - config: the FULL config object for this particular
#                   tool.
#         - source_fields: A list of the FIELDS that were in the data source
#                          this is likely to come from OGRInfo, and is basically
#                          a mapping from the fields in the data file to those fields
#                          that are required/exepected by the model for processing.
#     '''
#     mappings={'number': forms.DecimalField,
#               'string': forms.CharField,
#               'integer': forms.IntegerField,}
#     def __init__(self, *args, **kwargs):
#         if kwargs.has_key('job'):
#             job=kwargs.pop('job')
#         else:
#             job=args[0]
#             args=args[1:]
#         # Populate the parameters list with those fields that contain 
#         # user-settable parameters.  Populate data_fields with those
#         # fields that should be mapped over from the fields in the source
#         # data file.
#         self.data_fields=[]
#         self.parameters=[]
#         super(ToolConfigForm, self).__init__(*args, **kwargs)
#         config=job.tool.toolconfig.json_config
# #         job.data_file.processed_file.seek(0)
# #        data=json.loads(job.data_file.processed_file.read())
# #        source_fields=data['features'][0]['properties'].keys()
# #        logger.debug('Fields are %s', source_fields)
#         # build choices so the user can choose the mapping(s)
#         dataChoices=[(field, field) for field in source_fields]          
#         input=config['input']
#         self.fields['job_id']=forms.CharField(initial=job.pk,
#                                               widget=forms.HiddenInput)
#         for dataset in input:
#             for field_name, data in ((e['name'], e) for e in dataset['elements']):
#                 # these are the values the user needs to provide.
#                 if data['type'] in self.mappings:
#                     fieldObj=self.mappings[data['type']]
#                     fargs={'required': data.get('required', False),
#                            'help_text': data.get('description','')}
#                     if data.has_key('default'):
#                         fargs['initial']=data['default']
#                     self.fields[field_name]=fieldObj(**fargs)
#                     self.parameters.append(field_name)
#                 # These are the fields that need to come from the data source.
#                 elif data['type'] == 'property':
#                     fargs={'choices': dataChoices,
#                            'help_text': data.get('description','')}
#                     if field_name in source_fields:
#                         fargs['initial']=field_name
#                     self.fields[field_name]=forms.ChoiceField(**fargs)
#                     self.data_fields.append(field_name)
#             
#     def as_json(self):
#         '''
#         A method that outputs the form fields as a set of categorized JSON
#         data structures rather that a simple <p> list.
#         
#         def _html_output(self, normal_row, error_row, row_ender, help_text_html, errors_on_separate_row):
# 
#         '''    
#         top_errors = self.non_field_errors() # Errors that should be displayed above all fields.
#         output, hidden_fields = [], []
#         output={'errors': [],
#                 'fields': {}}
#         for name, field in self.fields.items():
#             result=output['fields'][name]={}
#             if name in self.parameters:
#                 result['type']='parameter'
#             elif name in self.data_fields:
#                 result['type']='choice'
#             html_class_attr = ''
#             bf = self[name]
#             bf_errors = self.error_class([conditional_escape(error) for error in bf.errors]) # Escape and cache in local variable.
#             if bf.is_hidden:
#                 # Indicate if the field is hidden, so we don't show it.
#                 result['hidden']= True
#             css_classes = bf.css_classes()
#             if css_classes:
#                 result['classes']='%s' % css_classes
#             else:
#                 result['classes']=None
#             if bf.label:
#                 label = conditional_escape(force_text(bf.label))
#                 # Only add the suffix if the label does not end in
#                 # punctuation.
#                 if self.label_suffix:
#                     if label[-1] not in ':?.!':
#                         label = format_html('{0}{1}', label, self.label_suffix)
#                 label = bf.label_tag(label) or ''
#             else:
#                 label = ''
#             
#             result['help_text']=force_text(field.help_text or '')
#             result['errors']=force_text(bf_errors)
#             result['label']=force_text(label)
#             result['html_class_attr']=html_class_attr
#             result['field']=six.text_type(bf)
#         if top_errors:
#             output['errors'].append(error_row % force_text(top_errors))
#         return output
