import boto3
import feedparser
import gzip
import hashlib
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

logger = logging.getLogger(__name__)
time_start: float = time.time()
patch_all()
logger.debug(f"X-Ray patching took {time.time() - time_start:.2f} seconds")

class RssStateHandler:
	"""Saves and retrieves RSS feed using AWS S3. This allows us to remember what the feed looked like the last time we checked it."""

	CONTENT_ENCODING = 'content-encoding'
	GZIP = 'gzip'

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
			s3_response: dict = self.client.get_object(Bucket=self.s3_bucket_name, Key=s3_key)
			content_bytes: bytes = s3_response['Body'].read()
			if s3_response['Metadata'].get(RssStateHandler.CONTENT_ENCODING) == RssStateHandler.GZIP:
				return gzip.decompress(content_bytes).decode()
			else:
				return content_bytes.decode()
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
		compressed_rss_blob: bytes = gzip.compress(rss_blob.encode())
		self.client.put_object(Bucket=self.s3_bucket_name, Key=s3_key, Body=compressed_rss_blob, Metadata={RssStateHandler.CONTENT_ENCODING: RssStateHandler.GZIP})


class RssNotifier:
	"""Notifies a AWS SNS topic about new RSS entries."""

	def __init__(self, sns_topic_arn: str):
		self.sns_topic_arn = sns_topic_arn
		# Create the client in the topic's region to avoid "InvalidParameter" TopicArn errors on publish
		self.client = boto3.client('sns', region_name=sns_topic_arn.split(':')[3])

	def notify(self, entry: dict):
		logger.info(f"Sending notification to SNS topic {self.sns_topic_arn} for entry: title={entry['title']}, id={entry['id']}, published={entry['published']}")
		response: dict = self.client.publish(
			TopicArn = self.sns_topic_arn,
			MessageStructure = 'json',
			Subject = entry['title'],
			Message = self.generate_notification_message(entry)
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

	@xray_recorder.capture('## Download RSS')
	def download_rss(self, rss_url: str) -> str:
		with urllib.request.urlopen(rss_url) as f:
			return f.read().decode()

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
			logger.info(f"No new entries found in RSS feed {rss_url}")
			return 0

		for new_entry in reversed(new_entries): # Reverse the list so that oldest entries are notified first
			self.rss_notifier.notify(new_entry)

		self.rss_state_handler.save_rss_feed(rss_url, new_rss_feed)

		return len(new_entries)

	@xray_recorder.capture('## Diff RSS feeds')
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

def check_feeds(sns_topic_arn: str, bucket: str, bucket_path: str, rss_urls: list[str]) -> int:
	"""Checks the RSS feeds and sends email-formatted notifications if new entries are found.

	Args:
		sns_topic_arn (str): SNS topic to send email notifications to
		bucket (str): S3 bucket used to save RSS feed state (so we remember which articles have been seen already)
		bucket_path (str): Path within the S3 bucket to save RSS feed state
		rss_urls (list[str]): List of RSS URLs to check

	Returns:
		int: _description_
	"""
	logger.info(f"Checking RSS feeds. SNS topic ARN: {sns_topic_arn}, S3 bucket: {bucket}, S3 path: {bucket_path}, RSS URLs: {rss_urls}.")

	notifier: RssNotifier = RssNotifier(sns_topic_arn)
	rss_state: RssStateHandler = RssStateHandler(bucket, bucket_path)

	new_articles: int = 0

	srs: SimpleRssMailer = SimpleRssMailer(rss_state, notifier)
	for rss_url in rss_urls:
		new_articles += srs.process_rss_feed(rss_url)

	return new_articles

def handle(event: dict, context: object) -> int:
	sns_topic_arn: str = os.getenv('SNS_TOPIC_ARN', '<missing>')
	bucket: str = os.getenv('BUCKET', '<missing>')
	bucket_path: str = os.getenv('BUCKET_PATH', '<missing>')
	rss_urls: list[str] = event['rss_urls']

	return check_feeds(sns_topic_arn, bucket, bucket_path, rss_urls)

if __name__ == '__main__':
	logging.basicConfig() # Basic logging to standard out
	logger.setLevel(logging.DEBUG)

	sns_topic_arn: str = sys.argv[1]
	bucket: str = sys.argv[2]
	bucket_path: str = sys.argv[3]
	rss_urls: list[str] = sys.argv[4:]

	new_articles: int = check_feeds(sns_topic_arn, bucket, bucket_path, rss_urls)
	logger.info(f"Number of new articles found: {new_articles}")
