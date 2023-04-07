sudo -H -u edxapp bash << EOF
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
python manage.py lms fetch_edflex_data --settings=aws
python manage.py lms fetch_new_edflex_data --settings=aws
python manage.py lms update_resources --settings=aws
EOF
