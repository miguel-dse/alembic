#!/usr/bin/env bash

python -m build

python -m twine upload \
--repository-url http://192.168.108.51:9090/ \
--username foo \
--password bar \
--non-interactive \
dist/*
