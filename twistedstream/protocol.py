import json
from twisted.protocols.basic import LineOnlyReceiver
from twisted.protocols.policies import TimeoutMixin
from twisted.python import log, failure
from twisted.web import error

class IStreamReceiver(object):
    def json(self, obj):
        pass

    def invalid(self, line):
        pass

    def disconnected(self, reason):
        pass

class TwitterStreamingProtocol(LineOnlyReceiver, TimeoutMixin):
    def __init__(self, receiver, timeout_seconds=60):
        self.setTimeout(timeout_seconds)
        self.receiver = receiver

    def lineReceived(self, line):
        self.resetTimeout()
        line = line.strip()
        if line:
            try:
                obj = json.loads(line)
                self.receiver.json(obj)
            except ValueError:
                self.receiver.invalid(line)

    def connectionLost(self, reason):
        self.receiver.disconnected(reason)

    def timeoutConnection(self):
        self.receiver.disconnected(failure.Failure(error.ConnectionLost()))
