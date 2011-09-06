import json
from twisted.internet import defer
from twisted.protocols.basic import LineOnlyReceiver
from twisted.protocols.policies import TimeoutMixin
from twisted.python import log
from twisted.web.client import ResponseDone
from twisted.web.http import PotentialDataLoss

class TwitterStreamingProtocol(LineOnlyReceiver, TimeoutMixin):
    def __init__(self, callback, timeout_seconds=60):
        self.setTimeout(timeout_seconds)
        self.callback = callback
        self.deferred = defer.Deferred()

    def lineReceived(self, line):
        """
        Decode the JSON-encoded datagram and call the callback.
        """
        line = line.strip()
        if line:
            try:
                obj = json.loads(line)
            except ValueError, e:
                log.err(e, 'Invalid JSON in stream: %r' % line)
                return
            self.callback(obj)

    def dataReceived(self, data):
        self.resetTimeout()
        LineOnlyReceiver.dataReceived(self, data)

    def connectionLost(self, reason):
        """
        Called when the body is complete or the connection was lost.

        @note: As the body length is usually not known at the beginning of the
        response we expect a L{PotentialDataLoss} when Twitter closes the
        stream, instead of L{ResponseDone}. Other exceptions are treated
        as error conditions.
        """
        self.setTimeout(None)
        if reason.check(ResponseDone, PotentialDataLoss):
            self.deferred.callback(None)
        else:
            self.deferred.errback(reason)

    def timeoutConnection(self):
        self.deferred.errback(None)
