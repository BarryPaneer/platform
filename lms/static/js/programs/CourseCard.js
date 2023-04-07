import React from "react";
import {formatLanguage} from "../LanguageLocale";
import {formatDate} from "js/DateUtils";
import {getDuration} from './utils';
import StringUtils from 'edx-ui-toolkit/js/utils/string-utils';

class ProgressBar extends React.Component {
    constructor(props) {
        super(props);
    }
    render() {
        const {value}=this.props
        return <div className="progress-bar">
                    <div className="progress-bar-bg">
                        <div className="progress-bar-filling" style={{'width':value}}></div>
                    </div>
                    <span className="percent">{value}%</span>
                </div>
    }
}

class CourseCard extends React.Component {
    constructor(props) {
        super(props);
    }

    render() {
        const pr = this.props
        const {systemLanguage} = this.props
        const formatDateStr = (dateStr) =>{
            const formatedStr = formatDate(new Date(dateStr), systemLanguage || 'fr', '')
            return formatedStr || dateStr
        }
        const non_started_string = StringUtils.interpolate(gettext('The course will start on {date}'),
            {
                date: formatDateStr(pr.start)
            })

        var courseUrl;
        if (pr.non_started) {
            courseUrl = 'about'
        } else if (pr.linkType && pr.linkType == 'course') {
            courseUrl = 'course'
        } else {
            courseUrl = 'about'
        }

        return <li className="course-card">
            <div className="course-image">
                <a href={`/courses/${pr.id}/${courseUrl}`}>
                    {pr.non_started && <div className="mask">
                        <i className="far fa-calendar-times"></i>
                        <span className="localized-date">{pr.start && non_started_string}</span>
                    </div>}
                    <img src={pr.image_url} alt={pr.title}/>
                </a>
                <span className="tags">
                    {(pr.tags || []).map(p=>(<div className="course-tag">{p.text}</div>))}
                    <div className="course-tag course-language">{formatLanguage(pr.language, systemLanguage)}</div>
                </span>
            </div>
            <div className="course-details">
                <div className="course-info">
                    <section>
                        <h2 className="course-title"><a href={`/courses/${pr.course_id}/about`}>{pr.title}</a></h2>
                    </section>
                    <div className="localized-date">{pr.start && formatDateStr(pr.start)}{pr.end && (" - " + formatDateStr(pr.end))}</div>
                </div>
                <section className="sub-info">
                    <div className="badge">
                        <i className="far fa-trophy"></i>
                        <span>{pr.badge}</span>
                    </div>
                    {!!getDuration(`${pr.duration} ${pr.duration_unit}`) && (
                        <>
                            <div className="spliter"></div>
                            <div className="duration">
                                <i className="far fa-clock"></i>
                                <span>{getDuration(`${pr.duration} ${pr.duration_unit}`)}</span>
                            </div>
                        </>
                    )}
                </section>
                {pr.enableProgress && <ProgressBar value={pr.progress}/>}
            </div>
        </li>
    }
}
export {CourseCard}
