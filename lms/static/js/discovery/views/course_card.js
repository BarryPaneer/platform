"use strict";

(function (define) {
  'use strict';

  define(['jquery', 'underscore', 'backbone', 'gettext', 'edx-ui-toolkit/js/utils/date-utils', 'edx-ui-toolkit/js/utils/string-utils'], function ($, _, Backbone, gettext, DateUtils, StringUtils) {
    function formatDate(date, userLanguage, userTimezone) {
      var context;
      context = {
        datetime: date,
        language: userLanguage,
        timezone: userTimezone,
        format: DateUtils.dateFormatEnum.shortDate
      };
      return DateUtils.localize(context);
    }

    function formatLanguage(language, userPreferences) {
      if (!window.Intl || !window.Intl.DisplayNames) return language;

      var capitalize = function capitalize(s) {
        return s.charAt(0).toUpperCase() + s.slice(1);
      };

      var displayLanguage = (userPreferences || {})['pref-lang'] || (document.querySelector('#footer-language-select option[selected]') || {}).value;
      var languageNames = new Intl.DisplayNames([displayLanguage || 'en'], {
        type: 'language'
      });
      return capitalize(languageNames.of((language || 'en').split(/[-_]/)[0]));
    }

    return Backbone.View.extend({
      tagName: 'li',
      templateId: '#course_card-tpl',
      className: 'courses-listing-item',
      initialize: function initialize() {
        this.tpl = _.template($(this.templateId).html());
      },
      render: function render() {
        var _this = this;

        var data = _.clone(this.model.attributes);

        var userLanguage = '',
            userTimezone = '';

        // Initialize fields
        data.is_enrolled = false;    
        data.is_completed = false; 
        data.cert_status = "";
        data.cert_download_url = "";

        if (this.model.userPreferences !== undefined) {
          userLanguage = this.model.userPreferences.userLanguage;
          userTimezone = this.model.userPreferences.userTimezone;

          if (this.model.userPreferences.student_enrollments_dict !== undefined) {
            const studentEnrollment = this.model.userPreferences.student_enrollments_dict[data.id]

            if (studentEnrollment) {
              data.is_enrolled = true
              if (studentEnrollment.completed) {
                data.is_completed = true

                // Gets info about Certificate (Status and Download Url)
                if (studentEnrollment.cert_info.status && studentEnrollment.cert_info.download_url) {
                  data.cert_status = studentEnrollment.cert_info.status;
                  data.cert_download_url = studentEnrollment.cert_info.download_url;
                }
              }
            }
          }  
        }
        if (data.advertised_start !== undefined) {
          data.start = data.advertised_start;
        } else {
          data.start = formatDate(new Date(data.start), userLanguage, userTimezone);
        }

        data.end = formatDate(new Date(data.end), userLanguage, userTimezone);
        data.enrollment_start = formatDate(new Date(data.enrollment_start), userLanguage, userTimezone);

        if (data.course_category) {
          data.course_category = window.COURSE_CATEGORIES[data.course_category];
        }

        if (data.content.duration) {
          var duration = data.content.duration.trim().split(' ');
          var fmt = '';

          if (duration.length > 1 && !_.isEmpty(duration[0])) {
            if (duration[1].startsWith('minute')) {
              fmt = gettext('%(min)s min', duration[0]);
              data.display_duration = interpolate(fmt, {
                min: duration[0]
              }, true);
            } else if (duration[1].startsWith('hour')) {
              fmt = gettext('%(h)s h', duration[0]);
              data.display_duration = interpolate(fmt, {
                h: duration[0]
              }, true);
            } else if (duration[1].startsWith('day')) {
              fmt = gettext('%(d)s d', duration[0]);
              data.display_duration = interpolate(fmt, {
                d: duration[0]
              }, true);
            }
          }
        }
        if (data.non_started) {
          data.non_started_string = StringUtils.interpolate(
              gettext('The course will start on {date}'),
              {date: data.start}
          );
        }
        data.formatLanguageString = function (language) {
          return formatLanguage(language, _this.model.userPreferences);
        }, this.$el.html(this.tpl(data));
        return this;
      }
    });
  });
})(define || RequireJS.define);