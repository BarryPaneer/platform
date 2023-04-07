sudo -H -u www-data bash << EOF
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
cat << EOF | python manage.py cms shell --settings=aws
execfile('scripts/rename_mcq_blocks.py')
exit
EOF