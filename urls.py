from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # when invoking this url, specify a 'callback' GET param containing the callback url
    # optionally specify a 'format' GET param, corresponding to what format the Evernote authorization you want ('microclip' or 'mobile')
    url(r'^$',
        'siteapps_v1.evernote_oauth.views.oauth_start',
        name='oauth-start'
    ),

    url(r'^callback/$',
        'siteapps_v1.evernote_oauth.views.oauth_test_callback',
        name='test-callback'
    ),
)
