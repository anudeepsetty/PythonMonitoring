#!/bin/bash

perl /apps/c1/scripts/logstashMetricCollector.pl

if [ $? -eq 0 ]; then
    echo "Successfully processed"
else
    echo "Error: Failed to process"
fi
