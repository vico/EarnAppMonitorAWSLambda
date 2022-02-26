#!/usr/bin/env bash
set -e  # instructs bash to immediately exit if any command has a non-zero exit status.
set -o pipefail  # prevents errors in a pipeline from being masked
set -u  # a reference to any variable you haven't previously defined - with the exceptions of $* and $@ - is an error

pipenv --rm && pipenv install  # remove venv and install non-dev requirements

ZIP_FILE=earning-notification-package.zip
PY_VER=3.9
LAMBDA_FUNC_NAME=test-function

rm -rf $ZIP_FILE
# SO: a double dash (--) is used in most Bash built-in commands and many other commands to signify
#   the end of command options, after which only positional arguments are accepted.
# ${BASH_SOURCE[0]} (or, more simply, $BASH_SOURCE ) contains the (potentially relative) path of
#   the containing script in all invocation scenarios, notably also when the script is sourced, which is not true for $0.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
VENV_DIR=$( pipenv --venv )/lib/python${PY_VER}/site-packages
cd $VENV_DIR && zip -r $SCRIPT_DIR/$ZIP_FILE . > /dev/null
cd $SCRIPT_DIR/src && zip -g $SCRIPT_DIR/$ZIP_FILE lambda_function.py > /dev/null
cd $SCRIPT_DIR && ls -lh $ZIP_FILE
aws lambda update-function-code --function-name ${LAMBDA_FUNC_NAME} --zip-file fileb://${ZIP_FILE}