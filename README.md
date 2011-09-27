Dependencies
============

* Evernote Python API SDK (download from http://www.evernote.com/about/developer/api/)
* Django sessions framework configured and enabled in settings.py

Setup
-----

* make sure the evernote/thrift python libraries are added to your python installation's site-packages directory
* place the evernote_oauth dir either in your django project or somewhere accessible on your python path (if placing inside your project dir, you'll need to reference it by prefixing your project's name in import statements)
* in your settings.py file, add evernote_oauth as an installed app
* in your project's top level url.py file, add a url pattern line to include evernote_oauth.urls, specifying a namespace and app name. Example:
	(r'^evernote/oauth/', include('evernote_oauth.urls', namespace='evernote_oauth', app_name='evernote_oauth'))
* open evernote_oauth/views.py and change the consumerKey and consumerSecret to the values you received from Evernote when requesting an API key

Usage Instructions
------------------

NOTE: Integration may not be the most elegant, but for now it works.

* In your views file, import from the evernote_oauth views the following as needed:
	- view functions and utility functions
		- parse_oauth_credentials
		- redirect_oauth_start
		- get_user_store
		- get_note_store
		- get_user_and_note_stores
		- unhandled_edam_user_exception
	- session key constants
		- EVERNOTE_OAUTH_TOKEN
		- EVERNOTE_EDAM_SHARD
		- EVERNOTE_EDAM_USERID
* Perform a check to determine whether evernote authentication (or reauthentication) is required (e.g. by examining session variables, checking the session expiry age, or trying to invoke the evernote service and handling an authentication expired exception).
* If authentication is not needed, proceed with your application view logic. 
* Otherwise, return redirect_oauth_start(request)
	- this will automatically redirect the user to authenticate with Evernote, and Evernote will use the value of request.build_absolute_uri(request.path) as the callback URL
	- your view function, to handle the callback invoked by Evernote, needs to invoke the parse_oauth_credentials method, which will store the authentication token, shard ID, and user ID as django session variables, indexed by the session key constants. After the call to parse_oauth_credentials, most likely you'll want to redirect the user once more to request.build_absolute_uri(request.path), and this time, your application view logic will be performed
	- in summary, your view function will be invoked 3 times: first by the user requesting it, second by Evernote as a callback with authentication parameters, and third by the view itself after the authentication parameters are stored in the session (this third redirect is performed in order to clear the authentication token from the address bar)
* Alternatively, if you want different callback/redirect behavior, you can redirect to reverse('evernote_oauth:oauth-start') directly, but remember to specify an absolute callback URL as a 'callback' GET parameter. To simply test evernote authentication, you can leave out the 'callback' GET parameter and it will redirect to a test callback view function which renders a template displaying sample information from the authenticated evernote account

Usage Example
-------------
	from myproject.evernote_oauth.views import parse_oauth_credentials, redirect_oauth_start, get_user_store, get_note_store, get_user_and_note_stores, unhandled_edam_user_exception
	from myproject.evernote_oauth.views import EVERNOTE_OAUTH_TOKEN, EVERNOTE_EDAM_SHARD, EVERNOTE_EDAM_USERID
	...
	...

	def example_view(request):
		# determine if authentication is needed
	    if request.session.get(EVERNOTE_OAUTH_TOKEN, False) and request.session.get(EVERNOTE_EDAM_SHARD, False) and request.session.get(EVERNOTE_EDAM_USERID, False):
	        auth_token = request.session.get(EVERNOTE_OAUTH_TOKEN)
	        edam_shard = request.session.get(EVERNOTE_EDAM_SHARD)
	        edam_userId = request.session.get(EVERNOTE_EDAM_USERID)

	        try:
	            userStore, noteStore = get_user_and_note_stores(edam_shard)
	            ...
	            ...
	        except Errors.EDAMUserException as e:
	            if e.errorCode == Errors.EDAMErrorCode.AUTH_EXPIRED:
	                # authentication token expired; re-initiate oauth process
	                return redirect_oauth_start(request)
	            else:
	                return unhandled_edam_user_exception(e)
	    else:
	        # request is either a callback invoked by evernote, or invoked by user to initiate evernote oauth
	        credentials = parse_oauth_credentials(request)
	        if credentials:
	            # authentication has been done; callback invoked by Evernote
	            # values stored in session
	            return HttpResponseRedirect(request.build_absolute_uri(request.path))
	        else:
	            # authentication has not been done; initiate oauth process
	            return redirect_oauth_start(request)