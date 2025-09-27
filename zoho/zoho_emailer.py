from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
import boto3
import json
import logging
import os

logger = logging.getLogger(__name__)

def _get_parameter(client, prefix: str, name: str) -> str:
	param: dict = client.get_parameter(Name=f"{prefix}/{name}", WithDecryption=True)
	return param['Parameter']['Value']

def handle(event: dict, context: object):
	# Config
	ssm_parameter_prefix: str = os.getenv('SSM_PARAMETER_PREFIX', '/')

	ssm_client = boto3.client('ssm')
	account_id = _get_parameter(ssm_client, ssm_parameter_prefix, 'accountId')
	client_id = _get_parameter(ssm_client, ssm_parameter_prefix, 'clientId')
	client_secret = _get_parameter(ssm_client, ssm_parameter_prefix, 'clientSecret')
	destination_emails = _get_parameter(ssm_client, ssm_parameter_prefix, 'destinationEmail').split(';')
	from_address = _get_parameter(ssm_client, ssm_parameter_prefix, 'fromEmail')

	logger.debug(f"Configuration: client_id={client_id}, account_id={account_id}, from={from_address}, destination={destination_emails}")

	# Zoho Mail API client
	client = BackendApplicationClient(client_id=client_id)
	oauth = OAuth2Session(client=client)
	oauth.fetch_token(token_url='https://accounts.zoho.com/oauth/v2/token', client_id=client_id, client_secret=client_secret, scope='ZohoMail.messages.CREATE')

	for record in event['Records']:
		message = json.loads(record['Sns']['Message'])
		logger.debug(f"SNS record={message}")
		link = message["link"]
		title = message["title"]
		publish_date = message["publishDate"]
		content_type = message['contentType']
		content = message['content']
		mail_format = "plaintext"
		if content_type == 'text/html':
			email_content = f'<h2><a href="{link}">{title}</a></h2>\n<p>Article date: {publish_date}</p>{content}'
			mail_format = "html"
		else:
			email_content = f'{title}\n\nArticle date: {publish_date}\nLink: {link}'
			if content:
				email_content += f'\n\n{content}'

		for destination_email in destination_emails:
			data: dict = {
				"fromAddress": from_address,
				"toAddress": destination_email.strip(),
				"subject": title,
				"content": email_content,
				"mailFormat": mail_format,
				"askReceipt": 'no'
			}
			response = oauth.post(f"https://mail.zoho.com/api/accounts/{account_id}/messages", json=data)
			logger.info(f"To={destination_email}, Title={title}. Response code={response.status_code}")
