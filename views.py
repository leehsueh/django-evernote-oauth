import sys
import time
import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.type.ttypes as Types
import evernote.edam.error.ttypes as Errors

import urllib
import urllib2
import urlparse

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect

from siteapps_v1.settings import EVERNOTE_CONSUMER_KEY as consumerKey
from siteapps_v1.settings import EVERNOTE_CONSUMER_SECRET as consumerSecret

# evernoteHost = "sandbox.evernote.com"   # change this to use production env when ready
evernoteHost = "evernote.com"
tempCredentialRequestUri = "https://" + evernoteHost + "/oauth"
resOwnerAuthUri = "https://" + evernoteHost + "/OAuth.action"
resEmbeddedParam = "?format=microclip"
resMobileParam = "?format=mobile"
tokRequestUri = tempCredentialRequestUri

userStoreUri = "https://" + evernoteHost + "/edam/user"
noteStoreUriBase = "https://" + evernoteHost + "/edam/note/"

userStoreHttpClient = THttpClient.THttpClient(userStoreUri)
userStoreProtocol = TBinaryProtocol.TBinaryProtocol(userStoreHttpClient)
userStore = UserStore.Client(userStoreProtocol)

# session keys
EVERNOTE_OAUTH_TOKEN = 'evernote_oauth_token'
EVERNOTE_EDAM_SHARD = 'evernote_edam_shard'
EVERNOTE_EDAM_USERID = 'evernote_edam_userId'

def oauth_start(request):
    """View function that begins the Evernote OAuth authentication process"""
    get_params = dict(request.GET)

    # check for callback url
    if 'callback' in get_params.keys():
        callback_url = get_params['callback'][0]
    else:
        # default to test callback URL
        callback_url = "http://" + request.get_host() + reverse('evernote_oauth:test-callback')

    # check for format of Evernote authorization page
    if 'format' in get_params.keys():
        format = get_params['format'][0]
        # check that format is either 'microclip' or 'mobile', as specified by Evernote API
        if format != 'microclip' and format != 'mobile':
            format = ''
    else:
        format = ''

    request_params = {}
    request_params['oauth_consumer_key'] = consumerKey
    request_params['oauth_signature'] = consumerSecret
    request_params['oauth_signature_method'] = 'PLAINTEXT'
    request_params['oauth_callback'] = callback_url

    timestamp = get_timestamp()
    request_params['oauth_timestamp'] = timestamp

    data = urllib.urlencode(request_params)
    req = urllib2.Request(tempCredentialRequestUri, data)
    response = urllib2.urlopen(req)

    response_params = urlparse.parse_qs(response.read())
    oauth_token = response_params['oauth_token'][0]
    oauth_callback_confirmed = response_params['oauth_callback_confirmed'][0]


    authUrl = resOwnerAuthUri + "?format=" + format + "&oauth_token=" + oauth_token
    return HttpResponseRedirect(authUrl)


def oauth_test_callback(request):
    """Test callback view"""
    if request.method == 'GET':
        credentials = parse_oauth_credentials(request)
        keys = credentials.keys()
        if 'oauth_token' in keys and 'edam_shard' in keys and 'edam_userId' in keys:
            auth_token = credentials.get('oauth_token')
            edam_shard = credentials.get('edam_shard')
            edam_userId = credentials.get('edam_userId')

            user = userStore.getUser(auth_token)

            noteStoreUri =  noteStoreUriBase + edam_shard
            noteStoreHttpClient = THttpClient.THttpClient(noteStoreUri)
            noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
            noteStore = NoteStore.Client(noteStoreProtocol)

            notebooks = noteStore.listNotebooks(auth_token)
            for notebook in notebooks:
                if notebook.defaultNotebook:
                    defaultNotebook = notebook
            
            # get notes in default notebook
            filter = NoteStore.NoteFilter()
            filter.notebookGuid = defaultNotebook.guid
            note_list = noteStore.findNotes(auth_token, filter, 0, 5)
            notes = []
            for note in note_list.notes:
                notes.append(note.title)
                
            c = {
                'notebooks': notebooks,
                'username': user.username,
                'edam_userId': edam_userId,
                'notes': notes,
            }
            return render_to_response("evernote_oauth_info.html", c,
                        context_instance=RequestContext(request))
        else:
            return HttpResponse('Missing oauth_token, edam_shard, or edam_userId')
    else:
        return HttpResponse("not a GET request..")

