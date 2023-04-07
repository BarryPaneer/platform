
define([
    'edx-ui-toolkit/js/utils/date-utils'
], function(DateUtils) {
    function getDuration (dur, shortDate) {
        function formatPlural (n, single, plural) {
            if (n <= 1 && single) return "".concat(n, " ").concat(single)
            return "".concat(n, " ").concat(plural)
        }

        var config = {
            h: gettext('Hours').toLowerCase(),
            m: gettext('Minutes').toLowerCase(),
            hs: gettext('Hour').toLowerCase(),
            ms: gettext('Minute').toLowerCase(),
            d: gettext('Days').toLowerCase(),
            ds: gettext('Day').toLowerCase()
        }
        var _config$m = config.m,
            m = _config$m === void 0 ? 'm' : _config$m,
            _config$h = config.h,
            h = _config$h === void 0 ? 'h' : _config$h,
            _config$d = config.d,
            d = _config$d === void 0 ? 'd' : _config$d

        if (typeof dur === 'string') {
            var contents = dur.split(" ")

            if (contents.length === 2) {
                var duration_unit = contents[1]
                var duration = contents[0].includes('.') ? parseFloat(contents[0]) : parseInt(contents[0])
                if (duration_unit.startsWith('minute')) return formatPlural(duration, config.ms, m)
                if (duration_unit.startsWith('hour')) return formatPlural(duration, config.hs, h)
                if (duration_unit.startsWith('day')) return formatPlural(duration, config.ds, d)
            }

            return ''
        }

        dur = typeof dur === 'number' ? dur : 0
        var days = Math.floor(dur / 60 / 24) || 0
        var dayStr = formatPlural(days, config.ds, d)
        var hours = Math.floor(dur % (60 * 24) / 60) || 0
        var hourStr = formatPlural(hours, config.hs, h)
        var minutes = dur % 60 || 0
        var minuteStr = shortDate ? gettext('${min} min').replace('${min}', minutes) : formatPlural(minutes, config.ms, m)

        if (!days) {
            if (!hours) return minuteStr

            if (minutes) {
                if (shortDate) return gettext('${hour} h $(min) m').replace('${hour}', hours).replace('$(min)', minutes)
                return "".concat(hourStr, " ").concat(minuteStr)
            }

            if (shortDate) return gettext('${hour} h').replace('${hour}', hours)
            return hourStr
        }

        return [[days, shortDate ? gettext('${day} d').replace('${day}', days) : dayStr], [hours, shortDate ? gettext('${hour} h').replace('${hour}', hours) : hourStr], [minutes, shortDate ? gettext('${min} m').replace('${min}', minutes) : minuteStr]].filter(function (spec) {
            return spec[0]
        }).map(function (spec) {
            return spec[1]
        }).join(' ') || minuteStr
    }

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

    return { DateUtils, formatDate, getDuration }
});
