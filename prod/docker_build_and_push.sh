#!/bin/bash
docker rmi expenseapp:latest
docker rmi $(docker images --filter "dangling=true" -q --no-trunc)
docker pull python:3.8-alpine
docker build --no-cache -t mredle/expenseapp:latest ..
docker push mredle/expenseapp:latest
