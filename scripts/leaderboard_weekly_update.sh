sudo -H -u www-data bash << EOF
source /edx/app/edxapp/edxapp_env
cd /edx/app/edxapp/edx-platform
cat << EOF | python manage.py lms shell --settings=aws
execfile('scripts/leaderboard_weekly_update.py')
exit
EOF