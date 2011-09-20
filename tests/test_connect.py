import unittest
from mock import Mock, patch
from oauth import oauth

from twisted.internet import defer
from twisted.internet import reactor
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

@patch('twistedstream.stream.ENDPOINT')
class ConnectTest(unittest.TestCase):

    def setUp(self):
        consumer = Mock(spec=oauth.OAuthConsumer)
        consumer.secret = 'abc'
        token = Mock(spec=oauth.OAuthToken)
        token.secret = 'abc'
        self.stream = Stream(consumer, token)

    def tearDown(self):
        for call in reactor.getDelayedCalls():
            if call.active():
                call.cancel()

    def _connect(self, mock_endpoint, mock_http_response):
        """general process for testing connection attempts which
        achieve a successful connection to the twitter servers and
        then attempt a http request
        """
        endpoint_connect_dfr = defer.Deferred()
        mock_endpoint.connect.return_value = endpoint_connect_dfr

        d = self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)

        # simulate a successful ssl connection
        mock_http_protocol = Mock(spec=HTTP11ClientProtocol)
        http_request_dfr = defer.Deferred()
        mock_http_protocol.request.return_value = http_request_dfr
        endpoint_connect_dfr.callback(mock_http_protocol)

        self.assertEquals(CONNECTING, self.stream.state)
        http_request_dfr.callback(mock_http_response)
        return d

    def _backoff(self, mock_endpoint):
        "put the test's stream object into BACKING_OFF state"
        mock_http_response = Mock()
        mock_http_response.code = 500
        self._connect(mock_endpoint, mock_http_response)

        # error should have caused back off
        self.assertEquals(BACKING_OFF, self.stream.state)
        self.assertTrue(self.stream.delayed_connect.active())

    def test_connection_error(self, mock_endpoint):
        "should back off linearly after network error"
        endpoint_connect_dfr = defer.Deferred()
        mock_endpoint.connect.return_value = endpoint_connect_dfr

        self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)

        # simulate a network error
        endpoint_connect_dfr.errback(Failure(''))
        self.assertEquals(BACKING_OFF, self.stream.state)
        self.assertEquals(2, self.stream.next_backoff)

    def test_recoverable_http_error(self, mock_endpoint):
        "should back off exponentially after recoverable http error"
        mock_http_response = Mock()
        mock_http_response.code = 500

        d = self._connect(mock_endpoint, mock_http_response)

        self.assertEquals(BACKING_OFF, self.stream.state)
        self.assertEquals(10, self.stream.next_backoff)

        self.assertFalse(d.called)

    def test_unrecoverable_http_error(self, mock_endpoint):
        "should disconnect and not retry after unrecoverable http error"
        mock_http_response = Mock()
        mock_http_response.code = 416

        d = self._connect(mock_endpoint, mock_http_response)

        self.assertEquals(DISCONNECTED, self.stream.state)
        self.assertEquals(-1, self.stream.next_backoff)

        self.assertTrue(d.called)
        # the deferred should have been cleared to allow future
        # connection attempts
        self.assertEquals(None, self.stream.dfr_stream_connected)

    def test_successful_connection(self, mock_endpoint):
        "should pass http request body to TwitterStreamingProtocol"
        mock_http_response = Mock()
        mock_http_response.code = 200
        mock_http_response.deliverBody = Mock()

        d = self._connect(mock_endpoint, mock_http_response)

        self.assertEquals(CONNECTED, self.stream.state)
        self.assertEquals(1, self.stream.next_backoff)
        self.assertTrue(mock_http_response.deliverBody.called)

        self.assertTrue(d.called)
        # the deferred should have been cleared to allow future
        # connection attempts
        self.assertEquals(None, self.stream.dfr_stream_connected)

    def test_disconnect_while_connecting_before_host_connect(self, mock_endpoint):
        endpoint_connect_dfr = defer.Deferred()
        mock_endpoint.connect.return_value = endpoint_connect_dfr

        self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)
        self.stream.disconnect()
        self.assertEquals(DISCONNECTED, self.stream.state)

    def test_disconnect_while_connecting_before_http_response(self, mock_endpoint):
        "should back off linearly after network error"
        endpoint_connect_dfr = defer.Deferred()
        mock_endpoint.connect.return_value = endpoint_connect_dfr

        self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)

        mock_http_protocol = Mock(spec=HTTP11ClientProtocol)
        mock_http_protocol.request.return_value = defer.Deferred()
        endpoint_connect_dfr.callback(mock_http_protocol)

        self.stream.disconnect()
        self.assertEquals(DISCONNECTED, self.stream.state)


    def test_disconnect_while_backing_off(self, mock_endpoint):
        self._backoff(mock_endpoint)

        # disconnect must cancel delayed connection attempt
        self.stream.disconnect()
        self.assertEquals(DISCONNECTED, self.stream.state)
        self.assertFalse(self.stream.delayed_connect.active())

    def test_new_connection_while_backing_off(self, mock_endpoint):
        self._backoff(mock_endpoint)

        # new connection attempt should cancel existing attempt, but
        # respect the backoff period. Should have scheduled a delayed
        # connection attempt.
        self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(DISCONNECTED, self.stream.state)
        self.assertTrue(self.stream.delayed_connect.active())

    def test_connect_while_connected(self, mock_endpoint):
        "should pass http request body to TwitterStreamingProtocol"
        mock_http_response = Mock()
        mock_http_response.code = 200
        mock_http_response.deliverBody = Mock()

        self._connect(mock_endpoint, mock_http_response)
        self.assertEquals(CONNECTED, self.stream.state)

        # create a new connection wihtout explicitly disconnecting
        mock_endpoint.connect.return_value = defer.Deferred()
        self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)
        self.assertEquals(None, self.stream.delayed_connect)

    def test_connect_while_connecting(self, mock_endpoint):
        first_deferred = defer.Deferred()
        mock_endpoint.connect.return_value = first_deferred
        self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)

        second_deferred = defer.Deferred()
        mock_endpoint.connect.return_value = second_deferred
        self.stream.track(TestReceiver(), ['track'])
        self.assertEquals(CONNECTING, self.stream.state)

        #original deferred should have been cancelled
        self.assertTrue(first_deferred.called)
        self.assertFalse(second_deferred.called)
        self.assertEquals(second_deferred, self.stream.dfr_reached_host)

