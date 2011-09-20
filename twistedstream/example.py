from stream import Stream
import random
from protocol import IStreamReceiver
import oauth2
from twisted.python import log
from twisted.internet import reactor

TWITTER_CONSUMER_KEY = 'bNH7tpZ5PcOIn9cPcC7A'
TWITTER_CONSUMER_SECRET = '1oONcbPEz4AwEXKziOx6qfG9FJc7O7Wm2j8ud2Tc'
TWITTER_APP_ACCESS_TOKEN = '6850912-MJmg4vAQhPrBVGWMw3Xkx2INNWVx8vsWwgEHtrgtbM'
TWITTER_APP_ACCESS_TOKEN_SECRET = 'YYVn9ezJdmCptP6PIY3NXGSch5Q7AgiCf3ylYlq7SHg'

consumer = oauth2.Consumer(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
token = oauth2.Token(TWITTER_APP_ACCESS_TOKEN, TWITTER_APP_ACCESS_TOKEN_SECRET)

class R(IStreamReceiver):
    def status(self, result):
        for url in result['entities']['urls']:
            if 'expanded_url' in url:
                print 'expanded', url['expanded_url']
            else:
                print 'url without expanded'
        print


if __name__ == '__main__':
    print 'go'
    stream = Stream(consumer, token)
    d = stream.track(R(), ["link"])
    d.addErrback(log.err)

    print 'go'
    reactor.run()
