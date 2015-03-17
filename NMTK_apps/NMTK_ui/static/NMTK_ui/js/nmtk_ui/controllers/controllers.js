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
/*
 * Chander Ganesan, 2013 (chander@otg-nc.com)
 * Controller loader for NMTK UI components, here is where
 * all the controllers should be referenced so that other
 * NMTK components can load them easily.
 */

define([
  // Standard Libs
  'underscore' // lib/underscore/underscore
  , 'nmtk_ui/controllers/NMTKCtrl' // Application Controller
  , 'nmtk_ui/controllers/SwitchJobCtrl' // Application Controller
  , 'nmtk_ui/controllers/ChangePasswordCtrl' // Controller to handle password changes
  , 'nmtk_ui/controllers/CloneConfigCtrl' // Modal dialog for cloning configuration
  , 'nmtk_ui/controllers/ConfigureCtrl' // Job configuration controller
  , 'nmtk_ui/controllers/CreateJobCtrl' // Controller for creating a new job
  , 'nmtk_ui/controllers/DeleteCtrl' // Ack modal for deleting a job
  , 'nmtk_ui/controllers/DownloadDatafileCtrl' // Modal Controller to download job(s) NOT USED?
  , 'nmtk_ui/controllers/FeedbackCtrl' // Grouse facility controller
  , 'nmtk_ui/controllers/FileInfoUpdateCtrl' // Controller for file information update (modal)
  , 'nmtk_ui/controllers/FilesCtrl' // Controller for file management page
  , 'nmtk_ui/controllers/IntroCtrl' // Main/intro page controller
  , 'nmtk_ui/controllers/JobCtrl' // Controller for Job management page
  , 'nmtk_ui/controllers/ToolExplorerCtrl' // Controller for Tool explorer page
  , 'nmtk_ui/controllers/ViewJobCtrl' // Controller for Viewing Job data (modal)
  , 'nmtk_ui/controllers/ViewDatafileCtrl' // Controller handling the view results page(s)
  , 'nmtk_ui/controllers/AdvancedFiltersCtrl' // Controller for managing Advanced filters
  , 'nmtk_ui/controllers/ColorRampSelectionCtrl' // Controller for managing Advanced filters
  , 'nmtk_ui/controllers/LoginCtrl' // Controller handling the user login process
  , 'nmtk_ui/controllers/JobStatusHistoryCtrl' // Controller handling the display of job status history
  , 'nmtk_ui/controllers/DeleteJobCtrl' // Controller handling the deletion of jobs
], function ( _, NMTKCtrl, SwitchJobCtrl, 
		ChangePasswordCtrl, CloneConfigCtrl, ConfigureCtrl,
		CreateJobCtrl, DeleteCtrl, DownloadDatafileCtrl, FeedbackCtrl,
		FileInfoUpdateCtrl, FilesCtrl, IntroCtrl, JobCtrl,
		ToolExplorerCtrl, ViewJobCtrl, ViewDatafileCtrl, AdvancedFiltersCtrl,
		ColorRampSelectionCtrl, LoginCtrl, JobStatusHistoryCtrl, DeleteJobCtrl
			 ) {
  "use strict";
  var controllers = {
	"NMTKCtrl": NMTKCtrl
	, "SwitchJobCtrl": SwitchJobCtrl
	, "ChangePasswordCtrl": ChangePasswordCtrl
	, "CloneConfigCtrl": CloneConfigCtrl
	, "ConfigureCtrl": ConfigureCtrl
	, "CreateJobCtrl": CreateJobCtrl
	, "DeleteCtrl": DeleteCtrl
	, "DownloadDatafileCtrl": DownloadDatafileCtrl
	, "FeedbackCtrl": FeedbackCtrl
	, "FileInfoUpdateCtrl": FileInfoUpdateCtrl
	, "FilesCtrl": FilesCtrl
	, "IntroCtrl": IntroCtrl
	, "JobCtrl": JobCtrl
	, "ToolExplorerCtrl": ToolExplorerCtrl
	, "ViewJobCtrl": ViewJobCtrl
	, "ViewDatafileCtrl": ViewDatafileCtrl
	, "LoginCtrl": LoginCtrl
	, "AdvancedFiltersCtrl": AdvancedFiltersCtrl
	, "ColorRampSelectionCtrl": ColorRampSelectionCtrl
	, "JobStatusHistoryCtrl": JobStatusHistoryCtrl
	, "DeleteJobCtrl": DeleteJobCtrl
  };
  
  var initialize = function(angModule) {
    // Register all the controllers we are using here.
    _.each(controllers,function(controller,name){
      angModule.controller(name, controller);
    })
  };

  return {
    initialize: initialize
  };
});