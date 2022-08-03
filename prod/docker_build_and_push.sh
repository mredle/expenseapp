#!/bin/bash
sudo docker rmi expenseapp:latest
sudo docker rmi $(docker images --filter "dangling=true" -q --no-trunc)
sudo docker pull python:3.10-alpine
sudo docker build --no-cache -t mredle/expenseapp:latest ..
sudo docker push mredle/expenseapp:latest
