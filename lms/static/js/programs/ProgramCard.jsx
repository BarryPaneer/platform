import React from 'react';

import LanguageLocale from '../LanguageLocale';
import {IsDebug} from '../../../../common/static/js/global_variable';
import {ProgressRing} from '../com/progress-ring';
import {getDuration} from './utils';
import StringUtils from 'edx-ui-toolkit/js/utils/string-utils';
import {formatDate} from "js/DateUtils";

export default function ProgramCard ({uuid, title, language, courses, start, non_started, courses_count, duration = 0, card_image_url, systemLanguage, finishedCourseNum=0, allCourseNum=0}) {
    const mock_image_url = card_image_url;
    const formatDateStr = (dateStr) =>{
        const formatedStr = formatDate(new Date(dateStr), systemLanguage || 'fr', '');
        return formatedStr || dateStr;
    };
    const non_started_program_string = StringUtils.interpolate(gettext('The Learning Path will start on {date}'),
        {
            date: formatDateStr(start)
        });

    return (
        <div className="program-card">
            <div>
                <a href={`/programs/${uuid}/about/`}>
                    <div className={`card-image ${non_started?'non-started-program':''}`} style={{ backgroundImage: `url(${card_image_url})`, backgroundSize: 'cover' }}>
                        {non_started && <i className="far fa-calendar-times"></i>}
                        {non_started && <span className="localized-date">{start && non_started_program_string}</span>}
                    </div>
                </a>
            </div>
            <div className="program_info">
                <div className="title_text">
                    <a href={`/programs/${uuid}/about/`}>
                        <h4 title={title}>{title}</h4>
                    </a>
                </div>
                <div className="info-wrapper">
                    <div className="info-texts">
                        <div className="info_text info_text_courses_number">
                            <i className="far fa-file"></i>
                            <span>{courses_count === undefined ? courses.length : courses_count} {ngettext('Course', 'Courses', courses_count === undefined ? courses.length : courses_count)}</span>
                        </div>
                        <div className="info_text info_text_duration_time">
                            <i className="far fa-clock"></i>
                            <span className="duration">
                                <span>{getDuration(duration)}</span>
                            </span>
                        </div>
                        <div className="info_text info_text_program_lang">
                            <i className="far fa-globe"></i>
                            <LanguageLocale language={language} displayLanguage={systemLanguage} />
                        </div>
                    </div>
                </div>
            </div>
            {(finishedCourseNum>0 || allCourseNum>0) && <ProgressRing radius={18} strokeWidth={3} value={finishedCourseNum} step={allCourseNum}/>}
        </div>
    )
}
