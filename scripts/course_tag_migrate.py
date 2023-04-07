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
        vendor = course.vendor
        if vendor and isinstance(vendor, (str, unicode)):
            course.vendor = [vendor]
        elif vendor and isinstance(vendor, list):
            pass
        else:
            course.vendor = []
        modulestore().update_item(course, user.id)
    except TypeError as e:
        print "Couldn't get course vendor, " + str(e)


if __name__ == '__main__':
    setup()
