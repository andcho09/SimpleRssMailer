# Simple RSS Mailer

Periodically checks an RSS feed and emails the articles.

## Limitations

Lots

* This is a simple project aimed at a single subscriber so only one email address can be configured.

## Developing

### Requirements

* Python 3.13
* AWS account
* [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html) for deployment

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
	pip install -r requirements.txt
	```

### Unit tests

Run tests either from:

1. VS Code using the "Test" launch configuration
1. The terminal using:

	```
	python -m unittest discover test
	```