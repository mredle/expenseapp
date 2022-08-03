#!/bin/bash
docker-compose down
#docker volume prune
docker pull python:3.9-alpine
DUMMY=$(date +%s) docker-compose up -d --build

