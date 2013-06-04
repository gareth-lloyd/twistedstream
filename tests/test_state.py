import unittest
from twistedstream import Stream
from twistedstream.stream import (DISCONNECTED, CONNECTING, CONNECTED, 
        FINISHED)

class StateTest(unittest.TestCase):
    """with four states, there are 16 possible transitions, including
    'transitioning' to the same state. 
    """
    def setUp(self):
        self.stream = Stream(None, None)

    def _invalid(self, initial_state, invalid_states):
        for invalid_state in invalid_states:
            with self.assertRaises(ValueError):
                self.stream.state = initial_state
                self.stream._advance_state_to(invalid_state)

    def _valid(self, initial_state, valid_states):
        for valid_state in valid_states:
            self.stream.state = initial_state
            self.stream._advance_state_to(valid_state)

    def test_disconnected(self):
        "can go from disconnected to connecting or disconnected"
        self._valid(DISCONNECTED, (CONNECTING, ))
        self._invalid(DISCONNECTED, (CONNECTED, FINISHED, DISCONNECTED))

    def test_connected(self):
        "from connected can transition to FINISHED only"
        self._valid(CONNECTED, (FINISHED, ))
        self._invalid(CONNECTED, (CONNECTING, DISCONNECTED, CONNECTED))

    def test_connecting(self):
        "from connecting can transition to disconnected, connected or backing off"
        self._valid(CONNECTING, (CONNECTED, FINISHED))
        self._invalid(CONNECTING, (CONNECTING, DISCONNECTED))

    def test_finished(self):
        "from finished, cannot advance"
        self._invalid(FINISHED, (CONNECTED, CONNECTING, DISCONNECTED))
        self._valid(FINISHED, (FINISHED, ))

