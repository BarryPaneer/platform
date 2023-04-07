# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.db.models import Count
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration
from student.models import CourseEnrollment, UserProfile
from student.roles import LT_TESTER


def migrate_lt_accounts():
    lt_accounts = UserProfile.objects.filter(user__email__endswith="learning-tribes.com")
    lt_accounts.update(org=LT_TESTER)


def migrate_normal_users():
    site_configs = SiteConfiguration.objects.filter(enabled=True)
    # case that it's a multi-microsites servers (lms+studio)
    if len(site_configs) > 2:
        org_combinations = []
        for configuration in site_configs:
            course_org_filter = configuration.get_value('course_org_filter', [])
            if not isinstance(course_org_filter, list):
                course_org_filter = [course_org_filter]
            course_org_filter = sorted(course_org_filter)
            if not course_org_filter in org_combinations:
                org_combinations.append(course_org_filter)

        users = User.objects.exclude(is_active=False, email__endswith="learning-tribes.com").only("id")
        for user in users:
            enrollments = CourseEnrollment.objects.filter(user_id=user.id, is_active=True).values(
                "course_id__org"
            ).annotate(org_count=Count("course_id__org")).order_by("-org_count")
            if not enrollments.exists():
                break
            orgs = list(enrollments)
            tmp_orgs = org_combinations
            for org in orgs:
                potential_orgs = [i for i in tmp_orgs if org["course_id__org"] in i]
                if not potential_orgs:
                    continue
                if len(potential_orgs) == 1:
                    break
                else:
                    tmp_orgs = potential_orgs
            if len(potential_orgs) != 1:
                final_org = "+".join(potential_orgs)
            else:
                final_org = orgs[0]["course_id__org"]
            user.profile.org = final_org
            user.profile.save()
