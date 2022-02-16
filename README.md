
# Development memo

## Create dev environment

```bash
python3 -m pip install --user pipenv
pipenv install --dev
cp sample.env .env
```

Modify EarnApp Dashboard authentication token and Discord's webhook url in `.env` file
and save.

## Create zip file for AWS Lambda deployment and deploy

Recreate venv to reduce the size of deployment file.
```bash
pipenv --rm   # rm venv
pipenv install  # install the venv again
```

Run bash script to create zip file and deploy to AWS Lambda:

```bash
package_and_deploy.sh
```

## Run local Dynamodb

```bash
docker run -p 8000:8000 amazon/dynamodb-local
```

Check table list in local DynamoDB

```bash
aws dynamodb list-tables --endpoint-url http://localhost:8000
```