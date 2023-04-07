sudo -H -u www-data bash << EOF
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
python manage.py lms ilt_virtual_session_check --mode=daily --settings=aws
EOF
