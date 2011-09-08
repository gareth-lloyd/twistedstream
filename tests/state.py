import unittest
from twistedstream import Stream
from twistedstream.stream import (DISCONNECTED, CONNECTING, CONNECTED, 
        BACKING_OFF)

class StateTest(unittest.TestCase):
    """with four states, there are 16 possible transitions, including
    'transitioning' to the same state. 
    """
    def setUp(self):
        self.stream = Stream(None, None)

    def test_disconnected(self):
        "can go from disconnected to connecting or disconnected"
        self._valid(DISCONNECTED, (CONNECTING, DISCONNECTED))
        self._invalid(DISCONNECTED, (CONNECTED, BACKING_OFF))

    def test_connected(self):
        "from connected can transition to disconnected only"
        self._valid(CONNECTED, (DISCONNECTED, ))
        self._invalid(CONNECTED, (CONNECTED, CONNECTING, BACKING_OFF))

    def test_connecting(self):
        "from connecting can transition to disconnected, connected or backing off"
        self._valid(CONNECTING, (DISCONNECTED, CONNECTED, BACKING_OFF))
        self._invalid(CONNECTING, (CONNECTING, ))

    def test_backing_off(self):
        "from backing off, can transition to disconnected, or connecting"
        self._valid(BACKING_OFF, (DISCONNECTED, CONNECTING))
        self._invalid(BACKING_OFF, (BACKING_OFF, CONNECTED))

    def _invalid(self, initial_state, invalid_states):
        for invalid_state in invalid_states:
            self.stream.state = initial_state
            self.assertRaises(ValueError, self.stream._advance_state_to, invalid_state)

    def _valid(self, initial_state, valid_states):
        for valid_state in valid_states:
            self.stream.state = initial_state
            self.stream._advance_state_to(valid_state)
