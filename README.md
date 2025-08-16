# Simple RSS Mailer

Periodically checks an RSS feed and emails the articles.

## Limitations

Functional:

* This is a simple project aimed at a single subscriber so only one email address can be configured.


## TODOs

* Add AWS X-ray so we can evaluate performance of:
	* Lambda function overall
	* RSS retrieval
	* Diffing
	* Notifications
* Lambda layers so it's faster to deploy


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

1. VS Code using the "Test" launch configuration
1. The terminal using:

	```
	python -m unittest discover test
	```

### Build and deployment

1. Start Docker if the daemon is not already running
1. AWS SAM build using a container (this is set in the `build` parameters of [samlconfig.toml](samlconfig.toml))

	```
	sam build
	```

1. AWS deploy (this will deploy to `us-east-1` as per the [samlconfig.toml](samlconfig.toml))

	```
	sam deploy
	```