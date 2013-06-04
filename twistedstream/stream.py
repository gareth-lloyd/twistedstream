from urllib import quote
from oauth import oauth

from twisted.internet import defer, reactor, error
from twisted.internet.endpoints import SSL4ClientEndpoint
from twisted.internet._sslverify import OpenSSLCertificateOptions
from twisted.internet.protocol import Factory
from twisted.web._newclient import Request, HTTP11ClientProtocol
from twisted.web.http_headers import Headers
from twisted.python.failure import Failure
from twisted.python import log

from twistedstream.protocol import TwitterStreamingProtocol

STREAM_HOST = 'stream.twitter.com'
_STREAM_URL = '/1/statuses/%s.json'
FILTER = _STREAM_URL % 'filter'
SAMPLE = _STREAM_URL % 'sample'

FACTORY = Factory()
FACTORY.protocol = HTTP11ClientProtocol

ENDPOINT = SSL4ClientEndpoint(reactor, STREAM_HOST, 443,
                OpenSSLCertificateOptions(), timeout=35)
HTTP_TIMEOUT = 55

# STREAM STATES
DISCONNECTED = 0
CONNECTING = 1
CONNECTED = 2
FINISHED = 3

STATES = {
    DISCONNECTED: 'disconnected',
    CONNECTING: 'connecting',
    CONNECTED: 'connected',
    FINISHED: 'finished',
}


class Stream(object):
    """Allows a Twitter OAuth consumer to use an access token
    to connect to the Twitter Streaming API. An instance should be
    constructed with a particular consumer and token. You can then use the
    methods such as follow and track to set up long-lived connections, and
    to register functions that will be called back with parsed json objects
    received from Twitter.

    Stream is a state-machine which can be DISCONNECTED, CONNECTING,
    CONNECTED or FINISHED. An instance of Stream can only be used once
    and once it attains the FINISHED state will refuse further attempts
    to make calls.
    """
    def _state_must_be(self, new_state, *acceptable_states):
        if self.state not in acceptable_states:
            m = "Can't transition from {s1} to {s2}"\
                    .format(s1=STATES[self.state], s2=STATES[new_state])
            raise ValueError(m)

    def __init__(self, consumer, token):
        self.consumer, self.token = consumer, token

        # initial state:
        self.state = DISCONNECTED

        # state variables
        self.connected_http = None
        self.dfr_stream_connected = defer.Deferred()
        self.dfr_reached_host = None
        self.dfr_got_response = None

    def _advance_state_to(self, new_state):
        if new_state == CONNECTING:
            self._state_must_be(new_state, DISCONNECTED)
        elif new_state == CONNECTED:
            self._state_must_be(new_state, CONNECTING)
        elif new_state == FINISHED:
            self._state_must_be(new_state, FINISHED, CONNECTING, CONNECTED)
        else:
            raise ValueError('invalid state')

        self.state = new_state

    def _add_oauth_header(self, headers, http_method, url, parameters):
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer,
            token=self.token, http_method=http_method, http_url=url, parameters=parameters)
        oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), self.consumer, self.token)

        headers.update(oauth_request.to_header())

    def _build_request(self, http_method, uri, parameters):
        url = _url_from_uri(uri)
        parameters = parameters or {}
        arg_str = _urlencode(parameters)
        header_dict = {'Host': STREAM_HOST}

        if http_method == 'GET':
            url += '?' + arg_str
            body_producer = None
        else:
            header_dict['Content-Type'] = 'application/x-www-form-urlencoded'
            body_producer = StringProducer(arg_str)

        self._add_oauth_header(header_dict, http_method, url, parameters)
        headers = Headers(_format_headers(header_dict))
        return Request(http_method, uri, headers, body_producer)

    def _connect(self, uri, http_method, receiver, parameters):
        """If already connected, or in the middle of a connection attempt,
        raise error.

        Return a Deferred. A failure to connect will fire off its error
        callbacks. If we successfully start consuming the response from
        Twitter, we fire it with no arguments.
        """
        self._advance_state_to(CONNECTING)

        def connection_failed(reason):
            log.err(reason, 'connection failed %s' % reason)
            self.dfr_stream_connected.errback(reason)
            self._advance_state_to(FINISHED)

        def got_response(response):
            """Called with the HTTP response object.
            """
            if response.code == 200:
                self._advance_state_to(CONNECTED)
                response.deliverBody(TwitterStreamingProtocol(receiver, self))
                self.dfr_stream_connected.callback(None)
            else:
                connection_failed(Failure(response.code))

        def protocol_connected(connected_http_protocol):
            """Use the protocol to kick off the API request, and add
            callbacks to the resulting deferred.
            """
            self.connected_http = connected_http_protocol
            request = self._build_request(http_method, uri, parameters)
            self.dfr_got_response = self.connected_http.request(request)
            self.dfr_got_response.addCallbacks(got_response, connection_failed)

            def timeout_if_unsuccessful(deferred):
                if not deferred.called:
                    deferred.cancel()
            reactor.callLater(HTTP_TIMEOUT, timeout_if_unsuccessful, 
                    self.dfr_got_response)

        self.dfr_reached_host = ENDPOINT.connect(FACTORY)
        self.dfr_reached_host.addCallbacks(protocol_connected, connection_failed)
        return self.dfr_stream_connected

    def disconnect(self, reason=None):
        """Transition to a finished state. Attempt to do so cleanly...
        """
        if self.connected_http is not None:
            if reason is None:
                self.connected_http.abort()
            else:
                self.connected_http._giveUp(reason)

        if self.dfr_reached_host and not self.dfr_reached_host.called:
            self.dfr_reached_host.cancel()

        if self.dfr_got_response and not self.dfr_got_response.called:
            self.dfr_got_response.cancel()

        if not self.dfr_stream_connected.called:
            self.dfr_stream_connected.errback(Failure(
                    error.ConnectionDone('disconnected')))

        self._advance_state_to(FINISHED)

    def sample(self, receiver, parameters=None):
        """Receive ~1% of all twitter statuses. 'receiver' must
        implement  twistedstream.protocol.IStreamReceiver
        """
        return self._connect(SAMPLE, 'GET', receiver, parameters)

    def filter(self, receiver, parameters=None):
        """Filter twitter statuses according to parameters. 'receiver'
        must implement twistedstream.protocol.IStreamReceiver
        """
        return self._connect(FILTER, 'POST', receiver, parameters)

    def follow(self, receiver, follows):
        """Follow a list of twitter users. 'receiver' must implement
        twistedstream.protocol.IStreamReceiver
        """
        return self.filter(receiver, {'follow': ','.join(follows)})

    def track(self, receiver, terms):
        """Track a list of search terms. 'receiver' must implement
        twistedstream.protocol.IStreamReceiver
        """
        for term in terms:
            if len(term) > 60:
                raise ValueError('Terms must be 60 chars or fewer in length.')
        return self.filter(receiver, {'track': ','.join(terms)})


def _url_from_uri(uri):
    return 'https://' + STREAM_HOST + uri

def _urlencode(headers):
    encoded = []
    for key, value in headers.iteritems():
        encoded.append("%s=%s" %
            (quote(key.encode("utf-8")),
            quote(value.encode("utf-8"), safe='')))
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

