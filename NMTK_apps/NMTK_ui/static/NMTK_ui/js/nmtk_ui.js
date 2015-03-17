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
"use strict";
require.config({
	paths: {
		/* The two items below are for IE backwards compatibility. */
		"json2": "lib/json2" // Create a JSON object if one does not exist.
		, "html5shiv": "lib/html5shiv" // For IE 8 and earlier, this adds some HTML5 elements
		/* End IE backwards compatibility components */
		/* Required for the blueimp jquery file uploader (drag and drop file upload) */
		, "jquery": "lib/jquery" // Used for the file upload drag-and-drop stuff - and nothing else.
		, "jquery.ui.widget": "lib/jquery.ui.widget" // UI Widget needed for file upload
		, "jquery-iframe-transport": "lib/jquery.iframe-transport" // Used for file upload
		, "angular-elastic": "lib/angular-elastic" // Used for auto-resize of textarea fields
		, "jquery-fileupload": "lib/jquery.fileupload" // Used for file upload
		/* End drag-and-drop upload required files */
		, "browserdetect": "lib/browserdetect" // Might not be needed - detect browser version
		, "underscore": "lib/underscore" // Underscore.js
		, "text": "lib/text" // Requirejs Text loading plugin (for templates)
		, "domReady": "lib/domReady" // requirejs - test if the Dom is ready
		, "angular": "lib/angular" // Angular JS 
		, "angular-bootstrap": "lib/ui-bootstrap-tpls" // Bootstrap for angular, with templates
		, "bootstrap-slider": "lib/bootstrap-slider" // Bootstrap for angular, with templates
		, "ng-grid": "lib/ng-grid" // Angular Grid library (for gridded tables)
		, "restangular": "lib/restangular" // REST Support for AngularJS
		, "angular-leaflet": "lib/angular-leaflet-directive" // Directive to angularlize leaflet
		, "leaflet": "lib/leaflet" // Library for the map UI stuff
		, "respond": "lib/respond" // Respond js
		, "ng-grid-flexible-height": "lib/ng-grid-flexible-height" // Flexi-height plugin for grid
		, "ng-grid-layout": "lib/ng-grid-layout" // Rebuild columns when a column changes.
		, "nmtk_ui_app": "nmtk_ui/nmtk_ui_app" // The NMTK UI components
		/* Templates used for page rendering */
		, "changePasswordTemplate": "../templates/changepassword.html" // Template to change password
		, "configureTemplate": "../templates/configure.html" // template related to job configuration
		, "createJobTemplate": "../templates/create_job_modal.html" // modal template related to creating new jobs
		, "deleteModalTemplate": "../templates/delete_modal.html" // Delete dialog modal template
		, "deleteJobModalTemplate": "../templates/delete_job_modal.html" // Delete job dialog modal template
		, "downloadDatafileTemplate": "../templates/downloaddatafile.html" // Download job dialog
		, "feedbackTemplate": "../templates/feedback.html" // Grouse/Feedback dialog
		, "filesTemplate": "../templates/files.html" // Template for managing job files
		, "introTemplate": "../templates/intro.html" // Template for introduction page
		, "jobTemplate": "../templates/job.html" // Template for job management page
		, "pagerTemplate": "../templates/pager.html" // Template for the pager
		, "passwordChangeStatusModalTemplate": "../templates/password_change_status_modal.html" // Status of password change
		, "resultsTemplate": "../templates/results.html" // Results viewing template
		, "explorerTemplate": "../templates/tool_explorer.html" // Explorer template
		, "loginTemplate": "../templates/login.html" // Login template
		, "fileInfoTemplate": "../templates/file_info.html" // Login template
		, "fileActionsCellTemplate": "../templates/file_actions_cell.html" // Template for ng-grid file actions
		, "jobActionsCellTemplate": "../templates/job_actions_cell.html" // Template for ng-grid job actions
		, "jobStatusCellTemplate": "../templates/job_status_cell.html" // Template for ng-grid job actions
		, "jobDescriptionCellTemplate": "../templates/job_description_cell.html" // Template for ng-grid job actions
		, "viewJobModalTemplate": "../templates/view_job_modal.html" // Template for ng-grid file actions
		, "switchJobModalTemplate": "../templates/switch_job_modal.html" // Template for ng-grid job actions
		, "configureErrorsServerTemplate": "../templates/configure_errors_server_modal.html" //Template for configuration error messages
		, "configureErrorsClientTemplate": "../templates/configure_errors_client_modal.html" //Template for configuration error messages
		, "cloneConfigTemplate": "../templates/clone_config_modal.html" // Template for config page to clone config.
		, "AdvancedFiltersTemplate": "../templates/advanced_filters_modal.html" // Template for the advanced filters modal.
		, "ColorRampSelectionTemplate": "../templates/wms_colorramp_selection_modal.html" // Template for choosing a color ramp.
		, "JobStatusHistoryTemplate": "../templates/job_status_history_modal.html" // Template for job status history

	}
	, shim: {
	    "underscore": { exports: '_' }
		, "leaflet": { exports: 'L' }
	    , "angular": { exports: 'angular',
	    	           deps: ['jquery']} // Note: Jquery must load first so we don't use jqlite
	    , "jquery.ui.widget": ["jquery"]
	    , "jquery-iframe-transport": ["jquery", "jquery-fileupload",
	                                  "jquery.ui.widget"]
	    , "jquery-fileupload": ["jquery", "jquery.ui.widget"]
	    , "angular-leaflet": ["angular", "leaflet"]
	    , "angular-elastic": ["angular"]
	    , "restangular": ["angular"]
	    , "ng-grid": ["angular", "ng-grid-flexible-height", "ng-grid-layout"]
	    , "angular-bootstrap": ["angular"]
	    , "bootstrap-slider": ["angular", "angular-bootstrap"]
	    , "jquery": { exports: '$' }
	}

	// Allow an update of version to cause cache updates in the browser.
	// TODO: Remove the "bust" part of this before release - it's for
	//       DEBUG only and forces a reload of all libs on each reload
	//urlArgs: 'v=1.0' + "bust=" +  (new Date()).getTime()
	, urlArgs: 'v=1.1' 
});


// Bootstrap the NMTK_ui Application now.
// Note that jquery, html5shiv, json2, etc. load into the global
// scope so we need only require them here to make sure they are loaded.
// then we need not ever call them again...
require(['require', 'jquery','html5shiv','json2',
         'jquery.ui.widget','jquery-fileupload','respond',
         'jquery-iframe-transport', 'browserdetect', 
         'ng-grid-flexible-height', 'ng-grid-layout'], 
     function (require) {	
  	    require(['nmtk_ui_app'], function (nmtk_ui_app) {
  	    	nmtk_ui_app.initialize();
	  	});
});
