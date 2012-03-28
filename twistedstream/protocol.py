import json
from twisted.protocols.basic import LineOnlyReceiver
from twisted.protocols.policies import TimeoutMixin
from twisted.python import failure
from twisted.internet import error

class IStreamReceiver(object):
    """Receiver methods should expect a dictionary-like JSON object,
    containing all the properties passed by the Twitter API. If the
    API sends through an unrecognized but valid JSON object, it will
    be passed to the json() method. If an invalid JSON object is
    received, the line in question will be passed to the invalid()
    method.
    """

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
    def __init__(self, receiver, stream, timeout_seconds=60):
        self.receiver = receiver
        self.stream = stream
        self.setTimeout(timeout_seconds)

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
        self.stream.disconnect(reason)
        self.receiver.disconnected(reason)

    def timeoutConnection(self):
        self.stream.disconnect(failure.Failure(error.ConnectionLost()))
        self.receiver.disconnected(failure.Failure(error.ConnectionLost()))
