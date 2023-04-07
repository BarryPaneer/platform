sudo -H -u edxapp bash << EOF
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
cat << EOF | python manage.py lms shell --settings=aws
execfile('scripts/analytics_generate_reports.py')
exit
EOF
exit
EOF
