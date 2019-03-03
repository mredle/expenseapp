#!/bin/bash
find . -type d -name __pycache__ -exec rm -r {} \+
find . -type d -name static -exec rm -r {} \+
docker rmi expenseapp:latest
docker rmi $(docker images --filter "dangling=true" -q --no-trunc)
docker build --no-cache -t expenseapp:latest .
