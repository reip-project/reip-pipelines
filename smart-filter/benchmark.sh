#!/bin/bash

rm -fr logs
mkdir logs

python3 benchmark.py --throughput=small | tee 'logs/python3 benchmark.py --throughput=small.log'

python3 benchmark.py --throughput=medium | tee 'logs/python3 benchmark.py --throughput=medium.log'

python3 benchmark.py --throughput=large | tee 'logs/python3 benchmark.py --throughput=large.log'

