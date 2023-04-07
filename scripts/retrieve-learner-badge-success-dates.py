from django.contrib.auth.models import User
from django.utils import timezone
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.content.course_structures.api.v0.api import course_structure
from xmodule.modulestore.django import modulestore
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from student.models import CourseEnrollment
from completion.models import BlockCompletion
from django.db.models import Max
from opaque_keys.edx.keys import UsageKey
from triboo_analytics.models import Badge, LearnerBadgeSuccess

def get_outline(course_key):
    outline = course_structure(course_key)
    outline = outline['blocks']
    my_outline = {}
    for block_id, block in outline.iteritems():
        if block['type'] == "chapter":
            children = {}
            for child in block['children']:
                children[child] = {'pretty': "", "children": {}}
            my_outline[block_id] = {
                'pretty': "%s < %s > - %s" % (block_id, block['type'], block['display_name']),
                'children': children
            }
    for block_id, block in outline.iteritems():
        if block['type'] == "sequential":
            children = {}
            for child in block['children']:
                children[child] = {'pretty': "", "children": {}}
            for chapter_id, chapter in my_outline.iteritems():
                if block_id in chapter['children'].keys():
                    chapter['children'][block_id]['pretty'] = "%s < %s > - %s" % (block_id, block['type'], block['display_name'])
                    chapter['children'][block_id]['children'] = children
    for block_id, block in outline.iteritems():
        if block['type'] == "vertical":
            children = {}
            for child in block['children']:
                children[child] = {'pretty': ""}
            for chapter_id, chapter in my_outline.iteritems():
                for sequential_id, sequential in chapter['children'].iteritems():
                    if block_id in sequential['children'].keys():
                        sequential['children'][block_id]['pretty'] = "%s < %s > - %s" % (block_id, block['type'], block['display_name'])
                        sequential['children'][block_id]['children'] = children
    for block_id, block in outline.iteritems():
        if block['type'] not in ["chapter", "sequential", "vertical"]:
            children = {}
            for chapter_id, chapter in my_outline.iteritems():
                for sequential_id, sequential in chapter['children'].iteritems():
                    for vertical_id, vertical in sequential['children'].iteritems():
                        if block_id in vertical['children'].keys():
                            vertical['children'][block_id]['pretty'] = "%s < %s > - %s" % (block_id, block['type'], block['display_name'])
                            vertical['children'][block_id]['type'] = block['type']
    return my_outline


def pretty_print_outline(my_outline):
    for chapter_id, chapter in my_outline.iteritems():
        print chapter['pretty']
        for sequential_id, sequential in chapter['children'].iteritems():
            print "    |____ %s" % sequential['pretty']
            for vertical_id, vertical in sequential['children'].iteritems():
                print "        |____ %s" % vertical['pretty']
                for block_id, block in vertical['children'].iteritems():
                    print "            |____ %s (%s)" % (block['pretty'], block['graded'])
                    


def get_completable_children(outline, section):
    completable_children = []
    for chapter_id, chapter in my_outline.iteritems():
        for sequential_id, sequential in chapter['children'].iteritems():
            if ("%s" % sequential_id) == ("%s" % section):
                for vertical_id, vertical in sequential['children'].iteritems():
                    for block_id, block in vertical['children'].iteritems():
                        if block['type'] not in ["discussion", "html"]:
                            block_key = UsageKey.from_string(block_id)
                            completable_children.append(block_key)
                return completable_children


try:
    user = User.objects.get(username="LaetitiaP")
except User.DoesNotExist:
    user = User.objects.get(username="edx")
course_grade_factory = CourseGradeFactory()
yesterday = timezone.now() + timezone.timedelta(days=-1)
overviews = CourseOverview.objects.filter(start__lte=yesterday).only('id')
for overview in overviews:
    print "%s -- %s" % (overview.id, overview.display_name.encode('utf-8'))
    course = modulestore().get_course(overview.id)
    my_outline = get_outline(overview.id)
    # pretty_print_outline(my_outline)
    grading_rules = course.raw_grader
    if grading_rules:
        badges = {}
        grading_rules_dict = {}
        for rule in grading_rules:
            grading_rules_dict[rule['type']] = rule['threshold'] * 100

        grade_summary = course_grade_factory.read(user, course)
        chapter_grades = grade_summary.chapter_grades.values()
        i = 0
        for chapter in chapter_grades:
            for section in chapter['sections']:
                if section.graded and section.format in grading_rules_dict.keys():
                    i += 1
                    badge_hash = Badge.get_badge_hash(section.format, chapter['url_name'], section.url_name)
                    # print "Badge %d: %s - %s (%s - %s) >= %s" % (i, section.format, section.display_name, chapter['url_name'], section.url_name,
                    #     grading_rules_dict[section.format])

                    badge = Badge.objects.filter(course_id=overview.id, badge_hash=badge_hash).first()
                    if not badge:
                        badge, _ = Badge.objects.update_or_create(course_id=overview.id,
                                                               badge_hash=badge_hash,
                                                               defaults={'order': i,
                                                                         'grading_rule': section.format,
                                                                         'section_name': section.display_name,
                                                                         'threshold': grading_rules_dict[section.format]})

                    completable_children = get_completable_children(my_outline, section.location)
                    badges[badge_hash] = {'badge': badge, 'sections': completable_children}

        enrollments = CourseEnrollment.objects.filter(course_id=overview.id, is_active=True, user__is_active=True)
        for enrollment in enrollments:
            grade_summary = CourseGradeFactory().read(enrollment.user, course)
            chapter_grades = grade_summary.chapter_grades.values()
            for chapter in chapter_grades:
                for section in chapter['sections']:
                    if section.graded:
                        badge_hash = Badge.get_badge_hash(section.format, chapter['url_name'], section.url_name)
                        # print "attempted=%s override=%s result=%s threshold=%s" % (section.attempted_graded,
                        #                                                            section.override,
                        #                                                            section.percent_graded,
                        #                                                            badges[badge_hash]['badge'].threshold)
                        if section.attempted_graded or section.override is not None:
                            if (section.percent_graded * 100) >= badges[badge_hash]['badge'].threshold:
                                block_keys = badges[badge_hash]['sections']
                                success_date = BlockCompletion.objects.filter(course_key=overview.id,
                                                               user_id=enrollment.user.id,
                                                               block_key__in=block_keys).aggregate(Max('modified')).get('modified__max')
                                if success_date:
                                    LearnerBadgeSuccess.objects.update_or_create(user=user, badge=badge, defaults={'success_date': success_date})

                        #         print "user %s SUCCESS on badge %s (%s) %s" % (enrollment.user.username, section.format, section.display_name, success_date)
                        #     else:
                        #         print "user %s FAILED on badge %s (%s)" % (enrollment.user.username, section.format, section.display_name)
                        # else:
                        #     print "user %s NOT ATTEMPTED badge %s (%s)" % (enrollment.user.username, section.format, section.display_name)

    else:
        print "    NO grading rules"

