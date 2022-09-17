
# Development memo

## AWS account preparation

```bash
aws cloudformation create-stack \
    --profile mfa_admin \
    --stack-name iam-settings1 \
    --template-body file://iam_settings.yml \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameters file://./prod.json
```

or you can run CloudFormation by upload the file `iam_settings.yml` to AWS Console interface.

Download access_key and secret_access_key for `dev` IAM user created above.

In file `~/.aws/credentials`, add developer `aws_access_key` and `aws_secret_access_key`,
looks like the following (replace the XX and qqq with real access_key and real secret_access_key):

```yaml
[dev]
aws_access_key_id = XX
aws_secret_access_key = qqq
```

Then, in file `~/.aws/config`, add a profile with admin role so that the `dev` user can switch to.
Let's call it `mfa_admin`. (replace 111111111111 with real account number)

```yaml
[default]
region = ap-northeast-1
output = text

[profile mfa_admin]
region = ap-northeast-1
output = text
source_profile = dev
mfa_serial = arn:aws:iam::111111111111:mfa/dev
role_arn = arn:aws:iam::111111111111:role/AdminRole
```

## Create dev environment

```bash
pyenv install 3.9.0
pyenv local 3.9.0
python3 -m pip install --user pipenv
pipenv sync --dev
cp sample_env.json env.json      # for production
cp sample_env.json dev_env.json  # for development
```


Modify EarnApp Dashboard authentication token and Discord's webhook url in `env.json` and `dev_env.json` file
and save. Remember to get a new token from Earnapp site.


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

### Create tables and populate data for local dev

```bash
pipenv shell
python create_table.py
```

Check table list in local DynamoDB

```bash
aws --profile dev dynamodb list-tables --endpoint-url http://localhost:8000 --region ap-northeast-1
```

Run Lambda function in local environment without SAM:

```bash
pipenv shell
# to run function in local environment, it may need to modify lambda_function.py to use dev profile.
python lambda_function.py
```

Run Lambda function local with SAM

 Remember to set endpoint of local DynamoDB to `http://172.17.0.1:8000` where the IP can be checked
by running `ip addr show docker0`

```bash
sam build  && sam local invoke --profile dev  \
  --docker-network bridge --docker-network bridge --parameter-overrides \
  $(jq -r '.Parameters | to_entries[] | "\(.key)=\(.value) "' dev_env.json)
```


## AWS Deployment

```bash
pipenv lock -r > src/requirements.txt
sam build  # build artifacts

sam deploy --profile mfa_admin --template-file ./template.yml \
 --parameter-overrides  $(jq -r '.Parameters | to_entries[] | "\(.key)=\(.value) "' env.json) --resolve-s3
```

## Publish application to AWS Serverless Application Repository

Package the application (using admin role)

```bash
sam package --profile mfa_admin --template-file template.yml --output-template-file packaged.yml --s3-bucket earnappdiscord
```

and then publish it.

```bash
sam publish --profile mfa_admin --template packaged.yml --region ap-northeast-1
```


## References
- https://blog.serverworks.co.jp/2020/12/17/001653
- https://qiita.com/ytaka95/items/5899c44c85e71fdc5273
- https://github.com/amazon-archives/serverless-app-examples/blob/master/python/dynamodb-process-stream-python3/template.yaml
- https://dev.classmethod.jp/articles/check-when-creating-cloudwatchevents-and-lambda-with-cloudformation/