#!/bin/bash

prog_name="pronunciation-dict-creation-cli"
cli_path=src/pronunciation_dict_creation/cli.py

mkdir -p ./dist

pipenv run cxfreeze \
  -O \
  --compress \
  --target-dir=dist \
  --bin-includes "libffi.so" \
  --target-name=cli \
  $cli_path

cd dist
zip $prog_name-linux.zip ./ -r
cd ..
echo "zipped."