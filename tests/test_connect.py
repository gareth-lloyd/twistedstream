import unittest
from mock import Mock, patch
from oauth import oauth

from twisted.internet import defer
from twisted.web._newclient import HTTP11ClientProtocol
from twisted.python.failure import Failure

from twistedstream import Stream
from twistedstream.stream import (CONNECTING, BACKING_OFF,
        CONNECTED, DISCONNECTED)


class TestReceiver(object):
    disconnected = False
    def json(self, obj):
        pass
    def disconnected(self, reason):
        self.disconnected = True

class ConnectTest(unittest.TestCase):

    def setUp(self):
        consumer = Mock(spec=oauth.OAuthConsumer)
        consumer.secret = 'abc'
        token = Mock(spec=oauth.OAuthToken)
        token.secret = 'abc'
        self.stream = Stream(consumer, token)

    @patch('twistedstream.stream.ENDPOINT')
    def test_connection_error(self, mock_endpoint):
        "should back off linearly after network error"
        endpoint_connect_dfr = defer.Deferred()
        mock_endpoint.connect.return_value = endpoint_connect_dfr

        d = self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)

        # simulate a network error
        endpoint_connect_dfr.errback(Failure(''))
        self.assertEquals(BACKING_OFF, self.stream.state)
        self.assertEquals(2, self.stream.next_backoff)

    @patch('twistedstream.stream.ENDPOINT')
    def test_recoverable_http_error(self, mock_endpoint):
        "should back off exponentially after recoverable http error"
        # to test exponential backoff, start at a higher backoff
        self.stream.next_backoff = 10

        endpoint_connect_dfr = defer.Deferred()
        mock_endpoint.connect.return_value = endpoint_connect_dfr

        d = self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)

        # simulate a successful connection
        mock_http_protocol = Mock(spec=HTTP11ClientProtocol)
        http_request_dfr = defer.Deferred()
        mock_http_protocol.request.return_value = http_request_dfr
        endpoint_connect_dfr.callback(mock_http_protocol)

        # simulate unsuccessful http request
        self.assertEquals(CONNECTING, self.stream.state)
        mock_http_response = Mock()
        mock_http_response.code = 500
        http_request_dfr.callback(mock_http_response)

        self.assertEquals(BACKING_OFF, self.stream.state)
        self.assertEquals(20, self.stream.next_backoff)

    @patch('twistedstream.stream.ENDPOINT')
    def test_unrecoverable_http_error(self, mock_endpoint):
        "should back off exponentially after recoverable http error"
        # to test exponential backoff, start at a higher backoff
        self.stream.next_backoff = 10

        endpoint_connect_dfr = defer.Deferred()
        mock_endpoint.connect.return_value = endpoint_connect_dfr

        d = self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)

        # simulate a successful connection
        mock_http_protocol = Mock(spec=HTTP11ClientProtocol)
        http_request_dfr = defer.Deferred()
        mock_http_protocol.request.return_value = http_request_dfr
        endpoint_connect_dfr.callback(mock_http_protocol)

        # simulate unsuccessful http request
        self.assertEquals(CONNECTING, self.stream.state)
        mock_http_response = Mock()
        mock_http_response.code = 401
        http_request_dfr.callback(mock_http_response)

        self.assertEquals(DISCONNECTED, self.stream.state)
        self.assertEquals(-1, self.stream.next_backoff)

    @patch('twistedstream.stream.ENDPOINT')
    def test_successful_connection(self, mock_endpoint):
        "should pass http request body to TwitterStreamingProtocol"
        endpoint_connect_dfr = defer.Deferred()
        mock_endpoint.connect.return_value = endpoint_connect_dfr

        d = self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)

        # a successful connection
        mock_http_protocol = Mock(spec=HTTP11ClientProtocol)
        http_request_dfr = defer.Deferred()
        mock_http_protocol.request.return_value = http_request_dfr
        endpoint_connect_dfr.callback(mock_http_protocol)

        # simulate successful http request
        self.assertEquals(CONNECTING, self.stream.state)
        mock_http_response = Mock()
        mock_http_response.code = 200
        mock_http_response.deliverBody = Mock()
        http_request_dfr.callback(mock_http_response)

        self.assertEquals(CONNECTED, self.stream.state)
        self.assertTrue(mock_http_response.deliverBody.called)

    def test_connection_cancelled(self):
        pass

    def test_connection_cancelled_after_host_connect(self):
        pass

    def test_connect_while_backing_off(self):
        pass
    def test_connect_while_connected(self):
        pass
