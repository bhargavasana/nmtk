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
define(['underscore'], function (_) {	
	"use strict";
	var controller=['$scope','$log','$q','$modalInstance','api','id','name','type','operation',
	                'jobdata','Restangular',
		function ($scope, $log, $q, $modalInstance, api, id, name, type, operation,
				  jobdata, Restangular) {
			$scope.api=api;
			$scope.id=id;
			$scope.name=name;
			$scope.operation=operation;
			$scope.type=type;
			$scope.jobs_in=[];
			$scope.jobs_out=[];
			Restangular.all('job_results').getList({'job': id,
													'limit': 999}).then(function (filedata) {
				if (filedata.length) {
					_.each(filedata, function (data) {
						// Get the File ID so we can use it to query to see if it's used at all.
						var datafile_id=data.datafile.split('/').reverse()[1];
						Restangular.all('job_file').getList({'datafile': datafile_id}).then(function (job_input_file) {
							if (job_input_file.length == 0) {
								$scope.jobs_in.push(data);
							}
						});
					});
				}
			});
			$scope.form_params={'delete': true};
			
			
			
			$scope.delete=function () {
				var promises=[];
				// Remove the job in question, then cascade to the file.
				// The job needs to go before the file, so we will only do
				// the file delete after the job delete completes.
				Restangular.all('job').one(id).remove().then(function () {
					if ($scope.form_params['delete']) {
						// Remove each of the job files in question.
						_.each($scope.jobs_in, function (job_file) {
							var id=job_file.datafile.split('/').reverse()[1];
							promises.push(Restangular.all('datafile').one(id).remove());
						});
					}
					var p=$q.all(promises);
					p.then(function (d) {
						$modalInstance.close();
					}, function (d) { $modalInstance.close(); });
				});
				
				// Wait until all the deletes complete before doing the close/refresh.
				
			}
			$scope.close=function () {
				$modalInstance.dismiss();
			}
		}
	];
	return controller;
});
