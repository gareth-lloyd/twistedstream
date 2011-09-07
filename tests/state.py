import unittest
from datetime import datetime
from twistedstream import Stream
from twistedstream.stream import (DISCONNECTED, CONNECTING, CONNECTED, 
        BACKING_OFF)
from mock import Mock
from oauth import oauth


class StateTest(unittest.TestCase):

    def setUp(self):
        self.stream = Stream(Mock(spec=oauth.OAuthConsumer),
            Mock(spec=oauth.OAuthToken))

    def test_disconnected_to_connecting(self):
        self.stream._advance_state_to(CONNECTING)

    def test_disconnected_to_connected(self):
        "Can't transition to CONNECTED without passing through CONNECTING"
        self.assertRaises(ValueError, self.stream._advance_state_to, CONNECTED)
