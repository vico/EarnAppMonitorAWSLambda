
# Development memo

## Create dev environment

```bash
python3 -m pip install --user pipenv
pipenv install --dev
```

## Create zip file for AWS Lambda deployment and deploy

```bash
package_and_deploy.sh
```

## Run local Dynamodb

```bash
docker run -p 8000:8000 amazon/dynamodb-local
```