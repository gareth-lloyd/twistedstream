import json
from twisted.protocols.basic import LineOnlyReceiver
from twisted.protocols.policies import TimeoutMixin
from twisted.python import failure
from twisted.internet import error

class IStreamReceiver(object):

    def status(self, obj):
        pass

    def status_deletion(self, obj):
        pass

    def location_deletion(self, obj):
        pass

    def rate_limitation(self, obj):
        pass

    def json(self, obj):
        "Default case for an unrecognized json object"

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
                if 'text' in obj:
                    self.receiver.status(obj)
                elif 'delete' in obj:
                    self.receiver.status_deletion(obj)
                elif 'scrub_geo' in obj:
                    self.receiver.location_deletion(obj)
                elif 'limit' in obj:
                    self.receiver.rate_limitation(obj)
                else:
                    self.receiver.json(obj)
            except ValueError, e:
                print e
                self.receiver.invalid(line)

    def connectionLost(self, reason):
        self.receiver.disconnected(reason)

    def timeoutConnection(self):
        self.receiver.disconnected(failure.Failure(error.ConnectionLost()))
