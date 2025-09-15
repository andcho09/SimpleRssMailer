# Simple RSS Mailer

Periodically checks an RSS feed and emails the articles.

## Limitations

Functional:

* This is a simple project aimed at a single subscriber so only one email address can be configured.
* When checking the RSS feed for the first time, no notifications are sent. Notifications are sent from this point onwards.


## Developing

### Requirements

* Python 3.13
* AWS account
	* Various AWS SSM parameters denoting:
		|Parameter|Description|
		|---------|-----------|
		|/RssEmailerZohoNotifier/accountId|Zoho Mail API account ID|
		|/RssEmailerZohoNotifier/clientId|Zoho Mail API client ID|
		|/RssEmailerZohoNotifier/clientSecret|Zoho Mail API client secret|
		|/RssEmailerZohoNotifier/destinationEmail|Email address to send the notification to|
		|/RssEmailerZohoNotifier/fromEmail|From email address. Must be a valid email address in the Zoho account|
		|/RssEmailerZohoNotifier/emailSubject|Email subject to use in the notification|

		* Where `RssEmailerZohoNotifier` is the SSM parameter's path prefix. This is passed as an environment variable to the Lambda function. It should start with `/`
		* Example AWS CLI to create the parameters:

			```sh
			aws ssm put-parameter --name "<prefix>/clientId" --type "String" --value "1111111" --tags "Key=Application,Value=RssEmailerZohoNotifier" --region us-east-1

			aws ssm put-parameter --name "/RssEmailerZohoNotifier/clientSecret" --type "SecureString" --value "ABCDEF" --tags "Key=Application,Value=RssEmailerZohoNotifier" --region us-east-1
			```
* [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html) for deployment
* Docker, also for deployment with [AWS SAM which can help avoid issues when apps depend on natively compiled dependencies](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html)

### First time setup

1. Clone this repo
1. Python virtual environment:

	```
	python -m venv .venv
	```

1. [Activate](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#create-and-use-virtual-environments) the virtual environment (Linux instructions shown):

	```
	source .venv/bin/activate
	```

1. Install requirements:

	```
	pip install -r rss/requirements.txt
	```

### Unit tests

Run tests either from:

1. VS Code using the "Test" launch configuration (recommend to avoid AWS X-Ray log spam which sets the `AWS_XRAY_SDK_ENABLED` environment variable to `false`)
1. Or the terminal using:

	```
	python -m unittest discover test
	```

### Build and deployment

1. Start Docker if the daemon is not already running
1. AWS SAM build using a container (this is set in the `build` parameters of [samlconfig.toml](samlconfig.toml))

	```sh
	sam build
	```

1. AWS deploy (this will deploy to `us-east-1` as per the [samlconfig.toml](samlconfig.toml))

	```sh
	sam deploy
	```

1. Test the deployment by invoking the Lambda function, e.g.

	```sh
	aws lambda invoke --function-name <insert_actual_function_name> --payload '{"rss_urls": ["https://www.keycloak.org/rss.xml"]}' --cli-binary-format raw-in-base64-out output.txt --region us-east-1
	```

	Where the payload might be (formatted for readability):

	```json
	{
		"rss_urls": [
			"https://www.keycloak.org/rss.xml"
		]
	}
	```
