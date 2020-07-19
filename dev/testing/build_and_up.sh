#!/bin/bash
docker-compose down
#docker volume prune
docker pull python:3.8-alpine
DUMMY=$(date +%s) docker-compose up -d --build

