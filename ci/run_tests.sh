#!/bin/bash -x
. /edx/app/edxapp/edxapp_env

. /edx/app/edxapp/nodeenvs/edxapp/bin/activate
. /edx/app/edxapp/venvs/edxapp/bin/activate

cd /edx/app/edxapp/edx-platform

apt-get install -y `cat /edx/app/edxapp/edx-platform/requirements/system/ubuntu/third-party-apt.txt`
pip install -r /edx/app/edxapp/edx-platform/requirements/edx/third-party.txt
pip install -e .
export TESTING="True"
python scripts/trans.py --all --settings=devstack_docker
paver test_system -C -c "--cov-append" --fasttest
paver test_lib -C -c "--cov-append"
paver coverage
