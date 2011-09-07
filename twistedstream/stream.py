from urllib import quote
from oauth import oauth

from twisted.internet import defer, reactor, error
from twisted.internet.endpoints import SSL4ClientEndpoint
from twisted.internet._sslverify import OpenSSLCertificateOptions
from twisted.internet.protocol import Factory
from twisted.internet.defer import AlreadyCalledError, CancelledError

from twisted.web._newclient import Request, HTTP11ClientProtocol
from twisted.web.http_headers import Headers

from twisted.python.failure import Failure
from twisted.python import log

from protocol import TwitterStreamingProtocol

STREAM_HOST= 'stream.twitter.com'
_STREAM_URL = '/1/statuses/%s.json'
FILTER = _STREAM_URL % 'filter'
SAMPLE = _STREAM_URL % 'sample'

def _api_url(uri):
    return 'https://' + STREAM_HOST + uri

FACTORY = Factory()
FACTORY.protocol = HTTP11ClientProtocol

ENDPOINT = SSL4ClientEndpoint(reactor, STREAM_HOST, 443,
                OpenSSLCertificateOptions())

MAX_BACKOFF = 240

# STREAM STATES
DISCONNECTED = 0
CONNECTING = 1
CONNECTED = 2
BACKING_OFF = 4

def _state_must_be(current_state, *acceptable_states):
    if current_state not in acceptable_states:
        raise ValueError('Invalid State transition')

class Stream(object):
    """Methods to enable a Twitter OAuth consumer to use an access token
    to connect to the Twitter Streaming API. An instance should be
    constructed with a particular consumer and token. You can then use the
    methods such as follow and track to set up long-lived connections, and
    to register functions that will be called back with parsed json objects
    received from Twitter.

    Stream is a state-machine which can be DISCONNECTED, CONNECTING, 
    BACKING_OFF or CONNECTED
    """

    def __init__(self, consumer, token):
        self.consumer, self.token = consumer, token

        # initial state:
        self.state = DISCONNECTED
        self.next_backoff = 1
        self.connected_http = None
        self.dfr_stream_connected = None
        self.dfr_reached_host = None
        self.dfr_got_response = None

    def _advance_state_to(self, new_state):
        if new_state == DISCONNECTED:
            pass
        elif new_state == CONNECTING:
            _state_must_be(self.state, DISCONNECTED, BACKING_OFF)
        elif new_state == CONNECTED:
            _state_must_be(self.state, CONNECTING)
        elif new_state == BACKING_OFF:
            _state_must_be(self.state, CONNECTING)
        else:
            raise ValueError('Invalid state')
        self.state = new_state

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
        """If already connected, or in the middle of a connection attempt,
        disconnect. This will cancel any outstanding Deferreds.

        Attempt to connect, immediately if this is the first try, or
        after a backoff period.

        We return a Deferred. A failure to connect, even after backing off,
        will will fire off its error callbacks. If we successfully start 
        consuming the response from Twitter, we fire it with no arguments.
        """
        if self.state in (CONNECTING, CONNECTED):
            self.disconnect()

        if self.dfr_stream_connected is None:
            self.dfr_stream_connected = defer.Deferred()

        if self.state == BACKING_OFF:
            reactor.callLater(self.next_backoff, self._do_connect, uri, 
                    http_method, receiver, parameters)
        else:
            self._do_connect(uri, http_method, receiver, parameters)

        return self.dfr_stream_connected

    def _do_connect(self, uri, http_method, receiver, parameters):
        """
        Set up callbacks which will connect to the Twitter Streaming API
        endpoint. There are two stages to the connection process - first we
        attempt to connect to the host, and then send a signed HTTP request.
        The response to this request is passed to an instance of
        TwitterStreamingProtocol.
        """

        self._advance_state_to(CONNECTING)

        def connection_failed(reason):
            log.err(reason, 'Failed connecting to stream')
            if reason.type == int:
                # received a status code > 200
                status_code = reason.value
                # recoverable?
            if self.next_backoff >= MAX_BACKOFF:
                self.dfr_stream_connected.errback(reason)
                self.disconnect() # TODO reason
                return

            self.next_backoff = self._next_backoff(reason)
            log.msg('Backing off %ss' % self.next_backoff)
            self._advance_state_to(BACKING_OFF)
            self._connect(uri, http_method, receiver, parameters)

        def got_response(response):
            """Called with the HTTP response object
            """
            if response.code == 200:
                response.deliverBody(TwitterStreamingProtocol(receiver))
                self._advance_state_to(CONNECTED)
                self.dfr_stream_connected.callback(None)
            else:
                connection_failed(Failure(response.code))

        def protocol_connected(protocol):
            """Called with a connected HTTP11ClientProtocol. We use
            it to kick off the API request.
            """
            self.connected_http = protocol
            request = self._build_request(http_method, uri, parameters)
            self.dfr_got_response = self.connected_http.request(request)
            self.dfr_got_response.addCallbacks(got_response, connection_failed)
            return protocol

        self.dfr_reached_host = ENDPOINT.connect(FACTORY)
        self.dfr_reached_host.addCallbacks(protocol_connected, connection_failed)
        return self.dfr_stream_connected

    def _next_backoff(self, reason):
        return self.next_backoff * 2

    def disconnect(self, reason=None):
        """Return the Stream to a disconnected state regardless
        of current state. Attempt to do so cleanly...
        """
        if self.connected_http is not None:
            if reason is None:
                reason = Failure(error.ConnectionDone('Done listening'))
            self.connected_http._giveUp(reason)
            self.connected_http = None

        if self.dfr_reached_host is not None:
            self.dfr_reached_host.cancel()
            self.dfr_reached_host = None

        if self.dfr_got_response is not None:
            self.dfr_got_response.cancel()
            self.dfr_got_response = None

        if self.dfr_stream_connected is not None:
            try:
                self.dfr_stream_connected.errback(
                    Failure(error.ConnectionDone('disconnected')))
            except (AlreadyCalledError, CancelledError):
                pass
            self.dfr_stream_connected = None
        self._advance_state_to(DISCONNECTED)

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

