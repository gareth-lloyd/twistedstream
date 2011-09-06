from stream import Stream
import oauth2
from twisted.python import log
from twisted.internet import reactor

TWITTER_CONSUMER_KEY = ''
TWITTER_CONSUMER_SECRET = ''
TWITTER_APP_ACCESS_TOKEN = ''
TWITTER_APP_ACCESS_TOKEN_SECRET = ''

consumer = oauth2.Consumer(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
token = oauth2.Token(TWITTER_APP_ACCESS_TOKEN, TWITTER_APP_ACCESS_TOKEN_SECRET)

def twister():
    def callback(result):
        print result['text']
        print

    stream = Stream(consumer, token, 35)
    d = stream.track(callback, ['football'])
    d.addErrback(log.err)

    reactor.run()

if __name__ == '__main__':
    twister()
