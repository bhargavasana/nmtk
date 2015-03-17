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
define([  'text!jobActionsCellTemplate'
        , 'text!viewJobModalTemplate'
        , 'text!jobDescriptionCellTemplate'
        , 'text!jobStatusCellTemplate'
        , 'text!JobStatusHistoryTemplate'
        , 'text!deleteJobModalTemplate'], function (jobActionsCellTemplate,
        		viewJobModalTemplate, 
        		jobDescriptionCellTemplate, jobStatusCellTemplate,
        		JobStatusHistoryTemplate, DeleteJobModalTemplate) {	
	"use strict";
	var controller=['$scope','$routeParams','$modal','$position','$location','$log','$q',
	                'Restangular',
		/*
		 * This is the controller for Jobs - in particular viewing and controlling
		 * a job.  Here we'll work with dialogs to create new jobs and then 
		 * choose/set the parameters for them.
		 */
		
		function ($scope, $routeParams, $modal, $position, $location, $log, $q,
				  Restangular) {
			$scope.loginCheck();
			$scope.enableRefresh(['job']);
			$scope.refreshData('job');
			//var jobid=$routeParams.jobid;
			$log.info('In JobCtrl');
			$scope.changeTab('viewjob');
			
			$scope.deleteJob=function (api, item, name, type, operation) {
				if ((typeof(operation) === 'undefined') || (! operation) ) {
					operation='Delete';
				}
				
				var modal_dialog=$modal.open({
					controller: 'DeleteJobCtrl',
					resolve: {api: function () { return api; },
						      id: function () { return item.id; },
						      name: function () { return name; },
						      operation: function () { return operation; },
						      type: function () { return type; },
						      jobdata: function () { return $scope.rest['job']}},
					template: DeleteJobModalTemplate
				});
				modal_dialog.result.then(function(result) {
					$scope.refreshData('job');
					$scope.refreshData('datafile');
				});
			}
			
			$scope.viewJobStatusLog=function(job) {
				$scope.view_job_opts = {
					backdrop: true,
					keyboard: true,
					backdropClick: true,
					scope: $scope,
					template:  JobStatusHistoryTemplate,
					controller: 'JobStatusHistoryCtrl',
					resolve: { jobdata: function () { return job; } }
				};
				var d=$modal.open($scope.view_job_opts);
			};
			
			$scope.openDialog=function(job) {
				$scope.view_job_opts = {
					backdrop: true,
					keyboard: true,
					backdropClick: true,
					scope: $scope,
					template:  viewJobModalTemplate,
					controller: 'ViewJobCtrl',
					resolve: { jobdata: function () { return job; } }
				};
				var d=$modal.open($scope.view_job_opts);
				d.result.then(function(result) {
					if (result) {
						result.put().then(function () {
							$scope.refreshData('job');
						});
					}
				});
			};		
			$scope.gridOptions= {
					 data: 'job_cache',
					 showFooter: false,
					 showFilter: true,
					 rowHeight: 75,
					 enableColumnResize: false,
					 enableRowSelection: false,
					 multiSelect: false,
					 plugins: [new ngGridFlexibleHeightPlugin()],
					 selectedItems: $scope.selections,
					 columnDefs: [  { width: '10%',
				                      sortable: false,
				                      cellClass: 'cellCenterOverflow',
				                      cellTemplate: jobActionsCellTemplate,
				                      displayName: ''}
				           		  , { width: '50%',
						 		      sortable: false,
						              cellTemplate: jobDescriptionCellTemplate,
						              displayName: 'Job Description'}
						          , { field: 'status',
						              width: '12%',
						              displayName: 'Status'}
						          , { width: '28%',
					        	      sortable: false,
						              cellTemplate: jobStatusCellTemplate,
						              displayName: 'Tool Reported Status'}
						          ],
					 showColumnMenu: false };
		}
	];
	return controller;
});
