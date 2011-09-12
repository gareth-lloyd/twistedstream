import unittest
from mock import Mock

from twistedstream.protocol import IStreamReceiver, TwitterStreamingProtocol


class TwitterStreamingProtocolTests(unittest.TestCase):
    def setUp(self):
        self.receiver = Mock(spec=IStreamReceiver)
        self.protocol = TwitterStreamingProtocol(self.receiver)

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
        self.protocol.connectionLost(None)
        self.assertTrue(self.receiver.disconnected.called)

    def test_timeout(self):
        self.protocol.timeoutConnection()
        self.assertTrue(self.receiver.disconnected.called)

SAMPLE_STATUS = """{         u'in_reply_to_user_id': null,        u'text': text,        u'created_at': u'Fri Sep 09 09:31:30 +0000 2011',        u'truncated': false,        u'retweeted': false,        u'in_reply_to_status_id': null,        u'id': 112095778343890944,        u'in_reply_to_status_id_str': null,        u'in_reply_to_screen_name': null,        u'id_str': u'112095778343890944',        u'place': null,        u'retweet_count': 0,        u'geo': null,        u'in_reply_to_user_id_str': null,        user = {             u'profile_image_url_https': u'https://si0.twimg.com/a.jpg',            u'id': 110827095,            u'profile_text_color': u'cfaf10',            u'followers_count': 252,            'profile_background_color': u'070808',            u'id_str': u'110827095',            u'utc_offset': -28800,            u'profile_image_url': u'http://a3.twimg.com/a.jpg',            u'name': u'javonte',            u'lang': u'en',            u'profile_background_tile': true,            u'screen_name': u'vony_abb',            u'contributors_enabled': false,            u'time_zone': u'Pacific Time (US & Canada)',            u'listed_count': 0        }}"""
