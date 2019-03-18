#!/bin/bash
docker rmi expenseapp:latest
docker rmi $(docker images --filter "dangling=true" -q --no-trunc)
docker build --no-cache -t mredle/expenseapp:latest ..
docker push mredle/expenseapp:latest
