from urllib import quote
from oauth import oauth

from twisted.internet.endpoints import SSL4ClientEndpoint
from twisted.internet._sslverify import OpenSSLCertificateOptions
from twisted.internet import defer, reactor
from twisted.internet.protocol import Factory

from twisted.web._newclient import Request, HTTP11ClientProtocol
from twisted.web import error
from twisted.web.http_headers import Headers

from twisted.python import log

from protocol import TwitterStreamingProtocol

STREAM_HOST= 'stream.twitter.com'
_STREAM_URL = '/1/statuses/%s.json'
FILTER = _STREAM_URL % 'filter'
SAMPLE = _STREAM_URL % 'sample'

# STREAM STATES
DISCONNECTED = 0
CONNECTING = 1
CONNECTED = 2
BACKING_OFF = 4

class Stream(object):
    """Methods to enable a Twitter OAuth consumer to use an access token
    to connect to the Twitter Streaming API. An instance should be
    constructed with a particular consumer and token. You can then use the
    methods such as follow and track to set up long-lived connections, and
    to register functions that will be called back with parsed json objects
    received from Twitter.
    """

    def __init__(self, consumer, token, timeout=60):
        self._state = DISCONNECTED

        self.timeout = timeout
        self.consumer = consumer
        self.token = token

        self.http_protocol_factory = Factory()
        self.http_protocol_factory.protocol = HTTP11ClientProtocol
        self.current_http_protocol = None
        self.current_streaming_protocol = None
        self.twitter_streaming_endpoint = SSL4ClientEndpoint(reactor,
                STREAM_HOST, 443, OpenSSLCertificateOptions())

    def _make_oauth1_headers(self, http_method, url, parameters={}, headers={}):
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer,
            token=self.token, http_method=http_method, http_url=url, parameters=parameters)
        oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), self.consumer, self.token)

        headers.update(oauth_request.to_header())
        return headers

    def _build_request(self, http_method, uri, parameters):
        url = _api_url(uri)
        parameters = parameters or {}
        arg_str = _urlencode(parameters)
        headers = {'Host': STREAM_HOST}
        if http_method == 'GET':
            url += '?' + arg_str
            body_producer = None
        else:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            body_producer = StringProducer(arg_str)

        headers_with_auth = self._add_oauth_header(http_method, url, 
                parameters, headers)
        headers = Headers(_format_headers(headers_with_auth))
        return Request(http_method, uri, headers, body_producer)

    def _connect(self, uri, http_method, status_receiver, parameters):
        """
        Set up callbacks which will connect to the Twitter Streaming API
        endpoint using the HTTP protocol and then hand off the body data
        to our own Twitter protocol.

        Return a Deferred which will be fired if we start streaming,
        successfully or errored if we cannot.
        """
        stream_deferred = defer.Deferred()
        if self._state != DISCONNECTED:
            raise ValueError
        else:
            self._state = CONNECTING

        def response_received(response):
            """Called by HTTP11ClientProtocol with the response object
            when response headers have been processed and we're ready
            to start consuming the body. We do this using a new instance
            of TwitterStreamingProtocol
            """
            if response.code == 200:
                self.current_streaming_protocol = TwitterStreamingProtocol(status_receiver)
                response.deliverBody(self.current_streaming_protocol)
                self._state = CONNECTED
                stream_deferred.callback(None)
            else:
                self.disconnect()
                stream_deferred.errback(error.Error(response.code, response.phrase))

        def protocol_connected(protocol):
            """Called with a connected HTTP11ClientProtocol produced by
            self.http_protocol_factory. Use the protocol to make a Twitter
            API request.
            """
            self.current_http_protocol = protocol

            request = self._build_request(http_method, uri, parameters)
            deferred = self.current_http_protocol.request(request)
            deferred.addCallbacks(response_received, log.err)
            return protocol

        endpoint_deferred = self.twitter_streaming_endpoint.connect(self.http_protocol_factory)
        endpoint_deferred.addCallbacks(protocol_connected, log.err)

        return stream_deferred

    def disconnect(self):
        if self._state != DISCONNECTED and self.current_http_protocol is not None:
            self.current_http_protocol._giveUp(None)
            self.current_http_protocol = None
            self.current_streaming_protocol = None
            self._state = DISCONNECTED

    def filter(self, status_receiver, parameters=None):
        return self._connect(FILTER, 'POST', status_receiver, parameters)

    def follow(self, status_receiver, follow):
        return self.filter(status_receiver, {'follow': ','.join(follow)})

    def track(self, status_receiver, terms):
        return self.filter(status_receiver, {'track': ','.join(terms)})

def _urlencode(headers):
    encoded = []
    for key, value in headers.iteritems():
        encoded.append("%s=%s" %
            (quote(key.encode("utf-8")),
            quote(value.encode("utf-8"))))
    return '&'.join(encoded)

def _format_headers(headers):
    return dict([(name, [value]) for name, value in headers.iteritems()])

def _api_url(uri):
    return 'https://' + STREAM_HOST + uri

class StringProducer(object):
    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

