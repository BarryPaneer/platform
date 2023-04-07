# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from courseware.views.views import decode_datetime
from django.conf import settings
from django.views import View
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.http import HttpResponse
from PIL import Image
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth, getFont
import base64, json
from django.utils.translation import pgettext, ugettext as _
from util.date_utils import strftime_localized
from opaque_keys.edx.keys import UsageKey
from courseware.models import XModuleUserStateSummaryField
from xmodule.modulestore.django import modulestore

log = logging.getLogger("ILT_invitation")


class SessionInvitationPdf(View):
    ihfo = 0  # icon height from origin
    shfo = 0  # string height from origin

    def drawIconImage(self, c, absolutepath, x_pos, y_pos, width, height):
        try:
            img = Image.open(str(absolutepath))
            c.drawImage(absolutepath, x_pos, y_pos, width=width, height=height, mask="auto")
        except IOError, ex:
            log.exception('Pdf unable to open the image file: %s', str(ex))

    def get_text_height(self, font_name, font_size):
        face = getFont(font_name).face
        ascent = (face.ascent * font_size) / 1000.0
        descent = (face.descent * font_size) / 1000.0

        return ascent - descent

    def increment_height(self, ih, sh):
        self.ihfo += ih * cm
        self.shfo += sh * cm

    def get_text_position(self, width_1, width_2, initial_position):
        if width_1 >= width_2:
            position_1 = initial_position
            position_2 = initial_position + (width_1 - width_2)/2
        else:
            position_2 = initial_position
            position_1 = initial_position + (width_2 - width_1)/2
        return position_1, position_2

    def get(self, request, usage_id, session_id):
        usage_key = UsageKey.from_string(usage_id)
        ilt_block = modulestore().get_item(usage_key)
        sessions = XModuleUserStateSummaryField.objects.get(field_name='sessions', usage_id=usage_key)
        session_info = json.loads(sessions.value)[session_id]

        BASE_DIR = settings.PROJECT_ROOT
        if "instructor" in session_info:
            INVITATION_TEMPLATE = BASE_DIR + '/static/images/session_invitation/template.png'
        else:
            INVITATION_TEMPLATE = BASE_DIR + '/static/images/session_invitation/template_without_instructor.png'

        font_name = settings.DEFAULT_FONT_SANS_SERIF
        font_bold_name = font_name + '-Bold'
        FONT_DIR = settings.STATIC_ROOT + '/fonts/' + font_name + '/'

        width, height = A4  # keep for later
        width = width - 0.8 * cm
        pdfmetrics.registerFont(TTFont(font_name, FONT_DIR + font_name + '-Regular.ttf'))
        pdfmetrics.registerFont(TTFont(font_bold_name, FONT_DIR + font_bold_name + '.ttf'))
        font_size = 16
        page_margin = 1.5 * cm
        grey = (0.639, 0.631, 0.631)
        black = (0.114, 0.114, 0.106)

        header_text = _('Invitation to a training session')
        header_text_width = stringWidth(header_text, font_name, font_size + 2)

        subheader_text = _('Invitation for {first_name} {last_name}').format(
            first_name=request.user.first_name.capitalize(),
            last_name=request.user.last_name.capitalize()
        )
        subheader_text_width = stringWidth(subheader_text, font_name, font_size)

        info_header_1 = _("We're glad to confirm your registration to the")
        info_header_width_1 = stringWidth(info_header_1, font_name, font_size)
        info_header_2 = _("following in-class or virtual training")
        info_header_width_2 = stringWidth(info_header_2, font_name, font_size)

        course_key = usage_key.course_key
        course_name = modulestore().get_course(course_key).display_name
        course_width = stringWidth(course_name, font_name, font_size)
        title = ilt_block.display_name
        title_width = stringWidth(title, font_name, font_size)

        footer_text = (_('We wish you a great training session.'))
        footer_text_width = stringWidth(footer_text, font_name, font_size - 2)

        str_start_date = decode_datetime(session_info["start_at"]).strftime("%Y-%m-%d")
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="session_invitation_{}.pdf"'.format(str_start_date)
        c = canvas.Canvas(response, pagesize=A4, bottomup=0)
        # draw template
        self.drawIconImage(c, INVITATION_TEMPLATE, 0, 0, width=21 * cm, height=29.7 * cm)
        c.translate(page_margin, page_margin)  # shifting origin from (0,0) to (2,2) cm

        c.setFillColorRGB(*black)
        c.setFont(font_bold_name, font_size + 2)
        c.drawString(((width - 2 * page_margin) / 2) - (header_text_width / 2), 1.5 * cm, header_text)
        c.setFont(font_name, font_size)
        width = width + 0.4 * cm
        c.drawString(((width - 2 * page_margin) / 2) - (subheader_text_width / 2), 2.3 * cm, subheader_text)
        c.drawString(((width - 2 * page_margin) / 2) - (info_header_width_1 / 2), 3 * cm, info_header_1)
        c.drawString(((width - 2 * page_margin) / 2) - (info_header_width_2 / 2), 3.7 * cm, info_header_2)
        c.drawString(((width - 2 * page_margin) / 2) - (course_width / 2), 5.3 * cm, course_name)
        c.drawString(((width - 2 * page_margin) / 2) - (title_width / 2), 6 * cm, title)

        self.ihfo = 11.5 * cm
        self.shfo = 11.85 * cm

        c.translate(1 * cm, 0)

        from_text = _("From")
        from_text_width = stringWidth(from_text, font_name, font_size)
        start_time = session_info["start_at"].split("T")[1]
        start_time_width = stringWidth(start_time, font_name, font_size)
        from_initial = width/2 - max(from_text_width, start_time_width) - 4.2*cm
        from_text_posn, start_time_posn = self.get_text_position(from_text_width, start_time_width, from_initial)
        c.drawString(from_text_posn, 10.7*cm, from_text)
        c.drawString(start_time_posn, 11.6*cm, start_time)

        start_date = strftime_localized(decode_datetime(session_info["start_at"]), "SHORT_DATE")
        try:
            start_date_month = start_date.split(", ")[0].upper()
            start_date_year = start_date.split(", ")[1]
        except IndexError:
            start_date_month = start_date.rsplit(" ", 1)[0].upper()
            start_date_year = start_date.rsplit(" ", 1)[1]
        start_date_1_width = stringWidth(start_date_month, font_name, font_size)
        start_date_2_width = stringWidth(start_date_year, font_name, font_size)
        start_date_1_posn, start_date_2_posn = self.get_text_position(
            start_date_1_width, start_date_2_width, from_initial - 3.5*cm)
        c.drawString(start_date_1_posn, 10.8 * cm, start_date_month)
        c.drawString(start_date_2_posn, 11.5 * cm, start_date_year)

        to_text = _("To")
        to_text_width = stringWidth(to_text, font_name, font_size)
        end_time = session_info["end_at"].split("T")[1]
        end_time_width = stringWidth(end_time, font_name, font_size)
        to_initial = width/2 - 1*cm
        to_text_posn, end_time_posn = self.get_text_position(to_text_width, end_time_width, to_initial)
        c.drawString(to_text_posn, 10.7 * cm, to_text)
        c.drawString(end_time_posn, 11.6 * cm, end_time)

        end_date = strftime_localized(decode_datetime(session_info["end_at"]), "SHORT_DATE")
        try:
            end_date_month = end_date.split(", ")[0].upper()
            end_date_year = end_date.split(", ")[1]
        except IndexError:
            end_date_month = end_date.rsplit(" ", 1)[0].upper()
            end_date_year = end_date.rsplit(" ", 1)[1]
        end_date_1_width = stringWidth(end_date_month, font_name, font_size)
        end_date_2_width = stringWidth(end_date_year, font_name, font_size)
        end_date_initial = to_initial + end_time_width + 1.5*cm
        end_date_1_posn, end_date_2_posn = self.get_text_position(
            end_date_1_width, end_date_2_width, end_date_initial)
        c.drawString(end_date_1_posn, 10.8 * cm, end_date_month)
        c.drawString(end_date_2_posn, 11.5 * cm, end_date_year)

        timezone = session_info["timezone"]
        timezone_offset = "{} GMT +{}".format(timezone, session_info["timezone_offset"])
        timezone_offset_text_width = stringWidth(timezone_offset, font_name, font_size - 2)
        c.setFont(font_name, font_size - 2)
        c.drawString(((width - 2 * page_margin) / 2) - (timezone_offset_text_width / 2) - 1*cm, 12.8 * cm, timezone_offset)
        self.increment_height(1, 1)

        c.setFont(font_name, font_size - 4)
        width = width - 0.8 * cm
        if "area_region" in session_info:
            c.setFillColorRGB(*grey)
            area_region_text = _("Area/Region") + ": "
            area_region_text_width = stringWidth(area_region_text, font_name, font_size - 4)
            c.drawString(width/2 - area_region_text_width - 2.7 * cm, 16.5 * cm, area_region_text)
            c.setFillColorRGB(*black)
            area_region = session_info["area_region"].capitalize()
            c.drawString(width / 2 - 2.5 * cm, 16.5 * cm, area_region)

        if "city" in session_info:
            c.setFillColorRGB(*grey)
            city_text = _("City") + ": "
            city_text_width = stringWidth(city_text, font_name, font_size - 4)
            c.drawString(width / 2 - city_text_width - 2.7 * cm, 17 * cm, city_text)
            c.setFillColorRGB(*black)
            city = session_info["city"].capitalize()
            c.drawString(width / 2 - 2.5 * cm, 17 * cm, city)

        if "zip_code" in session_info:
            c.setFillColorRGB(*grey)
            zip_code_text = _("Zip Code") + ": "
            zip_code_width = stringWidth(zip_code_text, font_name, font_size - 4)
            c.drawString(width / 2 - zip_code_width - 2.7 * cm, 17.5 * cm, zip_code_text)
            c.setFillColorRGB(*black)
            zip_code = session_info["zip_code"]
            c.drawString(width / 2 - 2.5 * cm, 17.5 * cm, zip_code)

        if "address" in session_info:
            c.setFillColorRGB(*grey)
            address_text = pgettext('xblock-ilt', "Address") + ": "
            address_text_width = stringWidth(address_text, font_name, font_size - 4)
            c.drawString(width / 2 - address_text_width - 2.7 * cm, 18 * cm, address_text)
            c.setFillColorRGB(*black)
            address = session_info["address"]
            c.drawString(width / 2 - 2.5 * cm, 18 * cm, address)

        if "location_id" in session_info:
            c.setFillColorRGB(*grey)
            location_id_text = _("Location ID") + ": "
            location_id_text_width = stringWidth(location_id_text, font_name, font_size - 4)
            c.drawString(width / 2 - location_id_text_width - 2.7 * cm, 18.5 * cm, location_id_text)
            c.setFillColorRGB(*black)
            location_id = session_info["location_id"]
            c.drawString(width / 2 - 2.5 * cm, 18.5 * cm, location_id)

        if "instructor" in session_info:
            c.setFont(font_name, font_size + 4)
            c.setFillColorRGB(*grey)
            c.setFont(font_name, font_size + 3)
            instructor_text = _("Instructor") + ":"
            instructor_text_width = stringWidth(instructor_text, font_name, font_size + 4)
            c.drawString(((width - 2 * page_margin) / 2) - (instructor_text_width / 2) - 0.5*cm, 22.8 * cm,
                         instructor_text)
            c.setFillColorRGB(*black)
            instructor = session_info["instructor"]
            instructor_width = stringWidth(instructor, font_name, font_size + 4)
            c.drawString(((width - 2 * page_margin) / 2) - (instructor_width / 2) - 0.5*cm, 23.7 * cm,
                         instructor)

        c.translate(-1 * cm, 0)
        c.setFont(font_bold_name, font_size)
        c.drawString((((width - 2 * page_margin) / 2) - (footer_text_width / 2)) - 0.4*cm, height - 4 * cm, footer_text)

        c.save()

        return response
