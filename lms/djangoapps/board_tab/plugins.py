from django.utils.translation import ugettext_noop
from courseware.tabs import CourseTab
from student.triboo_groups import ANDERSPINK_DENIED_GROUP


class MyBoardTab(CourseTab):
    """
    The representation of the course teams view type.
    """
    type = "board"
    name = "anderspink_board"
    title = ugettext_noop("Board")
    view_name = "board"
    is_default = True
    is_hideable = True

    @classmethod
    def is_enabled(cls, course, user=None):
        user_groups = [group.name for group in user.groups.all()]
        if ANDERSPINK_DENIED_GROUP not in user_groups and len(course.anderspink_boards) > 0:
            return True

        return False
