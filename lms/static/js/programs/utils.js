export function getDuration (dur, shortDate) {
    function formatPlural (n, single, plural) {
        if (n <= 1 && single) return `${n} ${single}`
        return `${n} ${plural}`
    }

    const config = {
        h: gettext('Hours').toLowerCase(),
        m: gettext('Minutes').toLowerCase(),
        hs: gettext('Hour').toLowerCase(),
        ms: gettext('Minute').toLowerCase(),
        d: gettext('Days').toLowerCase(),
        ds: gettext('Day').toLowerCase(),
    }

    const {m = 'm', h = 'h', d = 'd'} = config

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

    dur = typeof (dur) === 'number' ? dur : 0
    const days = Math.floor(dur / 60 / 24) || 0
    const dayStr = formatPlural(days, config.ds, d)
    const hours = Math.floor(dur % (60 * 24) / 60) || 0
    const hourStr = formatPlural(hours, config.hs, h)
    const minutes = (dur % 60) || 0
    const minuteStr = shortDate ? gettext('${min} min').replace('${min}', minutes) : formatPlural(minutes, config.ms, m)

    if (!days) {
        if (!hours) return minuteStr

        if (minutes) {
            if (shortDate) return gettext('${hour} h $(min) m').replace('${hour}', hours).replace('$(min)', minutes)
            return `${hourStr} ${minuteStr}`
        }

        if (shortDate) return gettext('${hour} h').replace('${hour}', hours)
        return hourStr
    }

    return [
        [days, shortDate ? gettext('${day} d').replace('${day}', days) : dayStr],
        [hours, shortDate ? gettext('${hour} h').replace('${hour}', hours) : hourStr],
        [minutes, shortDate ? gettext('${min} m').replace('${min}', minutes) : minuteStr],
    ].filter(spec => spec[0]).map(spec => spec[1]).join(' ') || minuteStr
}
