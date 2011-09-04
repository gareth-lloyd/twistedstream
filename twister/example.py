from stream import Stream
import oauth2
from twisted.python import log
from twisted.internet import reactor

from twittytwister.twitter import TwitterFeed

TWITTER_APP_ACCESS_TOKEN_SECRET = ''
TWITTER_APP_ACCESS_TOKEN = ''
TWITTER_CONSUMER_KEY = ''
TWITTER_CONSUMER_SECRET = ''

consumer = oauth2.Consumer(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
token = oauth2.Token(TWITTER_APP_ACCESS_TOKEN, TWITTER_APP_ACCESS_TOKEN_SECRET)

def twister():
    def callback(result):
        print result.text
        print

    def stop(failure):
        reactor.stop()

    stream = Stream(consumer, token, 35)
    d = stream.track(callback, ['gareth'])
    d.addErrback(log.err)
    d.addErrback(stop)

    reactor.run()


def twitty():
    def callback(status):
        # this is happening in streaming thread = stupid
        try:
            print status.text
            print
        except Exception, e:
            print e

    track = ['gareth']

    stream = TwitterFeed(consumer=consumer, token=token)
    print 'starting to stream'
    deferred = stream.track(callback, track)

    deferred.addErrback(log.err)
    print 'starting'
    reactor.run()

if __name__ == '__main__':
    twister()
