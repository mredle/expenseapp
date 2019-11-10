#!/bin/bash
docker-compose down
#docker volume prune
DUMMY=$(date +%s) docker-compose up -d --build

