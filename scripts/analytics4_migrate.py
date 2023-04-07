import json
import logging
import time
from django.utils import timezone
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from student.models import CourseEnrollment
from triboo_analytics.models import (
    dtdump,
    LearnerCourseJsonReport,
    LearnerCourseDailyReport,
)

logger = logging.getLogger("triboo_analytics")
log_handler = logging.handlers.TimedRotatingFileHandler('/edx/var/log/lms/analytics.log',
                                                        when='W0',
                                                        backupCount=5,
                                                        encoding='utf-8')
log_formatter = logging.Formatter('%(asctime)s %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)
logger.addHandler(log_handler)


yesterday = timezone.now() + timezone.timedelta(days=-1)
overviews = CourseOverview.objects.filter(start__lte=yesterday).only('id')
nb_courses = len(overviews)
i = 0
for o in overviews:
    i += 1
    enrollments = CourseEnrollment.objects.filter(is_active=True,
                                                  course_id=o.id,
                                                  user__is_active=True)
    nb_enrollments = len(enrollments)
    logger.info("%s (%d / %d): %d enrollments" % (o.id, i, nb_courses, nb_enrollments))
    j = 0
    for e in enrollments:
        j += 1
        if j == nb_enrollments or j % 10000 == 0:
            logger.info(j)
        reports = LearnerCourseDailyReport.objects.filter(user=e.user,
                                                          course_id=e.course_id).order_by('created')
        records = {}
        for report in reports:
            record = {
                "status": report.status,
                "progress": report.progress,
                "badges": report.badges,
                "current_score": report.current_score,
                "posts": report.posts,
                "total_time_spent": report.total_time_spent,
                "enrollment_date": dtdump(report.enrollment_date) if report.enrollment_date else None,
                "completion_date": dtdump(report.completion_date) if report.completion_date else None}
            records[report.created.strftime('%Y-%m-%d')] = record
        last_report = reports.last()
        LearnerCourseJsonReport.objects.update_or_create(user=e.user,
                                                         course_id=e.course_id,
                                                         defaults={'org': e.course_id.org,
                                                                   'status': last_report.status,
                                                                   'progress': last_report.progress,
                                                                   'badges': last_report.badges,
                                                                   'current_score': last_report.current_score,
                                                                   'posts': last_report.posts,
                                                                   'total_time_spent': last_report.total_time_spent,
                                                                   'enrollment_date': last_report.enrollment_date,
                                                                   'completion_date': last_report.completion_date,
                                                                   'records': json.dumps(records)})


