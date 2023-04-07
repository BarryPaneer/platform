"""
Django model specifications for the Program Enrollments API
"""
from datetime import datetime

from django.contrib.auth.models import User  # lint-amnesty, pylint: disable=imported-auth-user
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _
from model_utils.models import TimeStampedModel
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.django.models import CourseKeyField

from student.models import CourseEnrollment

from .constants import ProgramCourseEnrollmentStatuses, ProgramEnrollmentStatuses


class ProgramEnrollment(TimeStampedModel):
    """
    This is a model for Program Enrollments from the registrar service

    .. pii: PII is found in the external key for a program enrollment
    .. pii_types: other
    .. pii_retirement: local_api
    """
    STATUS_CHOICES = ProgramEnrollmentStatuses.__MODEL_CHOICES__

    class Meta:
        app_label = "program_enrollments"

        unique_together = (
            ('user', 'program_uuid'),
        )

    user = models.ForeignKey(
        User,
        null=True,
        blank=True, on_delete=models.CASCADE
    )
    program_uuid = models.UUIDField(db_index=True, null=False)
    status = models.CharField(max_length=9, choices=STATUS_CHOICES)
    # We'll add 20 Points for the `user` if he complete All Courses of the Program
    completed = models.DateTimeField(default=None, null=True)

    def clean(self):
        if not self.user:
            raise ValidationError(_('One of user must not be null.'))

    def __str__(self):
        return '[ProgramEnrollment id={}]'.format(self.id)

    def __repr__(self):
        return (  # lint-amnesty, pylint: disable=missing-format-attribute
            "<ProgramEnrollment"    # pylint: disable=missing-format-attribute
            " id={self.id}"
            " user={self.user!r}"
            " program_uuid={self.program_uuid!r}"
            " status={self.status!r}"
            ">"
        ).format(self=self)

    @classmethod
    def is_enrolled(cls, user, program_uuid):
        """
        Returns True if the user is enrolled in the program (the entry must exist
        and it must have `is_active=True`). Otherwise, returns False.

        `user` is a Django User object. If it hasn't been saved yet (no `.id`
               attribute), this method will automatically save it before
               adding an enrollment for it.

        `program_uuid` is our usual program id string (UUID)
        """
        if user.is_anonymous:
            return False

        try:
            cls.objects.get(user=user, program_uuid=program_uuid, status__in=ProgramEnrollmentStatuses.__ACTIVE__)
            return True
        except cls.DoesNotExist:
            return False


class ProgramCourseEnrollment(TimeStampedModel):
    """
    This is a model to represent a learner's enrollment in a course
    in the context of a program from the registrar service

    .. no_pii:
    """
    STATUS_CHOICES = ProgramCourseEnrollmentStatuses.__MODEL_CHOICES__

    class Meta:
        app_label = "program_enrollments"

        # For each program enrollment, there may be only one
        # waiting program-course enrollment per course key.
        unique_together = (
            ('program_enrollment', 'course_key'),
        )

    program_enrollment = models.ForeignKey(
        ProgramEnrollment,
        on_delete=models.CASCADE,
        related_name="program_course_enrollments"
    )
    # In Django 2.x, we should add a conditional unique constraint to this field so
    # no duplicated tuple of (course_enrollment_id, status=active) exists
    # MST-168 is the Jira ticket to accomplish this once Django is upgraded
    course_enrollment = models.ForeignKey(
        CourseEnrollment,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    course_key = CourseKeyField(max_length=255)
    status = models.CharField(max_length=9, choices=STATUS_CHOICES)

    @property
    def is_active(self):
        return self.status == ProgramCourseEnrollmentStatuses.ACTIVE

    def __str__(self):
        return '[ProgramCourseEnrollment id={}]'.format(self.id)

    def __repr__(self):
        return (  # lint-amnesty, pylint: disable=missing-format-attribute
            "<ProgramCourseEnrollment"  # pylint: disable=missing-format-attribute
            " id={self.id}"
            " program_enrollment={self.program_enrollment!r}"
            " course_enrollment=<{self.course_enrollment}>"
            " course_key={self.course_key}"
            " status={self.status!r}"
            ">"
        ).format(self=self)

    @classmethod
    def get_programs_courses_by_completed_status(cls, user, course_id, filter_uncompleted):
        """Return courses list of uncompleted programs for speicifed user OR course_id

            @param user:                    user instance
            @type user:                     django.contrib.auth.models.User
            @param course_id:               course id string
            @type course_id:                string
            @param filter_uncompleted:      filter flag: uncompleted(True)/completed(False) programs
            @type filter_uncompleted:       boolean
            @return:                        records of programs' courses enrollment
            @rtype:                         class ProgramCourseEnrollment

        """
        course_key = CourseKey.from_string(course_id) \
            if isinstance(course_id, str) \
            else course_id

        program_enrollment_ids = ProgramCourseEnrollment.objects.filter(
            program_enrollment__completed__isnull=filter_uncompleted,
            program_enrollment__status='enrolled',
            status='active',                                # program's courses' status == 'active'
            program_enrollment__user=user,
            course_key=course_key
        ).values(
            'program_enrollment_id'
        )

        return ProgramCourseEnrollment.objects.filter(
            program_enrollment_id__in=models.Subquery(
                program_enrollment_ids
            )
        ).order_by(
            'program_enrollment_id'
        ).all()

    @classmethod
    def update_programs_completion_status(cls, user, completed_course_id=None, uncompleted_course_id=None):
        """Update programs completed status (completed OR uncompleted) with course_id

            @param user:                    user instance
            @type user:                     django.contrib.auth.models.User
            @param completed_course_id:     completed course id string
            @type completed_course_id:      string
            @param uncompleted_course_id:   completed course id string
            @type uncompleted_course_id:    string
            @return:                        Affected number of completed/uncompleted programs
            @rtype:                         integer

        """
        if not completed_course_id and not uncompleted_course_id:
            raise ValidationError(_('Please pass course_id of programs'))

        program_enrollments = set()

        if completed_course_id:
            uncompleted_programs_enrollments = cls.get_programs_courses_by_completed_status(
                user, completed_course_id, filter_uncompleted=True
            )
            for enrollment in uncompleted_programs_enrollments:
                if enrollment.program_enrollment not in program_enrollments and \
                        not enrollment.program_enrollment.completed:
                    # Assign field `program_enrollment.completed` with a datetime value
                    enrollment.program_enrollment.completed = datetime.today()
                    enrollment.program_enrollment.save()
                    program_enrollments.add(enrollment.program_enrollment)

            return len(program_enrollments)

        elif uncompleted_course_id:
            completed_programs_enrollments = cls.get_programs_courses_by_completed_status(
                user, uncompleted_course_id, filter_uncompleted=False
            )

            for enrollment in completed_programs_enrollments:
                if enrollment.program_enrollment not in program_enrollments:
                    # Assign field `program_enrollment.completed` with `None`
                    enrollment.program_enrollment.completed = None
                    enrollment.program_enrollment.save()
                    program_enrollments.add(enrollment.program_enrollment)

            return len(program_enrollments)

        return 0
