
# Development memo

## Create dev environment

```bash
python3 -m pip install --user pipenv
pipenv install --dev
```

## Create zip file for AWS Lambda deployment

```bash
# add libraries to zip file
cd venv/lib/python3.9/site-packages
zip -r ../../../../earning-notification-package.zip .
# then add application file to zip file
cd ../../../../
zip -g earning-notification-package.zip lambda_function.py
# finally upload the zip file to AWS Lambda function `test-function`
aws lambda update-function-code --function-name test-function --zip-file fileb://earning-notification-package.zip
```

