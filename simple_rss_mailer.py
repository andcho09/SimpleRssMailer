import boto3
import feedparser
import hashlib
import json
import logging
import sys
import urllib.parse
import urllib.request

logger = logging.getLogger()

class RssStateHandler:
	"""Saves and retrieves RSS feed using AWS S3. This allows us to remember what the feed looked like the last time we checked it."""

	@staticmethod
	def calculate_s3_key(s3_path_prefix: str, rss_url: str) -> str:
		"""Hashes an RSS URL to a string that can be used as a key in S3. The hash includes the hostname to make it easy to identify.

		Args:
			rss_url (str): URL of the RSS feed

		Raises:
			ValueError: if the hostname could not be found in the URL

		Returns:
			str: The URL's hostname lowercased, followed by the last four characters of its MD5 hash.
		"""
		url: tuple = urllib.parse.urlparse(rss_url, allow_fragments=False)

		if url.hostname is None:
			raise ValueError(f"Could not determine hostname from: {rss_url}")

		# hash rss_url
		m = hashlib.md5()
		m.update(rss_url.encode())
		hash: str = m.hexdigest()[-4:] # Last 4 characters

		return f"{s3_path_prefix}/{url.hostname.lower()}-{hash}.xml"

	def __init__(self, s3_bucket_name: str, s3_bucket_path: str):
		self.s3_bucket_name = s3_bucket_name
		self.s3_bucket_path = s3_bucket_path
		self.client = boto3.client('s3')

	def get_rss_feed(self, rss_url: str) -> str:
		"""Retrieves the previous RSS feed saved in S3.

		Args:
			rss_url (str): URL of the RSS feed

		Returns:
			str: Raw RSS feed or the empty string if there's no state
		"""
		s3_key: str = RssStateHandler.calculate_s3_key(self.s3_bucket_path, rss_url)
		logger.debug(f"Getting RSS state for feed '{rss_url}' from S3 at '{s3_key}'")
		try:
			return self.client.get_object(Bucket=self.s3_bucket_name, Key=s3_key).get('Body').read().decode()
		except self.client.exceptions.NoSuchKey:
			return ""

	def save_rss_feed(self, rss_url: str, rss_blob: str):
		"""Saves the RSS feed in S3.

		Args:
			rss_url (str): URL of the RSS feed
			rss_blob (str): The raw RSS feed
		"""
		s3_key: str = RssStateHandler.calculate_s3_key(self.s3_bucket_path, rss_url)
		logger.debug(f"Saving RSS state for feed '{rss_url}' to S3 at '{s3_key}'")

		self.client.put_object(Bucket=self.s3_bucket_name, Key=s3_key, Body=rss_blob)


class RssNotifier:
	"""Notifies a AWS SNS topic about new RSS entries."""

	def __init__(self, sns_topic_arn: str):
		self.sns_topic_arn = sns_topic_arn
		self.client = boto3.client('sns')

	def notify(self, entry: dict):
		logger.info(f"Sending notification to SNS topic {self.sns_topic_arn} for entry: title={entry['title']}, id={entry['id']}, published={entry['published']}")
		# The topic has to be in same region as this is running otherwise this will create "InvalidParameter" TopicArn errors.
		response: dict = self.client.publish(
			TopicArn = self.sns_topic_arn,
			MessageStructure = 'json',
			Subject = entry['title'],
			Message = self.generate_notification_message(entry),
			MessageDeduplicationId = entry['id']
		)
		logger.debug(f"Published SNS notification {response['MessageId']}")

	def generate_notification_message(self, entry: dict) -> str:
		message: dict = dict()
		message['default'] = entry['title']
		message['email'] = f"{entry['title']}\n\nDate: {entry['published']}\n\nLink: {entry['link']}"
		return json.dumps(message)

class SimpleRssMailer:

	def __init__(self, rss_state_handler: RssStateHandler, rss_notifier: RssNotifier):
		self.rss_state_handler = rss_state_handler
		self.rss_notifier = rss_notifier

	def download_rss(self, rss_url: str) -> str:
		with urllib.request.urlopen(rss_url) as f:
			return f.read()

	def process_rss_feed(self, rss_url: str) -> int:
		"""Downloads the RSS feed, compares it the state, and sends notifications for any new entries. State is updated with the new RSS feed.

		Args:
			rss_url (str): URL of the RSS feed

		Returns:
			int: Number of new entries, i.e. notifications sent
		"""
		new_rss_feed: str = self.download_rss(rss_url)
		old_rss_feed: str = self.rss_state_handler.get_rss_feed(rss_url)

		new_entries: list[dict] = self.diff_rss_feeds(old_rss_feed, new_rss_feed)

		if len(new_entries) == 0:
			logger.info('No new entries found in RSS feed {rss_url}')
			return 0

		for new_entry in reversed(new_entries): # Reverse the list so that oldest entries are notified first
			self.rss_notifier.notify(new_entry)

		self.rss_state_handler.save_rss_feed(rss_url, new_rss_feed)

		return len(new_entries)

	def diff_rss_feeds(self, old_feed_str: str, new_feed_str: str) -> list[dict]:
		"""Returns entries in the new feed that aren't in the old feed.

		Args:
			old_feed_str (str): old raw RSS feed string
			new_feed_str (str): new raw RSS feed string

		Returns:
			list[dict]: A list of feedparser entry dict objects
		"""
		old_feed: feedparser.FeedParserDict = feedparser.parse(old_feed_str)
		new_feed: feedparser.FeedParserDict = feedparser.parse(new_feed_str)

		old_items_ids: set = set()
		new_entries: list[dict] = []
		for entry in old_feed.entries:
			old_items_ids.add(self.get_rss_entry_id(entry))
		for entry in new_feed.entries:
			entry_id = self.get_rss_entry_id(entry)
			if entry_id not in old_items_ids:
				new_entries.append(entry)
		return new_entries

	def get_rss_entry_id(self, entry: dict) -> str:
		if 'id' in entry:
			return entry['id']
		else:
			return entry['link']

if __name__ == '__main__':
	sns_topic_arn: str = sys.argv[1]
	bucket: str = sys.argv[2]
	bucket_path: str = sys.argv[3]
	rss_urls: list[str] = sys.argv[4:]

	logger.info(f"Checking RSS feeds. SNS topic ARN: {sns_topic_arn}, S3 bucket: {bucket}, S3 path: {bucket_path}, RSS URLs: {rss_urls}.")

	noitifier: RssNotifier = RssNotifier(sns_topic_arn)
	rss_state: RssStateHandler = RssStateHandler(bucket, bucket_path)

	srs: SimpleRssMailer = SimpleRssMailer(rss_state, noitifier)
	for rss_url in rss_urls:
		srs.process_rss_feed(rss_url)
