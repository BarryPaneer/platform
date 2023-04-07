"""Interface for adding certificate generation tasks to the XQueue. """
import json
import logging
import os
import random
from collections import OrderedDict
from uuid import uuid4

import lxml.html
from django.conf import settings
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import ugettext as _, override as override_language
from django.test.client import RequestFactory
from lxml.etree import ParserError, XMLSyntaxError
from requests.auth import HTTPBasicAuth

from capa.xqueue_interface import XQueueInterface, make_hashkey, make_xheader
from lms.djangoapps.certificates.models import CertificateStatuses as status
from lms.djangoapps.certificates.models import (
    CertificateWhitelist,
    ExampleCertificate,
    GeneratedCertificate,
    certificate_status_for_student,
    CertificatePdfConfig
)
from course_modes.models import CourseMode
from instructor.enrollment import get_user_email_language
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from lms.djangoapps.verify_student.services import IDVerificationService
from student.models import CourseEnrollment, UserProfile
from util.date_utils import strftime_localized
from xmodule.modulestore.django import modulestore
from openedx.core.djangoapps.models.course_details import CourseDetails

LOGGER = logging.getLogger(__name__)


class XQueueAddToQueueError(Exception):
    """An error occurred when adding a certificate task to the queue. """

    def __init__(self, error_code, error_msg):
        self.error_code = error_code
        self.error_msg = error_msg
        super(XQueueAddToQueueError, self).__init__(unicode(self))

    def __unicode__(self):
        return (
            u"Could not add certificate to the XQueue.  "
            u"The error code was '{code}' and the message was '{msg}'."
        ).format(
            code=self.error_code,
            msg=self.error_msg
        )


