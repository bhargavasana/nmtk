/**
 * @license Non-Motorized Toolkit
 * Copyright (c) 2014 Open Technology Group Inc. (A North Carolina Corporation)
 * Developed under Federal Highway Administration (FHWA) Contracts:
 * DTFH61-12-P-00147 and DTFH61-14-P-00108
 * 
 * Redistribution and use in source and binary forms, with or without modification, 
 * are permitted provided that the following conditions are met:
 *     * Redistributions of source code must retain the above copyright notice, 
 *       this list of conditions and the following disclaimer.
 *     * Redistributions in binary form must reproduce the above copyright 
 *       notice, this list of conditions and the following disclaimer 
 *       in the documentation and/or other materials provided with the distribution.
 *     * Neither the name of the Open Technology Group, the name of the 
 *       Federal Highway Administration (FHWA), nor the names of any 
 *       other contributors may be used to endorse or promote products 
 *       derived from this software without specific prior written permission.
 *       
 *       THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
 *       "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
 *       LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
 *       FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL 
 *       Open Technology Group Inc BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, 
 *       SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT 
 *       LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF 
 *       USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED 
 *       AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, 
 *       OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT 
 *       OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF 
 *       SUCH DAMAGE.
 */
define(['underscore',
        'text!configureErrorsServerTemplate',
        'text!configureErrorsClientTemplate',
        'text!cloneConfigTemplate'], function (_, configureErrorsServerTemplate,
        		configureErrorsClientTemplate,
        		cloneConfigTemplate) {	
	"use strict";
	var controller=['$scope', '$routeParams', '$location', '$modal', '$log',
		/*
		 * Output the form that is used to configure a job, and take the resulting 
		 * data to send up to the server so the job configuration can be validated.
		 * 
		 * Once a response comes back, we'll have to check for errors and then set
		 * the appropriate error messages in the template as well...
		 */
		function ($scope, $routeParams, $location, $modal, $log) {
			var FLOAT_REGEXP = /^\-?\d+((\.)\d+)?$/;
			var INTEGER_REGEXP= /^\-?\d+$/;
			$scope.loginCheck();
			var jobid=$routeParams.jobid;
			if (typeof $scope.$parent.job_uri === 'undefined' || 
			    ($scope.$parent.job_uri != $location.path())) {
				$scope.$parent.job_uri=$location.path();
				$scope.$parent.job_config=undefined;
			}
			
			// Get Job, tool, and file information, then use them to generate the form
			// configuration.
			$scope.tool_config=[];			
			
			$scope.sections={}
			$scope.toggleSection=function (type) {
				$scope.sections[type]=!$scope.sections[type];
			}
			
			
			$scope.hideField=function (namespace, property) {
				if ($scope.validation[namespace][property.name].hidden) {
					return true;
				}
				if (! _.isUndefined(property.display_if_true)) {
					if (_.isUndefined($scope.job_config[namespace])) {
						return false;
					}
					if (! _.isUndefined($scope.job_config[namespace][property.display_if_true])) {
						if ($scope.job_config[namespace][property.display_if_true].value) {
							return false;
						} else {
							return true;
						}
					}
				}
				if (! _.isUndefined(property.display_if_filled)) {
					if (! _.isUndefined($scope.job_config[namespace][property.display_if_filled])) {
						if (String($scope.job_config[namespace][property.display_if_filled].value).length) {
							return false;
						} else {
							return true;
						}
					}
				}
				return false;
			}
			$scope.disabled=false;
			$scope.rest.job.then(function (jobs) {
				var job_data=_.find(jobs, function (job) {
					return (job.id == jobid);
				});
				if (typeof job_data === 'undefined') {
					$scope.$parent.job_uri=undefined;
					$scope.$parent.job_config=undefined;
					$location.path('/job');
				}
				$scope.job_data=job_data;
				$log.debug('Job data is', job_data);
				var tool_id=job_data.tool.split('/').reverse()[1];
				
				if (job_data.config) {
					// Load the old job config if we are viewing an existing
					// jobs configuration.
					// Jobs not in the "pending" state are not modifiable.
					if (job_data.status != 'Configuration Pending') {
						$scope.disabled=true;
					}
					$scope.$parent.job_config=JSON.parse(job_data.config);
					if (_.isUndefined($scope.$parent.job_config_files)) {
						$scope.$parent.job_config_files={};
					}
					_.each(job_data.job_files, function (jf) {
						$scope.$parent.job_config_files[jf.namespace]=jf.datafile;
					});
				}
				$scope.rest.tool.then(function (row) {
					var tool_data=_.find(row, function(toolinfo) {
						return (toolinfo.id==tool_id);
					});
					$log.debug('Got tool data of ', tool_data);
					/*
					 * Go through and setup the default state of the different 
					 * sections here.
					 */
					var i=0;
					_.each(tool_data.config.input, function (data) {
						if (_.has(data,'expanded')) {
							$scope.sections[data.namespace]=data.expanded;
						} else {
							$scope.sections[data.namespace]=true;
						}
						i+=1;
					});
					_.each(tool_data.config.output, function (data) {
						if (_.has(data,'expanded')) {
							$scope.sections[data.namespace]=data.expanded;
						} else {
							$scope.sections[data.namespace]=true;
						}
						i+=1;
					});
					// If we don't have a config, we'll build a default using
					// the tool information
					var new_config=false;
					$scope.validation={};
					if (! $scope.$parent.job_config) {
						$scope.$parent.job_config={};
						new_config=true;
					}
					if (_.isUndefined($scope.$parent.job_config_files) && 
						$scope.$parent.job_config_files != true) {
						$scope.$parent.job_config_files={};
					}
					 
					_.each(['input','output'], function (section) {
						_.each(tool_data.config[section], function (data) {
							if (new_config) {
								$scope.$parent.job_config[data.namespace]={};
								if (_.isUndefined($scope.$parent.job_config_files[data.namespace])) {
									$scope.$parent.job_config_files[data.namespace]='';
								}
							}
							$scope.validation[data.namespace]={};
							_.each(data.elements, function (config_set) {
								if (new_config) {
									$scope.$parent.job_config[data.namespace][config_set.name]={};
									$scope.$parent.job_config[data.namespace][config_set.name]['type']=config_set.type;
									if (typeof config_set.default !== 'undefined' && data.type != 'File') {
//										$scope.$parent.job_config[data.namespace][config_set.name]['value']=config_set.default;
									} else if (data.type == 'File') {
//										$scope.$parent.job_config[data.namespace][config_set.name]['value']=config_set.name;
										$scope.$parent.job_config[data.namespace][config_set.name]['type']='property';
										// Note: hidden and readonly don't work for file fields.
										config_set.hidden=false;
									}
								}
								if (typeof config_set.readonly === 'undefined') {
									config_set.readonly=false;
								}
								$scope.validation[data.namespace][config_set.name]={ 'validation': config_set.validation,
																					 'type': config_set.type,
																					 'name': config_set.name,
																					 'default': config_set.default,
																					 'hidden': config_set.hidden,
																					 'readonly': config_set.readonly,
										        									 'choices': config_set.choices };
							});
						});
					});
					
					$scope.is_file_optional=function (namespace) {
						/*
						 * A file is only optional if all its properties allow a
						 * non-property field type.
						 */
						var file_optional=false;
						/*
						 * If there is at least one validation element, we need
						 * to ensure we default optional to true. If there are 0
						 * then the file is required.
						 */
						_.find($scope.validation[namespace], function (k) {
							file_optional=true;
							return true;
						});
						
						_.find($scope.validation[namespace], function (validation_data, field_name) {
							if (validation_data.type == 'property') {
								file_optional=false;
								return true;
							}
						});
						return file_optional;
					}
					
					$scope.get_options=function (options) {
						var dataset=[];
						if (_.isArray(options)) {
							_.each(options, function (opt) {
								dataset.push({'label': opt, 'value': opt});
							});
							
						} else {
							_.each(options, function (value, key) {
								dataset.push({'label': key, 'value': value});
							});
						}
						return dataset;
					}
					
					$scope.tool_name=tool_data.name;
					$scope.tool_data=tool_data;
				});
			});
			$scope.file_fields={};
			$scope.setConfigureJob(jobid);
			$scope.enableRefresh([]);
			$scope.changeTab('configurejob');

			$scope.closeConfig=function () {
				$scope.$parent.job_uri=null;
				$scope.$parent.job_config={};
				$scope.$parent.working_job_id=null;
				$location.path('/job');
			}
			$scope.constants_only={};
			$scope.rest.datafile.then(function (data_files) {
				$scope.updateFileFieldsFromResourceURI=function (key) {
					var force_property=$scope.constants_only[key];
					var force_constants=false;
					var resource_uri=$scope.$parent.job_config_files[key];
					if (typeof resource_uri !== 'undefined') {
						$log.debug('Resource URI is ', resource_uri);
						if (resource_uri !== true) {
							$scope.constants_only[key]=false;
							var df=_.find(data_files, function (datafile) {
								return (datafile.resource_uri == resource_uri);
							});
							
							if (df) {
								var fields=[];
								_.each(JSON.parse(df.fields), function (v) {
									fields.push({'label': v,
										         'value': v});
								});
								$scope.file_fields[key]=fields;
							}
						} else {
							/*
							 * this is the case when the user says they want to
							 * use all constants...
							 */
							$scope.constants_only[key]=true;
							force_constants=true;
						}
						if (force_property || force_constants) {
							_.each($scope.validation[key], function (this_data, field_name) {
								$scope.switchFieldMode(key, field_name, force_constants, force_property);
							});
						}
					} else {
						$scope.file_fields[key]=[];
					}
				}
				$scope.list_files=function (config) {
					/*
					 * Tricky! Here we need to find only those files that
					 * meet the requirements of type and spatial type,
					 * and those files must have completed loading already...
					 */
					var types=config.mime_types;
					var spatial_types = config.spatial_types;
					var files2=data_files;
					var files=[];
					if (typeof types !== 'undefined') {
						_.each(files2, function (file_entry) {
							if (_.contains(types,file_entry.content_type)) {
								files.push(file_entry);
							}
						});
						files2=files;
						files=[];
					}
					
					if (typeof spatial_types != 'undefined') {
						_.each(files2, function (file_entry) {
							_.find(spatial_types, function (st) {
								if (file_entry.geom_type && file_entry.geom_type.indexOf(st) !== -1) {
									files.push(file_entry);
									return true;
								}
							});
						});
						files2=files;
						files=[];
					}
					
					_.each(files2, function (file_entry) {
						if (/complete/i.exec(file_entry.status)) {
							files.push(file_entry);
						}
					});
					if ($scope.is_file_optional(config.namespace)) {
						/*
						 * This bit of hackery is required because when all the
						 * fields in a file are optional, and the user chooses
						 * to use a constant, then there is no file.  This
						 * results in no file chosen for the namespace, and then
						 * the section is collapsed.  By sticking true in, in
						 * this special case, we ensure that it shows the "no
						 * file" option and expands the field with constants.
						 */
						if (typeof $scope.job_config_files[config.namespace] === 'undefined' &&
							$scope.disabled) {
							$scope.constants_only[config.namespace]=true;
							$scope.job_config_files[config.namespace] = true;
						}
						files.push({'resource_uri': true,
							        'name': 'Use all Constants (no file)'})
					}
					return files;
				};
			});
			
			/*
			 * When a field is generated, this init function will set the 
			 * current default value for the field.  It is called from the 
			 * template using ng-init for all the form fields, and is also 
			 * called by the switchFieldMode function to ensure the proper
			 * defaults are chosen when the user switches field modes.
			 */
			$scope.setFieldDefaultValue=function (namespace, field) {
				// The CURRENT type for this (property or something else.)
				if (_.keys($scope.$parent.job_config).length > 0) {
					var name=$scope.validation[namespace][field]['name'];
					var field_default=$scope.validation[namespace][field]['default'];
					if (_.isUndefined($scope.$parent.job_config[namespace][field])) {
						$log.error('Field', field, 'is not defined in namespace', namespace);
						$scope.$parent.job_config[namespace][field]={
								'type': $scope.validation[namespace][field]['type'],
								'value': field_default
								};
						
					} else {
						var type=$scope.$parent.job_config[namespace][field]['type'];
						var current_value=$scope.$parent.job_config[namespace][field]['value'];
					}
					$scope.validation[namespace][field]['error']='This field is required.';
					
					
					// If the type is property, the default must be one of the fields.
					if (type == 'property') {
						if (typeof $scope.file_fields[namespace] !== 'undefined') {
							var file_fields=[];
							_.each($scope.file_fields[namespace], function (f) { 
								file_fields.push(f.value);
							});
							if (_.indexOf(file_fields, current_value) > -1) {
						    	$scope.$parent.job_config[namespace][field]['value']= current_value;
						    } else if (_.indexOf(file_fields, name) > -1) {
						    	$scope.$parent.job_config[namespace][field]['value']= name;
						    } else {
						    	$scope.$parent.job_config[namespace][field]['value']=undefined;
						    }
						}
					// If the type is choice, the default must be one of the choices.
					} else if (typeof $scope.validation[namespace][field]['choices'] !== 'undefined') {
						var options=$scope.get_options($scope.validation[namespace][field]['choices'])
						var this_default=undefined;
						
						// First try to use the current value, if that doesn't work, use
						// the field default value and return a suitable default value.
						_.find([current_value, field_default], function (default_value) {
							if (typeof default_value !== 'undefined') {
								this_default=_.find(options, function (item) {
									if (item.value == default_value) {
										return true;
									}
								return false;
								});
							}
							return (typeof this_default !== 'undefined');
						});
						if (typeof this_default === 'undefined' && $scope.validation[namespace][field]['choices'].length > 0) {
							$scope.$parent.job_config[namespace][field]['value']=$scope.validation[namespace][field]['choices'][0].value;
						} else if (typeof this_default !== 'undefined') {
							$scope.$parent.job_config[namespace][field]['value']=this_default.value;
						}
						
					// If the type is neither choice nor property, the current_value or field_default is used.
					} else {
						$scope.$parent.job_config[namespace][field]['value']=current_value || field_default;
					}
					// Note: The validation code must be called to set the correct state here (if a field requires it)
					// this is typically done in the controller by chaining a call to validation after this function.
				}
			}
			
			$scope.getFieldOptions=function (namespace, field) {
				var props=$scope.validation[namespace][field]
				var options=[{value: props.type,
					          detail: 'Use '+props.type}];
				if (props.choices) {
					options.push({value: 'choices',
						          detail: "Select from value list"});
				}
				options.push({value: 'property',
					          detail: "Use file field"});
//				$log.info('Options are', options);
				return options;
			}
			

			$scope.switchFieldMode=function (namespace, field, force_constant,
					                         force_property) {
				if (_.isUndefined(force_constant)) {
					force_constant=false;
				}
				if (_.isUndefined(force_property)) {
					force_property=false;
				}
				$log.debug('Called SwithFieldMode with ', namespace, field, force_constant)
				// This is the valid type for this field.
				var type=$scope.validation[namespace][field]['type'];
				$log.debug('The type is ', type)
				$log.debug('Current bound value is ', $scope.$parent.job_config[namespace][field]['type'])
				if (type != 'property') {
					if (force_property) {
						$scope.$parent.job_config[namespace][field]['type']= 'property'
					} else if (force_constant || 
					    ($scope.$parent.job_config[namespace][field]['type'] != 'property')) {
						/* Force the type to be a constant */
						if (force_constant) {
							$scope.$parent.job_config[namespace][field]['type'] = type;
						}
						$scope.$parent.job_config[namespace][field]['value']=undefined;
					}
				}
				$scope.setFieldDefaultValue(namespace, field);
			}
			
			
			$scope.submit_attempted=false;
			// If save_job is true then we want to simply save the current configuration.
			// So we just send it up to the server to be saved - without validation.
			$scope.submit_job=function (save_job) {
				if (_.isUndefined(save_job)) {
					save_job=false;
				}
				$log.debug($scope.job_config_form, $scope.validation);
				// If we are trying to save the job status (not submit it) then
				// we don't need to perform validation, since we will do that when
				// the user tries to submit the job itself.
				if ((! save_job) && $scope.job_config_form.$invalid) {
					$scope.submit_attempted=true;
					var opts = {
						    template: configureErrorsClientTemplate, // OR: templateUrl: 'path/to/view.html',
						    controller: ['$scope','$modalInstance', function ($scope, $modalInstance) {
											$scope.close=function () {
												$modalInstance.close();
											}
										}]
						  };
					var d=$modal.open(opts);
				} else {
					$scope.resources['job'].getList({'job_id': $scope.job_data.id}).then(function (response) {
						var data=response[0];
						if (! save_job) {
							data.status='A';
						}
						data.config=$scope.$parent.job_config;
						// Need to pass in the file configuration as well.
						data.file_config=$scope.$parent.job_config_files;
						_.each(data.file_config, function (this_data, namespace) {
							if (this_data === true) {
								data.file_config[namespace] = "";
							}
						})
						data.put().then(function (response) {
							// Return them to the job window.
							$scope.closeConfig();
						}, function (response) {
							/* Function called when an error is returned */
							$scope.$parent.errors=response.data.job.config;
							var opts = {
								    resolve: {messages: function () { return $scope.$parent.errors; } },
								    template: configureErrorsServerTemplate, // OR: templateUrl: 'path/to/view.html',
								    controller: ['$scope','$modalInstance','messages', function ($scope, $modalInstance, messages) {
													$scope.close=function () {
														$modalInstance.close();
													}
													$scope.messages=messages;
												}]
						    };
							var d=$modal.open(opts);
						});
					});
				}
			}		
			
			
			/* I had this in a custom directive before, but the reality is that
			 * it's much less complex here.  Also, there are issues with ng-options 
		     * and a local scope in Angular for some reason.
		     * Instead, this is slightly less efficient, but handles all the use
		     * cases well, not to mention it allows the error messages to be set
		     * properly.
		     */ 
			$scope.validateEntry=function (namespace, property_name) {
        		var validation=$scope.validation[namespace][property_name];
        		var value=$scope.$parent.job_config[namespace][property_name]['value'];
        		var error=undefined;
    			if (typeof value !== 'undefined') {
        			var valid=false;
        			if (value.length > 0) {
	        			if (/integer/i.test(validation.type)) {
	        				valid=INTEGER_REGEXP.test(value);
	        			} else if (/number/i.test(validation.type)) {
	        				valid=FLOAT_REGEXP.test(value);
	        			} else { // Must be string..
	        				valid=true;
	        			}
        			}
        			if (valid==false) {
        				error='Please enter a valid ' + validation.type + '.';
        			}
        			var max=undefined;
        			var min=undefined;
        			if (valid) {
        				if (typeof validation['validation'] !== 'undefined') {
        					var v=parseFloat(value);
        					if (_.has(validation['validation'], 'minimum')) {
        						min=validation['validation']['minimum'];
        						if (validation['validation']['minimum'] > v) {
        							valid=false;
        						}
        					}
        					if (_.has(validation['validation'], 'maximum')) {
        						max=validation['validation']['maximum'];
        						if (validation['validation']['maximum'] < v) {
        							valid=false;
        						}
        					}
        					if (valid == false) {
        						if (typeof max !== 'undefined' && 
								    typeof min !== 'undefined') {
        							error='Value must be between ' + min + ' and ' + max;
        						} else if (typeof max !== 'undefined') {
        							error='Value must be less than or equal to' + max;
        						} else if (typeof min !== 'undefined') {
        							error='Value must be greater than or equal to' + min;
        						}
        					}
        				}
        			}
    			} else {
    				valid=false;
    				error="This field is required";
    			}
    			$scope.validation[namespace][property_name]['error']=error;
    			$log.debug('Setting validity for', namespace+':'+property_name, 'to', valid);
				$scope.job_config_form[namespace+':'+property_name].$setValidity('nmtk',valid);
				
				if (! valid) {
					$log.debug($scope.job_config_form);
					$log.debug('INVALID?', valid, 'Value:', value, 'Error:',error, namespace + ':'+ property_name);
				}
				$log.debug('VALID?', valid, 'Value:', value, 'Error:',error, namespace + ':'+ property_name);

			}
			
			
			$scope.cloneConfig=function (target_namespace) {
				var modal_dialog=$modal.open({
					backdrop: true,
					scope: $scope,
				    template:  cloneConfigTemplate, // OR: templateUrl: 'path/to/view.html',
				    controller: 'CloneConfigCtrl'
				});
				modal_dialog.result.then(function (job) {
					var other_config=JSON.parse(job.config);
					var other_files=job.job_files;
					/*
					 * For a config we should have 3 dimensions - the namespace (outer most)
					 * Then the name of the setting (middle)
					 * Then an object which contains the "type" and the value. (innermost)
					 */
					var nsp_config;
					var nsp_file;
					_.find(other_config, function (data, oc) {
						if (oc == target_namespace) {
							nsp_config=data;
							return true;
						}
					});
					_.find(other_files, function (fdata) {
						if (fdata.namespace == target_namespace) {
							nsp_file=fdata.datafile;
							return true;
						}
					});
					if (typeof nsp_config !== 'undefined') {
						$scope.$parent.job_config[target_namespace]=nsp_config;
					} 
					if (typeof nsp_file !== 'undefined') {
						$scope.$parent.job_config_files[target_namespace]=nsp_file;
						$scope.updateFileFieldsFromResourceURI(target_namespace);
					}
					
				});
			}
		}
	];
	return controller;
});
