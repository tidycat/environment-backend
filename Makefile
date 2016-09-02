current_dir := $(shell pwd)
ENV=$(current_dir)/env

all: help

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

# Utility target for checking required parameters
guard-%:
	@if [ "$($*)" = '' ]; then \
     echo "Missing required $* variable."; \
     exit 1; \
   fi;

.PHONY: clean
clean:  ## Clean out some superficial crust
	find . -name "*.pyc" -exec /bin/rm -rf {} \;
	rm -rf $(ENV)

.PHONY: clean-all
clean-all: clean  ## Burn everything to the ground
	rm -rf build
	rm -rf deploy-env
	rm -rf lambda.zip
	rm -rf docs/_build
	rm -f .coverage
	rm -f dynamodb_sample_data/shared-local-instance.db

env: clean
	test -d $(ENV) || virtualenv $(ENV)

.PHONY: install
install: env  ## Install project dependencies
	$(ENV)/bin/pip install -r requirements.txt
	$(ENV)/bin/pip install -r requirements-dev.txt

.PHONY: checkstyle
checkstyle:  ## Run the linters locally
	$(ENV)/bin/flake8 --max-complexity 10 server.py
	$(ENV)/bin/flake8 --max-complexity 10 environment_backend
	$(ENV)/bin/flake8 --max-complexity 10 tests

.PHONY: unit-test
unit-test:  ## Run the unit-tests locally
	rm -f .coverage
	$(ENV)/bin/nosetests \
		-v \
		--with-coverage \
		--cover-package=environment_backend \
		tests

.PHONY: test
test: checkstyle unit-test  ## Run all the acceptance tests locally
	@echo "Tests look good!"

.PHONY: server
server:  ## Run the local development server
	$(ENV)/bin/python server.py 0.0.0.0 8082

# e.g. PART=major make release
# e.g. PART=minor make release
# e.g. PART=patch make release
.PHONY: release
release: guard-PART  ## Cut a new release! (e.g. PART=patch make release)
	$(ENV)/bin/bumpversion $(PART)
	@echo "Now manually run: git push && git push --tags"

.PHONY: lambda
lambda: clean-all  ## Prepare the lambda.zip file for AWS Lambda
	mkdir build
	pip install -r requirements.txt -t build
	cp -R environment_backend build/
	find build -type d -exec chmod ugo+rx {} \;
	find build -type f -exec chmod ugo+r {} \;
	find build -name "*.pyc" -exec /bin/rm -rf {} \;
	cd build; zip -Xr ../lambda.zip *

.PHONY: local-dynamodb
local-dynamodb:  ## Run a local instance of DynamoDB
	@mkdir -p /tmp/local-dynamodb
	@mkdir -p ./dynamodb_sample_data
	@test -f /tmp/local-dynamodb/DynamoDBLocal.jar || (wget -O /tmp/dynamodb_local_latest.tar.gz http://dynamodb-local.s3-website-us-west-2.amazonaws.com/dynamodb_local_latest.tar.gz && tar -xf /tmp/dynamodb_local_latest.tar.gz -C /tmp/local-dynamodb && rm -f /tmp/dynamodb_local_latest.tar.gz)
	@java \
		-Djava.library.path=/tmp/local-dynamodb/DynamoDBLocal_lib \
		-jar /tmp/local-dynamodb/DynamoDBLocal.jar \
		-sharedDb \
		-dbPath ./dynamodb_sample_data \
		-delayTransientStatuses \
		-port ${DYNAMODB_LOCAL_PORT}

.PHONY: init-local-dynamodb
init-local-dynamodb:  ## Initialize the local instance of DynamoDB
	aws dynamodb create-table \
		--endpoint-url ${DYNAMODB_ENDPOINT_URL} \
		--table-name "${DYNAMODB_TABLE_NAME_PREFIX}_environment" \
		--attribute-definitions \
			AttributeName=user_id,AttributeType=N \
		--key-schema \
			AttributeName=user_id,KeyType=HASH \
		--provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1

# This will need the following environment variables:
# AWS_ACCESS_KEY_ID
# AWS_SECRET_ACCESS_KEY
# AWS_DEFAULT_REGION
# LAMBDA_FUNCTION_NAME
.PHONY: deploy-local-lambda
deploy-local-lambda: lambda  ## Helper target to upload and deploy a local version of lambda.zip
	aws lambda \
		update-function-code \
		--function-name "${LAMBDA_FUNCTION_NAME}" \
		--zip-file fileb://lambda.zip \
		--publish
