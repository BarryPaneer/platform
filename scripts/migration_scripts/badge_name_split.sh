sudo -H -u edxapp bash << EOF
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
cat << EOF | python manage.py cms shell --settings=aws
execfile('scripts/migration_scripts/badge_name_split.py')
exit
EOF