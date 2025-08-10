import os
import unittest
import unittest.mock
from simple_rss_mailer import RssNotifier, RssStateHandler, SimpleRssMailer

class MockRssStateHandler(RssStateHandler):
	"""Unit test version of RssStateHandler which uses local directory instead of S3
	"""
	def __init__(self, directory: str):
		self.directory = directory
		if not os.path.exists(self.directory):
			os.makedirs(self.directory)

	def get_rss_feed(self, rss_url: str) -> str:
		file_path: str = self.directory + RssStateHandler.calculate_s3_key('', rss_url)
		if os.path.exists(file_path):
			with open(file_path, 'r') as f:
				return f.read()
		return ""

	def save_rss_feed(self, rss_url: str, rss_blob: str):
		pass

class MockRssNotifier(RssNotifier):

	def __init__(self):
		self.notified_entries: list[dict] = []

	def notify(self, entry: dict):
		self.notified_entries.append(entry)

class TestRssState(unittest.TestCase):

	def test_hash_rss_url(self):
		hash: str = RssStateHandler.calculate_s3_key('rss_feeds', 'https://www.keycloak.org/rss.xml')
		self.assertEqual('rss_feeds/www.keycloak.org-5120.xml', hash)

class SimpleRssMailerTest(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.mock_rss_state_handler_empty = MockRssStateHandler('test/state_empty') # No state has been previously saved
		cls.mock_rss_state_handler_old = MockRssStateHandler('test/state_old') # State is old so a comparison will return new entries
		cls.mock_rss_state_handler_current = MockRssStateHandler('test/state_current') # State is current so a comparison will return no new entries

	def setUp(self):
		self.mock_rss_notifier = MockRssNotifier()

	def test_compare_rss_feeds(self):
		srm: SimpleRssMailer = SimpleRssMailer(self.mock_rss_state_handler_old, self.mock_rss_notifier)

		with open('test/state_old/www.keycloak.org-5120.xml', 'r') as f_old:
			with open('test/state_current/www.keycloak.org-5120.xml', 'r') as f_new:
				new_entries: list[dict] = srm.diff_rss_feeds(f_old.read(), f_new.read())
				self.assertEqual(2, len(new_entries))
				self.assertEqual(new_entries[0]['title'], 'BRZ Keycloak case study published')
				self.assertEqual(new_entries[0]['id'], 'https://www.keycloak.org/2025/08/brz-case-study')
				self.assertEqual(new_entries[1]['title'], 'Keycloak 26.3.2 released')
				self.assertEqual(new_entries[1]['id'], 'https://www.keycloak.org/2025/07/keycloak-2632-released')

	def test_process_rss_feed(self):

		with open('test/state_current/www.keycloak.org-5120.xml', 'r') as f_new: # Download
			downloaded_rss_content = f_new.read()
			with unittest.mock.patch.object(SimpleRssMailer, 'download_rss', return_value=downloaded_rss_content): # Mock "download_rss" function to return current content

				# With old state - so should get new entries
				srm: SimpleRssMailer = SimpleRssMailer(self.mock_rss_state_handler_old, self.mock_rss_notifier)
				self.assertEqual(2, srm.process_rss_feed('https://www.keycloak.org/rss.xml'))
				self.assertEqual(2, len(self.mock_rss_notifier.notified_entries))
				self.assertEqual(self.mock_rss_notifier.notified_entries[0]['title'], 'Keycloak 26.3.2 released')
				self.assertEqual(self.mock_rss_notifier.notified_entries[0]['id'], 'https://www.keycloak.org/2025/07/keycloak-2632-released')
				self.assertEqual(self.mock_rss_notifier.notified_entries[1]['title'], 'BRZ Keycloak case study published')
				self.assertEqual(self.mock_rss_notifier.notified_entries[1]['id'], 'https://www.keycloak.org/2025/08/brz-case-study')

				# With current state - so no new entries
				self.mock_rss_notifier.notified_entries.clear()
				srm: SimpleRssMailer = SimpleRssMailer(self.mock_rss_state_handler_current, self.mock_rss_notifier)
				self.assertEqual(0, srm.process_rss_feed('https://www.keycloak.org/rss.xml'))
				self.assertEqual(0, len(self.mock_rss_notifier.notified_entries))

				# With empty state - so everything is new
				self.mock_rss_notifier.notified_entries.clear()
				srm: SimpleRssMailer = SimpleRssMailer(self.mock_rss_state_handler_empty, self.mock_rss_notifier)
				self.assertEqual(159, srm.process_rss_feed('https://www.keycloak.org/rss.xml'))
				self.assertEqual(159, len(self.mock_rss_notifier.notified_entries))
				self.assertEqual(self.mock_rss_notifier.notified_entries[0]['title'], 'How to Setup MS AD FS 3.0 as Brokered Identity Provider in Keycloak')
				self.assertEqual(self.mock_rss_notifier.notified_entries[0]['id'], 'https://www.keycloak.org/2017/03/how-to-setup-ms-ad-fs-30-as-brokered')
				self.assertEqual(self.mock_rss_notifier.notified_entries[158]['title'], 'BRZ Keycloak case study published')
				self.assertEqual(self.mock_rss_notifier.notified_entries[158]['id'], 'https://www.keycloak.org/2025/08/brz-case-study')