#!/bin/bash

echo "Running isort (import sorting)..."
isort mFinix
isort --check-only . || exit 1

echo "Running black (code formatting)..."
black mFinix
black mFinix --check || exit 1

echo "Running pylint (static code analysis)..."
pylint mFinix --fail-under 5 --fail-on E