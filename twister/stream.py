import time
from urllib import quote

from twisted.internet import defer, reactor
from twisted.web import client, error, http_headers
from twisted.web.http_headers import Headers
import oauth2

import protocol

STREAM_URL = 'http://stream.twitter.com/1/statuses/%s.json'

class Stream(object):

    protocol = protocol.TwitterStream

    def __init__(self, consumer=None, token=None, timeout=0):
        self.timeout = timeout
        self.consumer = consumer
        self.token = token
        self.agent = client.Agent(reactor)

    def _make_auth_headers(self, http_method, url, parameters={}, headers={}):
        oauth_request = oauth2.Request.from_consumer_and_token(self.consumer, is_form_encoded=True,
            token=self.token, http_method=http_method, http_url=url, parameters=parameters)
        oauth_request.sign_request(oauth2.SignatureMethod_HMAC_SHA1(), self.consumer, self.token)

        headers.update(oauth_request.to_header())
        for key, value in headers.items():
            headers[key] = [value]
        return headers

    def _stream(self, api_call, http_method, status_receiver, args):
        def get_initial_response(response):
            if response.code == 200:
                protocol = self.protocol(status_receiver)
                response.deliverBody(protocol)
                return protocol
            else:
                response.deliverBody(PrintProtocol())
                raise error.Error(response.code, response.phrase)

        url = STREAM_URL % api_call

        args = args or {}
        args['delimited'] = 'length'
        arg_str = _urlencode(args)
        print arg_str
        if http_method == 'GET':
            url += '?' + arg_str
            body_producer = None
        else:
            body_producer = StringProducer(arg_str)
        auth_headers = self._make_auth_headers(http_method, url, {})
        print auth_headers
        headers = Headers(auth_headers)
        print 'Fetching', url
        d = self.agent.request(http_method, url, headers, body_producer)
        d.addCallback(get_initial_response)
        return d

    def filter(self, status_receiver, args=None):
        return self._stream('filter', 'GET', status_receiver, args)

    def follow(self, status_receiver, follow):
        return self.filter(status_receiver, {'follow': ','.join(follow)})

    def track(self, status_receiver, terms):
        return self.filter(status_receiver, {'track': ','.join(terms)})

def _urlencode(headers):
    encoded = []
    for key,value in headers.iteritems():
        encoded.append('%s=%s' %
            (quote(key.encode("utf-8")),
            quote(value.encode("utf-8"))))
    return '&'.join(encoded)

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

class PrintProtocol(object):
    def __init__(self):
        self.f = open('log', 'w')

    def dataReceived(self, data):
        f.write(data)
    def connectionLost(self, reason):
        pass

    def makeConnection(self, transport):
        pass

    def connectionMade(self):
        pass

