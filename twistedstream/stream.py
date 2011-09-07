from urllib import quote
from oauth import oauth

from twisted.internet.endpoints import SSL4ClientEndpoint
from twisted.internet._sslverify import OpenSSLCertificateOptions
from twisted.internet import defer, reactor
from twisted.internet.protocol import Factory

from twisted.web._newclient import Request, HTTP11ClientProtocol
from twisted.web import error
from twisted.web.http_headers import Headers

from twisted.python import failure

from protocol import TwitterStreamingProtocol

STREAM_HOST= 'stream.twitter.com'
_STREAM_URL = '/1/statuses/%s.json'
FILTER = _STREAM_URL % 'filter'
SAMPLE = _STREAM_URL % 'sample'

def _api_url(uri):
    return 'https://' + STREAM_HOST + uri

ENDPOINT = SSL4ClientEndpoint(reactor,
        STREAM_HOST, 443, OpenSSLCertificateOptions())
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
        self.state = DISCONNECTED

        self.timeout = timeout
        self.consumer = consumer
        self.token = token

        self.http_factory = Factory()
        self.http_factory.protocol = HTTP11ClientProtocol
        self.current_http_protocol = None
        self.current_protocol = None

    def _advance_state_to(self, new_state):
        pass

    def _add_oauth_header(self, http_method, url, parameters={}, headers={}):
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

    def _connect(self, uri, http_method, receiver, parameters):
        """
        Set up callbacks which will connect to the Twitter Streaming API
        endpoint. There are two stages to the connection process - first we
        attempt to connect to the host, and then send a signed HTTP request.
        The response to this request is passed to an instance of
        TwitterStreamingProtocol.

        We return a Deferred. A failure at either stage will fire off its
        error callbacks. If we successfully start consuming the response
        from Twitter, we fire it with no arguments.
        """
        stream_deferred = defer.Deferred()
        if self.state != CONNECTING:
            self.disconnect()
        else:
            # is there a way to hook into previous deferred?
            return 

        def connection_error(failure):
            stream_deferred.errback(failure)

        def response_received(response):
            """Called with the HTTP response object
            """
            if response.code == 200:
                self.current_protocol = TwitterStreamingProtocol(receiver)
                self.current_protocol.deferred.addBoth(self.disconnect)

                response.deliverBody(self.current_protocol)
                self.state = CONNECTED
                stream_deferred.callback(None)
            else:
                self.disconnect(failure.Failure(error.ConnectionRefusedError()))
                stream_deferred.errback(failure.Failure(response.code))

        def protocol_connected(protocol):
            """Called with a connected HTTP11ClientProtocol.
            """
            # keep a reference to the protocol instance
            self.current_http_protocol = protocol

            # kick off the API request
            request = self._build_request(http_method, uri, parameters)
            deferred = self.current_http_protocol.request(request)
            deferred.addCallbacks(response_received, connection_error)
            return protocol

        self.state = CONNECTING
        endpoint_deferred = ENDPOINT.connect(self.http_factory)
        endpoint_deferred.addCallbacks(protocol_connected, connection_error)

        return stream_deferred

    def disconnect(self, reason=None):
        if self.current_http_protocol is not None:
            if reason is None:
                reason = failure.Failure(error.ConnectionDone('Done listening'))
            self.current_http_protocol._giveUp(reason)
            self.current_http_protocol = None
            self.current_protocol = None
        self.state = DISCONNECTED

    def sample(self, receiver, parameters=None):
        return self._connect(SAMPLE, 'GET', receiver, parameters)

    def filter(self, receiver, parameters=None):
        return self._connect(FILTER, 'POST', receiver, parameters)

    def follow(self, receiver, follow):
        return self.filter(receiver, {'follow': ','.join(follow)})

    def track(self, receiver, terms):
        return self.filter(receiver, {'track': ','.join(terms)})

def _urlencode(headers):
    encoded = []
    for key, value in headers.iteritems():
        encoded.append("%s=%s" %
            (quote(key.encode("utf-8")),
            quote(value.encode("utf-8"))))
    return '&'.join(encoded)

def _format_headers(headers):
    return dict([(name, [value]) for name, value in headers.iteritems()])


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

