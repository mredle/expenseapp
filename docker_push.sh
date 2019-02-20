#!/bin/bash
docker rmi mredle/expenseapp:latest
docker tag expenseapp:latest mredle/expenseapp:latest
docker push mredle/expenseapp:latest
