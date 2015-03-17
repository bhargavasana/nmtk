import simplejson as json
from NMTK_server import models
import decimal
import collections
import logging
logger=logging.getLogger(__name__)


class ToolConfigValidator(object):
    def __init__(self, job, file_config, tool_config):
       self.job=job
       self.file_config=file_config
       self.tool_config=tool_config
       self.errors=None
       
    def genToolConfig(self, force=False):
        '''
        The validation process "fills in" empty spaces with hidden and/or default
        settings, here we return it.
        '''
        if not (force or self.is_valid()):
            return None
        if not hasattr(self,'_tool_config'):
            self._tool_config=self.tool_config
        return self._tool_config
    
    def validate(self, type, v, required, readonly, default, fields=[], validation={}):
        '''
        Handle all the validation criteria for the types here.
        '''
        error=None
        if type == 'property':
            if not required and not v:
                pass
            elif v not in fields:
                error='Please choose from the available fields'
        elif readonly:
            if v != default:
                error='Readonly field must have a value of {0}'.format(default)
        elif type == 'numeric':
            if required and not v:
                error='Please enter a valid numeric value'
            elif v:
                try:
                    v=decimal.Decimal(v)  
                    error=self.range_check(v, validation)
                except:
                    error='Please enter a valid numeric value'
        elif type == 'integer':
            if required and not v:
                error='Please enter a valid integer value'
            elif v:
                try:
                    if str(v).isdigit():
                        v=int(v)
                        error=self.range_check(v, validation)
                    else:
                        error='Please enter a valid integer value'
                except:
                    error='Please enter a valid integer value'
        elif type == 'string':
            if required and not v:
                error='Please enter a valid string value'
        return error
            

    def range_check(self, v, validation):
        max=validation.get('maximum', None)
        min=validation.get('minimum', None)
        try:
            if min:
                min=decimal.Decimal(min)
            if max:
                max=decimal.Decimal(max)
            if min and max and (min > v or max < v):
                return 'Value must be between {0} and {1}'.format(min, max)
            if min and min > v:
                return 'Value must be less than {0}'.format(min)
            if max and max < v:
                return 'Value must be greater than {0}'.format(max)
            return None
        except:
            return 'Tool validation criteria is invalid (contact tool developer)'
    
    def is_valid(self):
        self.file_config_parsed={}
        # Convert the URI into proper files objects, otherwise we won't be 
        # able to get things like the list of valid fields from the namespace
        # entries.
        logger.debug('File config is %s', self.file_config)
        for namespace, uri in self.file_config.iteritems():
           if len(uri) > 0:
               try:
                   id=uri.rsplit('/',2)[-2]
                   self.file_config_parsed[namespace]=models.DataFile.objects.get(pk=id)
               except: 
                   pass
        # Get the configuration for this particular tool.
        # config from the user is of the form {'namespace':{'field_name': {type: type, value: value} } }
        tool_config=self.job.tool.toolconfig.json_config
        errors=collections.defaultdict(dict)
        for entry in ['input', 'output']:
            for config_entry in tool_config.get(entry, []):
                namespace_config=self.tool_config.get(config_entry['namespace'], {})
                
                for item in config_entry.get('elements', []): # each item here will have name, required, and type keys
                    data=namespace_config.get(item['name'], None) # So now we have type and value keys
                    validate_kwargs={}
                    # Verify that the required fields are provided
                    if data is None:
                        # if the user didn't provide the config for an item, 
                        # but there is a default, then use the default.
                        # This would also work for hidden stuff.
                        if item.get('default', None) and not item.get('required', True):
                            namespace_config[item['name']]={'type': item['type'],
                                                            'value': item['default']}
                            if id(self.tool_config) != id(namepsace_config):
                                self.tool_config[config_entry['namespace']]=namespace_config
                        # if it is a required field, but there is no default, then
                        # we will give them an error message.
                        elif item.get('required', True):
                            errors[config_entry['namespace']][item['name']]='This field is required'
                        continue
                    else:
                        allowed_types=[]
                        validate_kwargs['validation']=item.get('validation',{})
                        if config_entry['type'].lower() == 'file':
                            # Get the list of allowable file fields.
                            validate_kwargs['fields']=getattr(self.file_config_parsed.get(config_entry['namespace']),'fields',[])
                            if item['type'] != 'property':
                                allowed_types.append('property')
                        allowed_types.append(item['type'])
                    data_type=data.get('type', None)
                    value=data.get('value', None)
                    if not data_type:
                        errors[config_entry['namespace']][item['name']]='A valid type must be specified with the config'
                        continue
                    else:
                        error=self.validate(data_type, value, 
                                            item.get('required', True), 
                                            item.get('readonly', False),
                                            item.get('default', None),
                                            **validate_kwargs)
                        if error:
                            errors[config_entry['namespace']][item['name']]=error
        if len(errors): # Only return errors dict if there are errors.
            self.errors=errors
            return False
        return True
                    
                        
        
    
    def genJobFiles(self, force=False):
        '''
        Here we make a list of 
        '''
        if not hasattr(self, '_job_files'):
            self._job_files=[]
            if force or self.is_valid():
                logger.debug('File config parsed is %s', self.file_config_parsed)
                for namespace, datafile in self.file_config_parsed.iteritems():
                    self._job_files.append(models.JobFile(job=self.job,
                                                          datafile=datafile,
                                                          namespace=namespace))
        return self._job_files
        