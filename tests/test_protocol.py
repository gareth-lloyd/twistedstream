import unittest
from mock import Mock

from twistedstream.protocol import IStreamReceiver, TwitterStreamingProtocol
from twistedstream.stream import Stream, CONNECTED, FINISHED


class TwitterStreamingProtocolTests(unittest.TestCase):
    def setUp(self):
        self.receiver = Mock(spec=IStreamReceiver)
        self.stream = Stream(None, None)
        self.protocol = TwitterStreamingProtocol(self.receiver, self.stream)

    def test_deletion_notice(self):
        line = '{"delete":{"status":{"id":1234,"id_str":"1234","user_id":3,"user_id_str":"3"}}}'
        self.protocol.lineReceived(line)
        self.assertTrue(self.receiver.status_deletion.called)

    def test_status(self):
        self.protocol.lineReceived(SAMPLE_STATUS)
        self.assertTrue(self.receiver.status.called)

    def test_location_deletion(self):
        line = '{"scrub_geo":{"user_id":14090452,"user_id_str":"14090452","up_to_status_id":23260136625,"up_to_status_id_str":"23260136625"}}'
        self.protocol.lineReceived(line)
        self.assertTrue(self.receiver.location_deletion.called)

    def test_rate_limitation(self):
        line = '{"limit":{"track":1234}}'
        self.protocol.lineReceived(line)
        self.assertTrue(self.receiver.rate_limitation.called)

    def test_json_object(self):
        line = '{"object":{"something":1234}}'
        self.protocol.lineReceived(line)
        self.assertTrue(self.receiver.json.called)

    def test_invalid(self):
        line = '{"object":{"something":'
        self.protocol.lineReceived(line)
        self.assertTrue(self.receiver.invalid.called)

    def test_disconnected(self):
        self.stream.state = CONNECTED
        self.protocol.connectionLost(None)
        self.assertTrue(self.receiver.disconnected.called)
        self.assertEquals(FINISHED, self.stream.state)

    def test_timeout(self):
        self.stream.state = CONNECTED
        self.protocol.timeoutConnection()
        self.assertTrue(self.receiver.disconnected.called)

SAMPLE_STATUS = '{ "in_reply_to_user_id": null, "text": "the text" , "created_at": "Fri Sep 09 09:31:30 +0000 2011", "truncated": false, "retweeted": false, "in_reply_to_status_id": null, "id": 112095778343890944, "in_reply_to_status_id_str": null, "in_reply_to_screen_name": null, "id_str": "112095778343890944", "place": null, "retweet_count": 252, "geo": null, "user": { "profile_image_url_https": "https://si0.twimg.com/a.jpg", "id": 110827095, "profile_text_color": "cfaf10", "followers_count": 252, "profile_background_color": "070808", "id_str": "110827095", "utc_offset": -28800, "profile_image_url": "http://a3.twimg.com/a.jpg", "name": "javonte", "lang": "en", "profile_background_tile": true, "screen_name": "vony_abb", "contributors_enabled": false, "time_zone": "Pacific Time (US & Canada)", "listed_count": 0}}'
