#!/usr/bin/env zsh
#set -e  # instructs bash to immediately exit if any command has a non-zero exit status.
#set -o pipefail  # prevents errors in a pipeline from being masked
#set -u  # a reference to any variable you haven't previously defined - with the exceptions of $* and $@ - is an error

pipenv --rm && pipenv install  # remove venv and install non-dev requirements

ZIP_FILE=earning-notification-package.zip
PY_VER=3.9
LAMBDA_FUNC_NAME=test-function

rm -rf $ZIP_FILE
# get absolute directory contains the script
SCRIPT_DIR=${0:a:h}
VENV_DIR=$( pipenv --venv )/lib/python${PY_VER}/site-packages
cd $VENV_DIR && zip -r $SCRIPT_DIR/$ZIP_FILE . > /dev/null
cd $SCRIPT_DIR/src && zip -g $SCRIPT_DIR/$ZIP_FILE lambda_function.py > /dev/null
cd $SCRIPT_DIR && ls -lh $ZIP_FILE
aws lambda update-function-code --profile mfa_admin --function-name ${LAMBDA_FUNC_NAME} --zip-file fileb://${ZIP_FILE}

# finally install dev environment again
pipenv install --dev