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
define(['angular', 'underscore','leaflet',
        'text!AdvancedFiltersTemplate',
        'text!ColorRampSelectionTemplate'], function (angular, _, 
        										   L, 
        										   AdvancedFiltersTemplate,
        										   ColorRampSelectionTemplate) {
	"use strict";
	var controller=['$scope','$routeParams','$location','$log','$http',
	                '$timeout', 'leafletData','Restangular', '$q', '$modal',
        /*
		 * A variant of the ViewResults Controller that uses leaflet-directive 
		 * rather than leaflet directly.
		 */
	        
		function ($scope, $routeParams, $location, $log, $http, $timeout, 
				  leafletData, Restangular, $q, $modal) {
			$scope.loginCheck();
			$scope.changeTab('datafile_view');
			$scope.layercount=0;
			/*
			 * Filters will be specific for datafile or job, so here we will
			 * actually store the filters and reset them if the results_uri
			 * changes.  This allows us to make it seem like the view is
			 * persistent (when it really isn't!)
			 */
			if (_.isUndefined($scope.$parent.results_uri) ||
				$scope.$parent.results_uri != $location.path()) {
				$scope.$parent.results_uri=$location.path();
				//$scope.$parent.result_field=null;
				$scope.$parent.customFilters=[];
			} 
			if (_.isUndefined($scope.preferences.config.ramp)) {
				$scope.preferences.config.ramp={'ramp_id': 0,
						     					'reverse': 'false'};
			} 
			/*
			 * Here we figure out of we are viewing a file, or a set of job
			 * results.  The difference is that a file will have an integer
			 * file identifier.  While a job will have a UUID value, consisting
			 * of numbers and letters.
			 */
			if (/^\d+$/.test($routeParams.id)) {
				$scope.source_path='/files';
				$timeout(function () { getDatafile($routeParams.id); }, 0);
			} else {
				$scope.source_path='/job';
				$timeout(function () { getJobInfo($routeParams.id); }, 0);
			}
			
			
			$log.debug('Parameters are ', $routeParams);
			
			// Simple function to return true or false depending on whether
			// there are custom filters enabled.
			$scope.customFiltersEnabled=function () {
				return ! (_.isEmpty($scope.$parent.customFilters));
			}
			/*
			 * Function to change the current filters.  This ensures that 
			 * we consistently apply scrolling, etc. whenever a filter set
			 * change occurs.
			 */
			$scope.setCustomFilters=function (filters) {
				if (_.isUndefined(filters)) {
					filters=[];
				}
				$scope.$parent.customFilters=filters;
				$scope.getPagedDataAsync($scope.page_size, 0, '', 'nmtk_id');
				$scope.clearSelection();
				$scope.gridOptions.ngGrid.$viewport.scrollTop(0);
			}
			
			$scope.changeColors=function () {
				var opts = {
					    template:  ColorRampSelectionTemplate, // OR: templateUrl: 'path/to/view.html',
					    controller: 'ColorRampSelectionCtrl',
					    resolve:{'ramp': function () { return $scope.preferences.config.ramp; } },
					    scope: $scope
					  };
				
				var modal_dialog=$modal.open(opts);
				
				modal_dialog.result.then(function(result) {
					/*
					 * If the ramp id changes here we need to reload stuff, but
					 * we let that happen in the $watch defined later - so no 
					 * need to handle it here - we'll just store the changed value.
					 */
					$scope.preferences.config.ramp=result;
					$scope.savePreferences();
				});
			}
			
			$scope.advanced_filters=function () {
				var opts = {
					    template:  AdvancedFiltersTemplate, // OR: templateUrl: 'path/to/view.html',
					    controller: 'AdvancedFiltersCtrl',
					    resolve:{'filters': function () { return _.clone($scope.$parent.customFilters); },
					    	     'datafile_api': function () { return $scope.datafile_api;}
					    },
					    scope: $scope
					  };
				
				var modal_dialog=$modal.open(opts);
				
				modal_dialog.result.then(function(result) {
					/*
					 * We only want to reload things if the filters change - since
					 * otherwise we'll reset the current page the user is viewing,
					 * etc.
					 */
					if (! _.isEqual($scope.$parent.customFilters, result)) {
						// Here we reset things since the filters changed we need
						// to go back to the first page, etc.
						$scope.setCustomFilters(result);
					} 
				});
			}
			
			
			/*
			 * A function that, when given a job identifier, locates the 
			 * primary results for that job and then loads it's respective
			 * data file.
			 */
			var getJobInfo=function (job_id) {
				$scope.rest['job'].then(function (data) {
					$scope.refreshData('datafile');
					$scope.job_api=_.find(data, function (row) {
						if (row.id ==  job_id) {
							return true;
						}
					});
					if (typeof $scope.job_api === 'undefined') {
						// Do something here, because the job is not defined,
						// they probably used a bookmark for a deleted job
						// or are trying to see something they don't have
						// access to.
						$scope.$parent.preview_datafile_api=undefined;
						$scope.$parent.preview_job_api=undefined;
						$location.path($scope.source_path);
					}
					var results_file=_.find($scope.job_api.results_files, function (datafile) {
						return datafile.primary;
					});

					if (typeof results_file !== 'undefined') {
						getDatafile(results_file.datafile.split('/').reverse()[1]);
					} else {
						// they specified a job that has no complete 
						// primary results
						$scope.$parent.preview_datafile_api=undefined;
						$scope.$parent.preview_job_api=undefined;
						$location.path($scope.source_path);
					}
				});
			}
				
			var getDatafile=function (datafile_id) {
				$scope.resources['datafile'].getList().then(function (data) {
					$scope.datafile_api=_.find(data, function(row) {
						// Only allow viewing of complete files, since
						// others are not visible for this page.
						if ((datafile_id == row.id) &&
							(/complete/i.test(row.status))) {
							return true;
						}
					});
	                $scope.current_datafile_id = $scope.datafile_api.id
					if (_.isUndefined($scope.datafile_api)) {
						$scope.$parent.preview_datafile_api=undefined;
						$scope.$parent.preview_job_api=undefined;
						$location.path($scope.source_path);
					}
					$scope.fields=_.sortBy(JSON.parse($scope.datafile_api.fields),
										   function (a) { return a.toLowerCase(); });
					if (! _.contains($scope.fields, $scope.$parent.result_field)) {
						$scope.$parent.result_field=null;
					}
					if ($scope.$parent.result_field==null) {
						$scope.$parent.result_field=$scope.datafile_api.result_field;
					}  
					
					
					process_data();
				});
			}
			
						
			$scope.filterOptions= { filterText: "",
									userExternalFilter: true };
							
			
			$scope.totalServerItems=0;
			$scope.selections=[];
			$scope.page_size=100;
			$scope.pagingOptions= {
			};
			$scope.columnOptions=[];
			$scope.sortInfo= { fields: ['nmtk_id'],
							   directions: ['asc'] };

			/*
			 * Note: This relies on leaflet being available...
			 */
			function getBounds(bbox) {
				var southWest = new L.LatLng(bbox[1], bbox[0]);
				var northEast = new L.LatLng(bbox[3], bbox[2]);	
				return L.latLngBounds(southWest, northEast);
			}
			
			$scope.$on('ngGridEventScroll', function (e) {
				$log.info('Got paging event', e);
				$scope.getPagedDataAsync($scope.page_size, $scope.paging_offset+$scope.page_size,
						                 $scope.filterOptions.filterText,$scope.sort_field);
			});
		            				
			
			$scope.getPagedDataAsync=function(pageSize, offset, searchText, order){
				$scope.paging_offset=offset;
				if ($scope.datafile_api) {
					var options={offset: offset,
							     limit: pageSize,
							     search: searchText,
							     order_by: order,
							     format: 'pager'};
					if (! _.isEmpty($scope.$parent.customFilters)) {
						/*
						 * If there are filters, we need to build them into something
						 * that the API will recognize - Django filter syntax, we do
						 * that here, then jsonify the dictionary to send it to the API.
						 */
						var filters=[];
						_.each($scope.$parent.customFilters, function (filterSet) {
							// Format of each custom filter is (field, filterType, value)
							filters.push([filterSet.model_field + '__' + filterSet.criteria, filterSet.filter_value]);
						});
						options['filters']=angular.toJson(filters);
					}
					$log.info('Making request for ', $scope.datafile_api.download_url, options);
					$http.get($scope.datafile_api.download_url, {params: options}).success(function (data) {
						$scope.totalServerItems=data.meta.total;
						$scope.pagingOptions.currentPage=(data.meta.offset/data.meta.limit)+1
						if ($scope.paging_offset > 0) {
							$scope.data= $scope.data.concat(data.data);
		//					$scope.data.push.apply($scope.data, data.data);
						} else {
							$scope.data=data.data;
						}
						if ($scope.columnOptions.length == 0) {
							$scope.columnOptions=[]
							var visible=false;
							var i=0;
							var result_field=$scope.datafile_api.result_field;
							if (result_field) {
								// If there is a result field, no need to
								// show others.
								i=99;
							}
							_.each(data.data[0], function (col_val, col_name) {
								if ((i <= 1) || (col_name=='nmtk_id') || 
								    (col_name == result_field)) {
									visible=true;
								} else {
									visible=false;
								}
								$scope.columnOptions.push({ field: col_name,
									                        visible: visible});
								i += 1;
							});
//							}
						}
					});
				}
			};
			$scope.olcount=0;
			$scope.olsubcount=0;
			$scope.leaflet_layer_count=0;
			
			var updateHighlightSelected=function () {
				if ($scope.spatial) {
					if ($scope.leaflet.layers.overlays['highlight_selected' + $scope.olsubcount]) {
						delete $scope.leaflet.layers.overlays['highlight_selected'+$scope.olsubcount];
					}
					$scope.olsubcount += 1;
					if ($scope.highlight_selected) {
						var ids=[];
						_.each(newVal, function (data) {
							ids.push(data.nmtk_id);
						});
						$scope.leaflet.layers.overlays['highlight_selected'+$scope.olsubcount]= {
					            name: 'Visible Feature',
					            type: 'wms',
					            visible: true,
					            url: $scope.datafile_api.wms_url,
					            layerOptions: { layers: "highlight_selected",
					            	            ids: ids,
					            	            style_field: $scope.result_field || '',
					                    		format: 'image/png',
					                    		ramp: $scope.preferences.config.ramp.ramp_id,
					                    		reverse: $scope.preferences.config.ramp.reverse,
					                    		transparent: true }
					    }
					}
				}
			}
			
			var updateSelectedFeatures=function () {
				var ids=[];
				var clear=true;
				_.each($scope.selected_features, function (data) {
					ids.push(data.nmtk_id);
					/*
					 * Check to see if the selected item (if there is one) is
					 * still in the list of features.  Otherwise we need
					 * to clear the selection.
					 */
					if ($scope.selected_selected.length != 0) {
						if (data.nmtk_id == $scope.selected_selected[0].id) {
							clear=false;
						}
					}
				});
				if (clear) {
					$scope.selected_selected.length=0;
				}
				if ($scope.spatial) {
					if ($scope.leaflet.layers.overlays['highlight' + $scope.olcount]) {
						delete $scope.leaflet.layers.overlays['highlight'+$scope.olcount];
					}
				}
				$scope.olcount += 1;
				if ($scope.spatial) {
					if (ids.length) {
						$scope.leaflet.layers.overlays['highlight'+$scope.olcount]= {
					            name: 'Selected Features',
					            type: 'wms',
					            visible: true,
					            url: $scope.datafile_api.wms_url,
					            layerOptions: { layers: "highlight",
					            	            ids: ids.join(','),
					            	            style_field: $scope.result_field ||'',
					                    		format: 'image/png',
					                    		ramp: $scope.preferences.config.ramp.ramp_id,
					                    		reverse: $scope.preferences.config.ramp.reverse,
					                    		transparent: true }
					    }
					}
				}
			}
			
			
			var addResultWMS=function () {
				if ($scope.spatial) {
					if ($scope.leaflet.layers.overlays['results'+$scope.leaflet_layer_count]) {
						delete $scope.leaflet.layers.overlays['results'+$scope.leaflet_layer_count];
					}
					$scope.leaflet_layer_count+=1;
					$scope.leaflet.layers.overlays['results'+$scope.leaflet_layer_count]= {
				            name: 'Tool Results',
				            type: 'wms',
				            visible: true,
				            url: $scope.datafile_api.wms_url,
				            layerOptions: { layers: $scope.datafile_api.layer,
				            				style_field: $scope.result_field || '',
				                    		format: 'image/png',
				                    		ramp: $scope.preferences.config.ramp.ramp_id,
				                    		reverse: $scope.preferences.config.ramp.reverse,
				                    		transparent: true }
				    };
				}
			}
			
			var updateLegendGraphic=function () {
				if ($scope.spatial) {
					var url=$scope.datafile_api.wms_url;
					var ret = [];
					var data={ layers: $scope.datafile_api.layer,
            					style_field: $scope.result_field || '',
            					request: 'getLegendGraphic',
            					format: 'image/png',
            					ramp: $scope.preferences.config.ramp.ramp_id,
            					reverse: $scope.preferences.config.ramp.reverse,
            					transparent: true }
				    for (var d in data)
				       ret.push(encodeURIComponent(d.toUpperCase()) + "=" + encodeURIComponent(data[d]));
					url = url + '?' + ret.join("&");
					$scope.legend_url=url;
				}
			}
			
			var updateMapComponents=function () {
				addResultWMS();
				if ($scope.selected_selected) {
					updateHighlightSelected();
				}
				if ($scope.selected_features) {
					updateSelectedFeatures();
				}
				updateLegendGraphic();
			}
			
			/*
			 * If preferences are loaded then we need to use the loaded preference
			 * data.
			 */
			$scope.$watch('preferences', function (newVal, oldVal) {
				updateMapComponents();
			});
			
			$scope.$watch('result_field', function (newVal, oldVal){
				$scope.$parent.result_field=newVal;
				updateMapComponents();
			});
			
			$scope.changeJobFile=function() {
				// Change the path when the job file is changed
				$location.path("view_results/"+$scope.current_datafile_id);
			};
			
			$scope.$watch('job_id', function (newVal, oldVal){
				$scope.$parent.result_field=newVal;
				updateMapComponents();
			});
			
			
			$scope.$watch('preferences.config.ramp', function (newVal, oldVal){
				updateMapComponents();
			});
			
			// Whenever a feature is selected in the table, we will match that feature in
			// the view window...
			$scope.$watch('selected_selected', function (newVal, oldVal) {
				updateHighlightSelected();
			}, true);
			
			
			// Whenever a feature is selected in the table, we will match that feature in
			// the view window...
			$scope.$watch('selected_features', function (newVal, oldVal) {
				updateSelectedFeatures();
			}, true);
			
			// When someone selects items via the "results" grid it goes
			// into selections, which we then need to copy over to selected_features
			
			$scope.$watch('selections', function (newVal, oldVal) {
				// If we're working with results from a map-click, then clicking on
				// a row will remove those results.
				if ($scope.feature_query_results) {
					$scope.selected_features=[];
					$scope.selected_selected.length=0;
					$scope.feature_query_results=false;
				}
				var ids=[]
				_.each($scope.selected_features, function (data) {
					ids.push(data.nmtk_id);
				});
				if (! $scope.selected_features) {
					$scope.selected_features=newVal;
				} else {
					_.each(newVal, function (data) {
						if (! _.contains(ids, data.nmtk_id)) {
							$scope.selected_features.push(data);
						}
					})
				}
		//		$scope.selected_features=newVal;
			},true);
			
			// We watch reloadData to signal to ng-grid that it should reset its 
			// selections and reload data.  This is because Ng-grid does not have a
			// method by which we can *unselect* selected rows (easily.)
			$scope.reloadData=1;
			/*
			 * When the selection is cleared, just truncate all the lists of selected 
			 * stuff to 0 and then reload the data for the grid (to unselect items.)
			 */
			$scope.clearSelection=function() {
//				_.each($scope.selected_features, function (v, index) {
//					$scope.gridOptions2.selectItem(index, false);
//				});
				_.each($scope.data, function (v, index) {
					$scope.gridOptions.selectItem(index, false);
				});
				$scope.selected_features.length=0;
			}
			
			
			$scope.$on('leafletDirectiveMap.click', function(ev, e) {
				leafletData.getMap().then(function (leafletMap) {
			        $scope.clearSelection();
			        $scope.feature_query_results=true
					var config={params: {lat: e.leafletEvent.latlng.lat,
										 lon: e.leafletEvent.latlng.lng,
										 zoom: leafletMap.getZoom(),
										 format: 'query'}};
					$http.get($scope.datafile_api.download_url, config).success(function (data) {
						//$log.info('Result from query was %s', data);
						$scope.selected_features=data.data;
					})
				});
		    });
			function ngGridLayoutPlugin () {
			    var self = this;
			    this.grid = null;
			    this.scope = null;
			    this.init = function(scope, grid, services) {
			        self.domUtilityService = services.DomUtilityService;
			        self.grid = grid;
			        self.scope = scope;
			    };
			
			    this.updateGridLayout = function () {
			        if (!self.scope.$$phase) {
			            self.scope.$apply(function(){
			                self.domUtilityService.RebuildGrid(self.scope, self.grid);
			            });
			        }
			        else {
			            // $digest or $apply already in progress
			            self.domUtilityService.RebuildGrid(self.scope, self.grid);
			        }
			    };
			}
			
			$scope.selected_selected=[];

		
		    $scope.gridOptions2={data: 'selected_features',
		    		             showColumnMenu: true,
		    		             multiSelect: false,
		    		             columnDefs: 'columnOptions',
		    		             showFooter: false,
		    		             selectedItems: $scope.selected_selected}
		    
			$scope.gridOptions= {data: 'data',
								 columnDefs: 'columnOptions',
		//						 enablePaging: true,
								 showFooter: true,
								 multiSelect: true,
								 selectedItems: $scope.selections,
								 totalServerItems: 'totalServerItems',
								 sortInfo: $scope.sortInfo,
		//						 pagingOptions: $scope.pagingOptions,
								 filterOptions: $scope.filterOptions,
								 useExternalSorting: true,
			                     showColumnMenu: true };
			_.each(['filterOptions', 'sortInfo'], function (item) {
				$scope.$watch(item, function (newVal, oldVal) {
					$log.info('Got change to ', item, newVal, oldVal);
					if (newVal !== oldVal) {
						if ($scope.sortInfo.fields.length) {
						   $scope.sort_field=$scope.sortInfo.fields[0]
						   if ($scope.sortInfo.directions[0] == 'desc') {
							   $scope.sort_field='-'+$scope.sort_field;
						   }
						}
						$scope.getPagedDataAsync($scope.page_size, 
								                 0,
								                 $scope.filterOptions.filterText,
								                 $scope.sort_field);
					}
				}, true);
			});
			
			/* 
			 * The leaflet directive code is somewhat broke in that if 
			 * bounds is specified, but set to a variable set to null, it is then 
			 * totally ignored (the watch isn't setup.)  To mitigate this, set the
			 * bounds to some reasonable value to start with, then we can change it
			 * later since the $watch is there...
			 */
			$scope.bounds={southWest: { lat: 44.81773,
				                        lng: -93.499378},
				           northEast: { lat: 45.076137,
				                        lng: -93.16212 }
						  };
				
			$scope.bounds=getBounds([-93.499378, -93.16212,
									 44.81773, 45.076137]);
			$scope.center=$scope.bounds.getCenter();
			$scope.center.zoom=4;
			
			var style=function (feature) {
				geojsonMarkerOptions = {
						    radius: 8,
						    fillColor: "#ff7800",
						    color: "#000",
						    weight: 1,
						    opacity: 1,
						    fillOpacity: 0.8
						};
				return geojsonMarkerOptions;
			}
			$scope.leaflet={'defaults': { maxZoom: 18
										},
					        'layers': {
					        		   'baselayers': { osm: { name: 'OpenStreetMap',
										                      type: 'xyz',
										                      url: 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
										                      layerOptions: {
										                         subdomains: ['a', 'b', 'c'],
										                         attribution: '© OpenStreetMap contributors',
										                         continuousWorld: true
										                      }
										                     },
								                       blank: { name: 'Blank Base Map',
									                            type: 'xyz',
									                            url: 'http://downloads2.esri.com/support/TechArticles/blank256.png',
									                            layerOptions: {
									                               continuousWorld: true
									                            }
									                          }
										        	 },
									   'overlays': { }
					        }
					        
			}
			
			var getOtherJobResults=function () {
				/*
				 * Here we need to get the results entry for this datafile - since
				 * that's where we get the job id.  Once we have the job id we 
				 * can use it to get all the results files for the job in question
				 * then we can use this to populate the list of datafiles that belong
				 * to this job.
				 */
				Restangular.all('job_results').getList({'datafile': $scope.datafile_api.id}).then(function(job_result_datafile) {
					if (job_result_datafile.length > 0) {
						var job_id=job_result_datafile[0].job.split('/').reverse()[1]
						$scope.other_datafiles=[];
						Restangular.all('job_results').getList({'job': job_id}).then(function (job_results) {
							// Get the ids of the datafiles that go with this job
							var datafile_ids=_.map(job_results, function (job_result) { return parseInt(job_result.datafile.split('/').reverse()[1]) });
							// Get all the datafiles (since we already have that in browser cache)
							// and grab those datafiles that are in the list of job files.
							$scope.rest['datafile'].then(function (datafiles) {
								_.each(datafiles, function (datafile) {
									if (_.contains(datafile_ids, datafile.id)) {
										$scope.other_datafiles.push(datafile);
									}
								});
							});
						});
					}
				});
			}
			
			// Get the information about the input file - used to determine if this
			// job has a spatial component to it and get the various URLs for data
			// display.
			var process_data=function () {
				if ($scope.datafile_api.geom_type) {
					$scope.bounds=getBounds($scope.datafile_api.bbox);
					$scope.spatial=true;
				} else {
					$scope.spatial=false;
				}
				if ($scope.datafile_api.result_field) {
					$scope.$parent.data_file_tab_name="Results";
					getOtherJobResults()
				} else {
					$scope.$parent.data_file_tab_name="Data";
				}
				$scope.getPagedDataAsync($scope.page_size, 0, '', 'nmtk_id');	
				addResultWMS();
				updateLegendGraphic();
			};
			
			
			
			
			
			// Handle the case when a user clicks on a spot on the map, we need to then
			// fire off a GetFeatureInfo requests against the WMS.
			
		     
			$scope.close=function () {
				$scope.$parent.results_uri=null;
				$location.path($scope.source_path);
			}
		}
	];
	return controller;
});