def redirect_oauth_start(request):
    """Utility view for redirecting user to authenticate with
    Evernote and then redirecting back to where user came from"""

    clear_evernote_oauth_session(request)
    return HttpResponseRedirect(
                reverse('evernote_oauth:oauth-start') + "?"
                + urllib.urlencode({
                        'callback': request.build_absolute_uri(request.path)
                    })
            )

def parse_oauth_credentials(request):
    """This is not a view function! It is a utility
    for parsing the oauth response to the callback
    and returning the authentication credentials"""

    params = dict(request.GET)
    if 'oauth_token' in params.keys() and 'oauth_verifier' in params.keys():
        oauth_token = request.GET.get('oauth_token')
        oauth_verifier = request.GET.get('oauth_verifier')
        request_params = {}
        request_params['oauth_consumer_key'] = consumerKey
        request_params['oauth_signature'] = consumerSecret
        request_params['oauth_signature_method'] = 'PLAINTEXT'
        request_params['oauth_token'] = oauth_token
        request_params['oauth_verifier'] = oauth_verifier
        request_params['oauth_timestamp'] = get_timestamp()

        data = urllib.urlencode(request_params)
        req = urllib2.Request(tokRequestUri, data)
        response = urllib2.urlopen(req)

        response_params = urlparse.parse_qs(response.read())
        keys = response_params.keys()
        if 'oauth_token' in keys and 'edam_shard' in keys and 'edam_userId' in keys:
            auth_token = response_params.get('oauth_token')[0]
            edam_shard = response_params.get('edam_shard')[0]
            edam_userId = response_params.get('edam_userId')[0]

            # store values in session, and set session expiration to 24 hours
            request.session[EVERNOTE_OAUTH_TOKEN] = auth_token
            request.session[EVERNOTE_EDAM_SHARD] = edam_shard
            request.session[EVERNOTE_EDAM_USERID] = edam_userId
            request.session.set_expiry(60*60*24)

            # return values as a tuple
            return {
                'oauth_token': auth_token,
                'edam_shard': edam_shard,
                'edam_userId': edam_userId
            }
        else:
            return None

    else:
        return None

def get_user_and_note_stores(edam_shard):
    userStore = get_user_store()
    noteStore = get_note_store(edam_shard)
    return (userStore, noteStore)

def get_user_store():
    userStoreHttpClient = THttpClient.THttpClient(userStoreUri)
    userStoreProtocol = TBinaryProtocol.TBinaryProtocol(userStoreHttpClient)
    userStore = UserStore.Client(userStoreProtocol)
    return userStore

def get_note_store(edam_shard):
    noteStoreUri =  noteStoreUriBase + edam_shard
    noteStoreHttpClient = THttpClient.THttpClient(noteStoreUri)
    noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
    noteStore = NoteStore.Client(noteStoreProtocol)
    return noteStore

def clear_evernote_oauth_session(request):
    """This is not a view function! It is a utility
    for clearing the session values"""
    try:
        del request.session[EVERNOTE_OAUTH_TOKEN]
        del request.session[EVERNOTE_EDAM_SHARD]
        del request.session[EVERNOTE_EDAM_USERID]
    except KeyError:
        pass

def unhandled_edam_user_exception(e):
    """e should be an instance of Errors.EDAMUserException"""
    return HttpResponse("Unhandled EDAMUserException: <ul><li>errorCode: "
                                     + e.errorCode
                                     + "</li><li>parameter: "
                                     + e.parameter 
                                     + "</li></ul>")

def get_timestamp():
    timestamp = int(round(time.time() * 1000))
    return timestamp