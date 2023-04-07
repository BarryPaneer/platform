import React from "react"
import {formatDate} from "js/DateUtils"


export function CrehanaCourseCard ({image, duration, languages, rating, title, url, systemLanguage}) {
    return (
        <div className="courses-listing-item">
            <a href={`courses/crehana_catalog?next_url=${url}`} target="_blank">
                <div className="card-image-wrapper" style={{backgroundImage: 'url(' + image + ')'}}>
                </div>
                <div className="extra">
                    <ul className="tags">
                        <li className="active_crehana">{gettext("CREHANA")}</li>
                    </ul>
                    <span className="star-score">
                        <i className="fa fa-star"></i>
                        <span className="score">{parseFloat(rating).toFixed(2)}</span>
                    </span>
                </div>
                <h4 title={title}>{title}</h4>
                <div className="sub-info">
                    {duration && (<span className="duration">
                        <i className="far fa-clock"></i>
                        <span>{formatDuration(duration)}</span>
                    </span>)}

                    <span className="language">
                        <i className="far fa-globe"></i>
                        {languages.map(language => <span>{formatLanguage(language, systemLanguage)}</span>)}
                    </span>
                </div>
            </a>
        </div>
    )
}

export function EdflexCourseCard ({image, duration, language, rating, title, publication_date, url, type, systemLanguage}) {
    return (
        <div className="courses-listing-item">
            <a href={url} target="_blank">
                <div className="card-image-wrapper" style={{backgroundImage: 'url(' + image + ')'}}>
                </div>
                <div className="extra">
                    <ul className="tags">
                        <li className="active">{gettext("EDFLEX")}</li>
                        <li>{gettext(type)}</li>
                    </ul>
                    <span className="star-score">
                        <i className="fa fa-star"></i>
                        <span className="score">{parseFloat(rating).toFixed(2)}</span>
                    </span>
                </div>
                <h4 title={title}>{title}</h4>
                <div className="sub-info">
                    {duration && (<span className="duration">
                        <i className="far fa-clock"></i>
                        <span>{formatDuration(duration)}</span>
                    </span>)}
                    <span className="date-str">
                        <i className="far fa-calendar-week"></i>
                        <span>{formatDate(new Date(publication_date), systemLanguage || 'en', '')}</span>
                    </span>
                    <span className="language">
                        <i className="far fa-globe"></i>
                        <span>{formatLanguage(language, systemLanguage)}</span>
                    </span>
                </div>
            </a>
        </div>
    )
}

export function AnderspinkArticleCard ({image, reading_time, language, author, date_published, title, url, systemLanguage}) {
    return (
        <div className="courses-listing-item">
            <a href={url} target="_blank">
                <div className="card-image-wrapper" style={{backgroundImage: 'url(' + image + ')'}}>
                </div>
            <div className="extra">
                <ul style={{padding : 0}} className="tags">
                     <li className={'active_anderspink'} >{gettext("ANDERS PINK")}</li>
                </ul>
                {author &&
                    <span className="author" >
                        <i className="fa fa-user"></i>
                        <span className="name">{author}</span>
                    </span>
                        }
            </div>
                <h4 title={title}>{title}</h4>
                <div className="sub-info">
                    {reading_time && (<span className="duration">
                        <i className="far fa-clock"></i>
                        <span>{formatDuration(reading_time)}</span>
                    </span>)}
                    <span className="date-str">
                        <i className="far fa-calendar-week"></i>
                        <span>{formatDate(new Date(date_published), systemLanguage || 'en', '')}</span>
                    </span>
                    <span className="language">
                        <i className="far fa-globe"></i>
                        <span>{formatLanguage(language, systemLanguage)}</span>
                    </span>
                </div>
            </a>
        </div>
    )
}


function formatDuration (duration) {
    const hhmmArray = new Date(duration * 1000).toISOString().substr(11, 5).split(":")
    const hh = parseInt(hhmmArray[0])
    const mm = parseInt(hhmmArray[1])
    if (!hh) return gettext('${min} min').replace('${min}', mm)
    if (!mm) return gettext('${hour} hour').replace('${hour}', hh)
    return gettext('${hour} h $(min) m').replace('${hour}', hh).replace('$(min)', mm)
}

function formatLanguage (language, displayLanguage) {
    if (!window.Intl || !window.Intl.DisplayNames) return language

    const capitalize = s => s.charAt(0).toUpperCase() + s.slice(1)
    const languageNames = new Intl.DisplayNames([displayLanguage || 'en'], {type: 'language'})
    return capitalize(languageNames.of((language || 'en').split(/[-_]/)[0]))
}
