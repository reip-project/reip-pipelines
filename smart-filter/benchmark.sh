#!/bin/bash

rm -fr logs
mkdir logs

python3 benchmark.py --stereo=True --threads_only=False --all_processes=False --throughput=small --config_id=0 | tee 'logs/config_0.log'

python3 benchmark.py --stereo=True --threads_only=False --all_processes=False --throughput=medium --config_id=1 | tee 'logs/config_1.log'

python3 benchmark.py --stereo=True --threads_only=False --all_processes=False --throughput=large --config_id=2 | tee 'logs/config_2.log'

python3 benchmark.py --stereo=True --threads_only=True --all_processes=False --throughput=small --config_id=3 | tee 'logs/config_3.log'

python3 benchmark.py --stereo=True --threads_only=True --all_processes=False --throughput=medium --config_id=4 | tee 'logs/config_4.log'

python3 benchmark.py --stereo=True --threads_only=True --all_processes=False --throughput=large --config_id=5 | tee 'logs/config_5.log'

python3 benchmark.py --stereo=True --threads_only=False --all_processes=True --throughput=small --config_id=6 | tee 'logs/config_6.log'

python3 benchmark.py --stereo=True --threads_only=False --all_processes=True --throughput=medium --config_id=7 | tee 'logs/config_7.log'

python3 benchmark.py --stereo=True --threads_only=False --all_processes=True --throughput=large --config_id=8 | tee 'logs/config_8.log'

python3 benchmark.py --stereo=False --threads_only=False --all_processes=False --throughput=small --config_id=9 | tee 'logs/config_9.log'

python3 benchmark.py --stereo=False --threads_only=False --all_processes=False --throughput=medium --config_id=10 | tee 'logs/config_10.log'

python3 benchmark.py --stereo=False --threads_only=False --all_processes=False --throughput=large --config_id=11 | tee 'logs/config_11.log'

python3 benchmark.py --stereo=False --threads_only=True --all_processes=False --throughput=small --config_id=12 | tee 'logs/config_12.log'

python3 benchmark.py --stereo=False --threads_only=True --all_processes=False --throughput=medium --config_id=13 | tee 'logs/config_13.log'

python3 benchmark.py --stereo=False --threads_only=True --all_processes=False --throughput=large --config_id=14 | tee 'logs/config_14.log'

python3 benchmark.py --stereo=False --threads_only=False --all_processes=True --throughput=small --config_id=15 | tee 'logs/config_15.log'

python3 benchmark.py --stereo=False --threads_only=False --all_processes=True --throughput=medium --config_id=16 | tee 'logs/config_16.log'

python3 benchmark.py --stereo=False --threads_only=False --all_processes=True --throughput=large --config_id=17 | tee 'logs/config_17.log'

