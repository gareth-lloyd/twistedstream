from urllib import quote

from twisted.internet import defer, reactor
from twisted.web import client, error
from twisted.web.http_headers import Headers
from oauth import oauth

import protocol

STREAM_URL = 'https://stream.twitter.com/1/statuses/%s.json'

class Stream(object):

    protocol = protocol.TwitterStreamingProtocol

    def __init__(self, consumer=None, token=None, timeout=0):
        self.timeout = timeout
        self.consumer = consumer
        self.token = token
        self.agent = client.Agent(reactor)

    def _make_oauth1_headers(self, http_method, url, parameters={}, headers={}):
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer,
            token=self.token, http_method=http_method, http_url=url, parameters=parameters)
        oauth_request.sign_request(oauth.OAuthSignatureMethod_HMAC_SHA1(), self.consumer, self.token)

        headers.update(oauth_request.to_header())
        return headers

    def _connect(self, api_call, http_method, status_receiver, args):
        def get_initial_response(response):
            if response.code == 200:
                protocol = self.protocol(status_receiver)
                response.deliverBody(protocol)
                return protocol
            else:
                raise error.Error(response.code, response.phrase)

        url = STREAM_URL % api_call
        raw_headers = {}

        args = args or {}
        arg_str = _urlencode(args)
        if http_method == 'GET':
            url += '?' + arg_str
            body_producer = None
        else:
            raw_headers['Content-Type'] = 'application/x-www-form-urlencoded'
            body_producer = StringProducer(arg_str)
        auth_headers = self._make_oauth1_headers(http_method, url, args, raw_headers)
        raw_headers = dict([(name, [value])
                           for name, value
                           in auth_headers.iteritems()])
        headers = Headers(raw_headers)
        print http_method, url
        d = self.agent.request(http_method, url, headers, body_producer)
        d.addCallback(get_initial_response)
        return d

    def filter(self, status_receiver, args=None):
        return self._connect('filter', 'POST', status_receiver, args)

    def follow(self, status_receiver, follow):
        return self.filter(status_receiver, {'follow': ','.join(follow)})

    def track(self, status_receiver, terms):
        return self.filter(status_receiver, {'track': ','.join(terms)})

def _urlencode(headers):
    encoded = []
    for key, value in headers.iteritems():
        encoded.append("%s=%s" %
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

