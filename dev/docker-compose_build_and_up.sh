#!/bin/bash
docker-compose down
DUMMY=$(date +%s) docker-compose up -d --build

