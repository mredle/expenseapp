#!/bin/bash
sudo docker-compose down
#docker volume prune
sudo docker pull python:3.10-alpine
sudo docker build --no-cache -t expenseapp:latest ../.. && sudo docker-compose up -d

