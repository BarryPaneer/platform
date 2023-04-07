"""
Course vendor data migration.
"""

from django.contrib.auth.models import User
from xmodule.modulestore.django import modulestore


def setup():
    """
    Init work.
    """
    user = User.objects.get(username='staff')
    all_courses = modulestore().get_courses()
    for course in all_courses:
        migrate_data(course, user)


def migrate_data(course, user):
    """
    Migrate course vendor from str to list.
    """
    try:
        country = course.course_country
        if country and isinstance(country, (str, unicode)):
            course.course_country = [country]
        else:
            course.course_country = []
        modulestore().update_item(course, user.id)
    except TypeError as e:
        print "Couldn't get course country, " + str(e)


if __name__ == '__main__':
    setup()
