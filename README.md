# Simple RSS Mailer

Periodically checks an RSS feed and emails the articles.

## Limitations

Functional:

* This is a simple project aimed at a single subscriber so only one email address can be configured.


## TODOs

* Lambda layers so it's faster to deploy
* Needs AWS SES (or another email provider) to send HTML-formatted emails. Currently just sends a basic email notification containing the article's title, publication date, and link
* Feedparser is slow. Maybe use https://github.com/kagisearch/fastfeedparser instead?


## Developing

### Requirements

* Python 3.13
* AWS account
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
	pip install -r function/requirements.txt
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
