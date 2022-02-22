
# Development memo

## Create dev environment

```bash
pyenv install 3.9.0
pyenv local 3.9.0
python3 -m pip install --user pipenv
pipenv sync --dev
cp sample.env env.json
```

Modify EarnApp Dashboard authentication token and Discord's webhook url in `env.json` file
and save.

Run Lambda function in local using SAM CLI:

```bash
sam local invoke -n env.json
```

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

## AWS Deployment

```bash
pipenv lock -r > src/requirements.txt
sam build  # build artifacts

sam deploy --template-file ./template.yml --parameter-overrides  $(jq -r '.Parameters | to_entries[] | "\(.key)=\(.value) "' env.json) --resolve-s3
```

## References
- https://blog.serverworks.co.jp/2020/12/17/001653
- https://qiita.com/ytaka95/items/5899c44c85e71fdc5273
- https://github.com/amazon-archives/serverless-app-examples/blob/master/python/dynamodb-process-stream-python3/template.yaml
- https://dev.classmethod.jp/articles/check-when-creating-cloudwatchevents-and-lambda-with-cloudformation/