class XQueueCertInterface(object):
    """
    XQueueCertificateInterface provides an
    interface to the xqueue server for
    managing student certificates.

    Instantiating an object will create a new
    connection to the queue server.

    See models.py for valid state transitions,
    summary of methods:

       add_cert:   Add a new certificate.  Puts a single
                   request on the queue for the student/course.
                   Once the certificate is generated a post
                   will be made to the update_certificate
                   view which will save the certificate
                   download URL.

       regen_cert: Regenerate an existing certificate.
                   For a user that already has a certificate
                   this will delete the existing one and
                   generate a new cert.


       del_cert:   Delete an existing certificate
                   For a user that already has a certificate
                   this will delete his cert.

    """

    def __init__(self, request=None):

        # Get basic auth (username/password) for
        # xqueue connection if it's in the settings

        if settings.XQUEUE_INTERFACE.get('basic_auth') is not None:
            requests_auth = HTTPBasicAuth(
                *settings.XQUEUE_INTERFACE['basic_auth'])
        else:
            requests_auth = None

        if request is None:
            factory = RequestFactory()
            self.request = factory.get('/')
        else:
            self.request = request

        self.xqueue_interface = XQueueInterface(
            settings.XQUEUE_INTERFACE['url'],
            settings.XQUEUE_INTERFACE['django_auth'],
            requests_auth,
        )
        self.whitelist = CertificateWhitelist.objects.all()
        self.restricted = UserProfile.objects.filter(allow_certificate=False)
        if settings.DEBUG:
            self.use_https = False
        else:
            self.use_https = True

    def regen_cert(self, student, course_id, course=None, forced_grade=None,
                   template_file=None, generate_pdf=True, site=None):
        """(Re-)Make certificate for a particular student in a particular course

        Arguments:
          student   - User.object
          course_id - courseenrollment.course_id (string)

        WARNING: this command will leave the old certificate, if one exists,
                 laying around in AWS taking up space. If this is a problem,
                 take pains to clean up storage before running this command.

        Change the certificate status to unavailable (if it exists) and request
        grading. Passing grades will put a certificate request on the queue.

        Return the certificate.
        """
        # TODO: when del_cert is implemented and plumbed through certificates
        #       repo also, do a deletion followed by a creation r/t a simple
        #       recreation. XXX: this leaves orphan cert files laying around in
        #       AWS. See note in the docstring too.
        try:
            certificate = GeneratedCertificate.eligible_certificates.get(user=student, course_id=course_id)

            LOGGER.info(
                (
                    u"Found an existing certificate entry for student %s "
                    u"in course '%s' "
                    u"with status '%s' while regenerating certificates. "
                ),
                student.id,
                unicode(course_id),
                certificate.status
            )

            certificate.status = status.unavailable
            certificate.save()

            LOGGER.info(
                (
                    u"The certificate status for student %s "
                    u"in course '%s' has been changed to '%s'."
                ),
                student.id,
                unicode(course_id),
                certificate.status
            )

        except GeneratedCertificate.DoesNotExist:
            pass

        return self.add_cert(
            student,
            course_id,
            course=course,
            forced_grade=forced_grade,
            template_file=template_file,
            generate_pdf=generate_pdf,
            site=site
        )

    def del_cert(self, student, course_id):

        """
        Arguments:
          student - User.object
          course_id - courseenrollment.course_id (string)

        Removes certificate for a student, will change
        the certificate status to 'deleting'.

        Certificate must be in the 'error' or 'downloadable' state
        otherwise it will return the current state

        """

        raise NotImplementedError

    # pylint: disable=too-many-statements
    def add_cert(self, student, course_id, course=None, forced_grade=None,
                 template_file=None, generate_pdf=True, site=None):
        """
        Request a new certificate for a student.

        Arguments:
          student   - User.object
          course_id - courseenrollment.course_id (CourseKey)
          forced_grade - a string indicating a grade parameter to pass with
                         the certificate request. If this is given, grading
                         will be skipped.
          generate_pdf - Boolean should a message be sent in queue to generate certificate PDF

        Will change the certificate status to 'generating' or
        `downloadable` in case of web view certificates.

        The course must not be a CCX.

        Certificate must be in the 'unavailable', 'error',
        'deleted' or 'generating' state.

        If a student has a passing grade or is in the whitelist
        table for the course a request will be made for a new cert.

        If a student has allow_certificate set to False in the
        userprofile table the status will change to 'restricted'

        If a student does not have a passing grade the status
        will change to status.notpassing

        Returns the newly created certificate instance
        """

        if hasattr(course_id, 'ccx'):
            LOGGER.warning(
                (
                    u"Cannot create certificate generation task for user %s "
                    u"in the course '%s'; "
                    u"certificates are not allowed for CCX courses."
                ),
                student.id,
                unicode(course_id)
            )
            return None

        valid_statuses = [
            status.generating,
            status.unavailable,
            status.deleted,
            status.error,
            status.notpassing,
            status.downloadable,
            status.auditing,
            status.audit_passing,
            status.audit_notpassing,
            status.unverified,
            status.not_completed
        ]

        cert_status = certificate_status_for_student(student, course_id)['status']

        if cert_status not in valid_statuses:
            LOGGER.warning(
                (
                    u"Cannot create certificate generation task for user %s "
                    u"in the course '%s'; "
                    u"the certificate status '%s' is not one of %s."
                ),
                student.id,
                unicode(course_id),
                cert_status,
                unicode(valid_statuses)
            )
            return None

        # The caller can optionally pass a course in to avoid
        # re-fetching it from Mongo. If they have not provided one,
        # get it from the modulestore.
        if course is None:
            course = modulestore().get_course(course_id, depth=0)

        profile = UserProfile.objects.get(user=student)
        profile_name = profile.name

        # Needed for access control in grading.
        self.request.user = student
        self.request.session = {}

        is_whitelisted = self.whitelist.filter(user=student, course_id=course_id, whitelist=True).exists()
        course_grade = CourseGradeFactory().read(student, course)
        try:
            score = str(int(course_grade.percent*100)) + "%"
        except KeyError:
            score = 0
        enrollment_mode, __ = CourseEnrollment.enrollment_mode_for_user(student, course_id)
        mode_is_verified = enrollment_mode in GeneratedCertificate.VERIFIED_CERTS_MODES
        user_is_verified = IDVerificationService.user_is_verified(student)
        cert_mode = "" if enrollment_mode is None else enrollment_mode
        is_eligible_for_certificate = is_whitelisted or CourseMode.is_eligible_for_certificate(enrollment_mode)
        unverified = False
        # For credit mode generate verified certificate
        if cert_mode == CourseMode.CREDIT_MODE:
            cert_mode = CourseMode.VERIFIED

        # get PDF template information from the given site_name, overwrite template_file and pdf_info
        pdf_info = None
        if site:
            pdf_config = site.cert_pdf_configs.first()
            site_theme = site.themes.first()
            if site_theme:
                theme_name = site_theme.theme_dir_name
                template_dir = "{0}/{1}/lms/static/certificates".format(settings.COMPREHENSIVE_THEME_DIRS[0],
                                                                        theme_name)
                file_name = "{0}/certificate-template.pdf".format(template_dir)
                if os.path.exists(file_name) and pdf_config:
                    canvas = json.loads(pdf_config.canvas)
                    font_name = pdf_config.font_name
                    font_info = json.loads(pdf_config.font_info)
                    sentences = json.loads(pdf_config.sentences)
                    positions = json.loads(pdf_config.positions)
                    tmp_info = zip(canvas, positions, font_info)


                    with override_language(get_user_email_language(student)):
                        trans_sentences = [_(x) for x in sentences]
                        pdf_info = OrderedDict(zip(trans_sentences, tmp_info))
                    pdf_info.update({"font": font_name, "template_dir": template_dir})

        if template_file is not None:
            template_pdf = template_file
        elif mode_is_verified and user_is_verified:
            template_pdf = "certificate-template-{id.org}-{id.course}-verified.pdf".format(id=course_id)
        elif mode_is_verified and not user_is_verified:
            template_pdf = "certificate-template-{id.org}-{id.course}.pdf".format(id=course_id)
            if CourseMode.mode_for_course(course_id, CourseMode.HONOR):
                cert_mode = GeneratedCertificate.MODES.honor
            else:
                unverified = True
        else:
            # honor code and audit students
            template_pdf = "certificate-template.pdf"

        LOGGER.info(
            (
                u"Certificate generated for student %s in the course: %s with template: %s. "
                u"given template: %s, "
                u"user is verified: %s, "
                u"mode is verified: %s,"
                u"generate_pdf is: %s"
            ),
            student.username,
            unicode(course_id),
            template_pdf,
            template_file,
            user_is_verified,
            mode_is_verified,
            generate_pdf
        )

        cert, created = GeneratedCertificate.objects.get_or_create(user=student, course_id=course_id)

        cert.mode = cert_mode
        cert.user = student
        cert.grade = course_grade.percent
        cert.course_id = course_id
        cert.name = profile_name
        cert.download_url = ''

        # Strip HTML from grade range label
        grade_contents = forced_grade or course_grade.letter_grade
        try:
            grade_contents = lxml.html.fromstring(grade_contents).text_content()
            passing = True
        except (TypeError, XMLSyntaxError, ParserError) as exc:
            LOGGER.info(
                (
                    u"Could not retrieve grade for student %s "
                    u"in the course '%s' "
                    u"because an exception occurred while parsing the "
                    u"grade contents '%s' as HTML. "
                    u"The exception was: '%s'"
                ),
                student.id,
                unicode(course_id),
                grade_contents,
                unicode(exc)
            )

            # Log if the student is whitelisted
            if is_whitelisted:
                LOGGER.info(
                    u"Student %s is whitelisted in '%s'",
                    student.id,
                    unicode(course_id)
                )
                passing = True
            else:
                passing = False

        # If this user's enrollment is not eligible to receive a
        # certificate, mark it as such for reporting and
        # analytics. Only do this if the certificate is new, or
        # already marked as ineligible -- we don't want to mark
        # existing audit certs as ineligible.
        cutoff = settings.AUDIT_CERT_CUTOFF_DATE
        if (cutoff and cert.created_date >= cutoff) and not is_eligible_for_certificate:
            cert.status = status.audit_passing if passing else status.audit_notpassing
            cert.save()
            LOGGER.info(
                u"Student %s with enrollment mode %s is not eligible for a certificate.",
                student.id,
                enrollment_mode
            )
            return cert
        # If they are not passing, short-circuit and don't generate cert
        elif not passing:
            cert.status = status.notpassing
            cert.save()

            LOGGER.info(
                (
                    u"Student %s does not have a grade for '%s', "
                    u"so their certificate status has been set to '%s'. "
                    u"No certificate generation task was sent to the XQueue."
                ),
                student.id,
                unicode(course_id),
                cert.status
            )
            return cert

        else:
            enrollment = CourseEnrollment.get_enrollment(student, course.id)
            if not enrollment.completed and not is_whitelisted:
                cert.status = status.not_completed
                cert.save()

                LOGGER.info(
                    (
                        u"Student %s does not complete the course '%s', "
                        u"so their certificate status has been set to '%s'. "
                        u"No certificate generation task was sent to the XQueue."
                    ),
                    student.id,
                    unicode(course_id),
                    cert.status
                )
                return cert

        # Check to see whether the student is on the the embargoed
        # country restricted list. If so, they should not receive a
        # certificate -- set their status to restricted and log it.
        if self.restricted.filter(user=student).exists():
            cert.status = status.restricted
            cert.save()

            LOGGER.info(
                (
                    u"Student %s is in the embargoed country restricted "
                    u"list, so their certificate status has been set to '%s' "
                    u"for the course '%s'. "
                    u"No certificate generation task was sent to the XQueue."
                ),
                student.id,
                cert.status,
                unicode(course_id)
            )
            return cert

        if unverified:
            cert.status = status.unverified
            cert.save()
            LOGGER.info(
                (
                    u"User %s has a verified enrollment in course %s "
                    u"but is missing ID verification. "
                    u"Certificate status has been set to unverified"
                ),
                student.id,
                unicode(course_id),
            )
            return cert

        # Finally, generate the certificate and send it off.
        return self._generate_cert(cert, course, student, grade_contents, template_pdf, generate_pdf, pdf_info, score)

    def _generate_cert(self, cert, course, student, grade_contents, template_pdf, generate_pdf, pdf_info, score):
        """
        Generate a certificate for the student. If `generate_pdf` is True,
        sends a request to XQueue.
        """
        course_id = unicode(course.id)

        key = make_hashkey(random.random())
        cert.key = key
        contents = {
            'action': 'create',
            'username': student.username,
            'employee_id': student.profile.lt_employee_id,
            'course_id': course_id,
            'course_name': course.display_name or course_id,
            'name': cert.name,
            'grade': grade_contents,
            'template_pdf': template_pdf,
            'score': score,
            'pdf_info': pdf_info
        }
        if generate_pdf:
            cert.status = status.generating
        else:
            cert.status = status.downloadable
            cert.verify_uuid = uuid4().hex

        cert.save()
        logging.info(u'certificate generated for user: %s with generate_pdf status: %s',
                     student.username, generate_pdf)

        course_details = CourseDetails.fetch(course.id)
        contents['duration'] = course_details.duration
        enrollment = CourseEnrollment.get_enrollment(student, course.id)

        lang = get_user_email_language(student)
        with override_language(lang):
            completion_date = enrollment.completed if enrollment and enrollment.completed else cert.modified_date
            if lang not in ('en', 'zh-cn'):
                contents['issued_date'] = strftime_localized(cert.modified_date, "%d %B, %Y")
                contents['completion_date'] = strftime_localized(completion_date, "%d %B, %Y")
            else:
                contents['issued_date'] = strftime_localized(cert.modified_date, "%B %d, %Y")
                contents['completion_date'] = strftime_localized(completion_date, "%B %d, %Y")
        json_date = {
            'year': cert.modified_date.year,
            'month': cert.modified_date.month,
            'day': cert.modified_date.day
        }
        contents['json_date'] = json_date
        if generate_pdf:
            try:
                self._send_to_xqueue(contents, key)
            except XQueueAddToQueueError as exc:
                cert.status = ExampleCertificate.STATUS_ERROR
                cert.error_reason = unicode(exc)
                cert.save()
                LOGGER.critical(
                    (
                        u"Could not add certificate task to XQueue.  "
                        u"The course was '%s' and the student was '%s'."
                        u"The certificate task status has been marked as 'error' "
                        u"and can be re-submitted with a management command."
                    ), course_id, student.id
                )
            else:
                LOGGER.info(
                    (
                        u"The certificate status has been set to '%s'.  "
                        u"Sent a certificate grading task to the XQueue "
                        u"with the key '%s'. "
                    ),
                    cert.status,
                    key
                )
        return cert

    def add_example_cert(self, example_cert, request_user=None, site=None):
        """Add a task to create an example certificate.

        Unlike other certificates, an example certificate is
        not associated with any particular user and is never
        shown to students.

        If an error occurs when adding the example certificate
        to the queue, the example certificate status
        will be set to "error".

        Arguments:
            example_cert (ExampleCertificate)

        """
        template_file = None
        pdf_info = None
        if site:
            pdf_config = site.cert_pdf_configs.first()
            site_theme = site.themes.first()
            if site_theme:
                theme_name = site_theme.theme_dir_name
                template_dir = "{0}/{1}/lms/static/certificates".format(settings.COMPREHENSIVE_THEME_DIRS[0],
                                                                        theme_name)
                file_name = "{0}/certificate-template.pdf".format(template_dir)
                if os.path.exists(file_name) and pdf_config:
                    template_file = "certificate-template.pdf"
                    canvas = json.loads(pdf_config.canvas)
                    font_name = pdf_config.font_name
                    font_info = json.loads(pdf_config.font_info)
                    sentences = json.loads(pdf_config.sentences)
                    positions = json.loads(pdf_config.positions)
                    tmp_info = zip(canvas, positions, font_info)

                    # make sure this only works for Myacademy
                    if site.domain == "myacademy.learning-tribes.com":
                        trans_sentences = [_(x) for x in sentences]
                        pdf_info = OrderedDict(zip(trans_sentences, tmp_info))
                    else:
                        pdf_info = OrderedDict(zip(sentences, tmp_info))
                    pdf_info.update({"font": font_name, "template_dir": template_dir})
        course = modulestore().get_course(example_cert.course_key)
        duration = "1 hour"
        course_display_name = None
        if course:
            course_display_name = course.display_name
            course_details = CourseDetails.fetch(example_cert.course_key)
            duration = course_details.duration
        contents = {
            'action': 'create',
            'course_id': unicode(example_cert.course_key),
            'course_name': course_display_name or unicode(example_cert.course_key),
            'name': example_cert.full_name,
            'template_pdf': template_file or example_cert.template,
            'pdf_info': pdf_info,
            'json_date': {
                'year': now().year,
                'month': now().month,
                'day': now().day
            },
            'issued_date': strftime_localized(now(), "%B %d, %Y"),
            'duration': duration,
            'completion_date': strftime_localized(now(), "%B %d, %Y"),

            # Example certificates are not associated with a particular user.
            # However, we still need to find the example certificate when
            # we receive a response from the queue.  For this reason,
            # we use the example certificate's unique identifier as a username.
            # Note that the username is *not* displayed on the certificate;
            # it is used only to identify the certificate task in the queue.
            'username': example_cert.uuid,
            'employee_id': "employee_id",

            # We send this extra parameter to differentiate
            # example certificates from other certificates.
            # This is not used by the certificates workers or XQueue.
            'example_certificate': True,
        }

        if request_user:
            lang = get_user_email_language(request_user)
            enrollment = CourseEnrollment.get_enrollment(request_user, example_cert.course_key)
            completion_date = enrollment.completed if enrollment and enrollment.completed else now()
            with override_language(lang):
                if lang not in ('en', 'zh-cn'):
                    contents['issued_date'] = strftime_localized(now(), "%d %B, %Y")
                    contents['completion_date'] = strftime_localized(completion_date, "%d %B, %Y")
                else:
                    contents['issued_date'] = strftime_localized(now(), "%B %d, %Y")
                    contents['completion_date'] = strftime_localized(completion_date, "%B %d, %Y")

        # The callback for example certificates is different than the callback
        # for other certificates.  Although both tasks use the same queue,
        # we can distinguish whether the certificate was an example cert based
        # on which end-point XQueue uses once the task completes.
        callback_url_path = reverse('update_example_certificate')

        try:
            self._send_to_xqueue(
                contents,
                example_cert.access_key,
                task_identifier=example_cert.uuid,
                callback_url_path=callback_url_path
            )
            LOGGER.info(u"Started generating example certificates for course '%s'.", example_cert.course_key)
        except XQueueAddToQueueError as exc:
            example_cert.update_status(
                ExampleCertificate.STATUS_ERROR,
                error_reason=unicode(exc)
            )
            LOGGER.critical(
                (
                    u"Could not add example certificate with uuid '%s' to XQueue.  "
                    u"The exception was %s.  "
                    u"The example certificate has been marked with status 'error'."
                ), example_cert.uuid, unicode(exc)
            )

    def add_certs_export(self, certs_path, course_id, task_identifier):
        contents = {
            'action': 'export',
            'certs_path': certs_path,
            'course_id': course_id
        }
        key = make_hashkey(random.random())
        try:
            self._send_to_xqueue(contents,
                                 key,
                                 task_identifier=task_identifier,
                                 callback_url_path='/update_instructor_task'
                                 )
        except XQueueAddToQueueError as exc:
            LOGGER.critical(

                (
                    u"Could not add certificates export task {} to XQueue.  "
                    u"The exception was {}."
                ).format(task_identifier, unicode(exc))
            )

    def _send_to_xqueue(self, contents, key, task_identifier=None, callback_url_path='/update_certificate'):
        """Create a new task on the XQueue.

        Arguments:
            contents (dict): The contents of the XQueue task.
            key (str): An access key for the task.  This will be sent
                to the callback end-point once the task completes,
                so that we can validate that the sender is the same
                entity that received the task.

        Keyword Arguments:
            callback_url_path (str): The path of the callback URL.
                If not provided, use the default end-point for learner-generated
                certificates.

        """
        callback_url = u'{protocol}://{base_url}{path}'.format(
            protocol=("https" if self.use_https else "http"),
            base_url=settings.SITE_NAME,
            path=callback_url_path
        )

        # Append the key to the URL
        # This is necessary because XQueue assumes that only one
        # submission is active for a particular URL.
        # If it receives a second submission with the same callback URL,
        # it "retires" any other submission with the same URL.
        # This was a hack that depended on the URL containing the user ID
        # and courseware location; an assumption that does not apply
        # to certificate generation.
        # XQueue also truncates the callback URL to 128 characters,
        # but since our key lengths are shorter than that, this should
        # not affect us.
        callback_url += "?key={key}".format(
            key=(
                task_identifier
                if task_identifier is not None
                else key
            )
        )

        xheader = make_xheader(callback_url, key, settings.CERT_QUEUE)

        (error, msg) = self.xqueue_interface.send_to_queue(
            header=xheader, body=json.dumps(contents))
        if error:
            exc = XQueueAddToQueueError(error, msg)
            LOGGER.critical(unicode(exc))
            raise exc
