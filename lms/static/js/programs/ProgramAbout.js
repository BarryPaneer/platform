import React, {Fragment} from 'react'
import {ProgressRing} from '../com/progress-ring'
import {formatDate, getDuration} from "js/DateUtils"
import {formatLanguage} from '../LanguageLocale'
import Cookies from 'js-cookie'
import StringUtils from 'edx-ui-toolkit/js/utils/string-utils';


const getFormatedDate = (date, language) => {
    return formatDate(new Date(date), language || 'fr', '')
}

class ProgramAbout extends React.Component {
    constructor (props) {
        super(props)
        this.state = {
            title: props.program.title,
        }
    }

    enroll () {
        const formData = new FormData()
        const param = {
            'uuid': this.props.program_uuid,
            'status': 'enrolled',
            'cascade_courses': 1
        }
        Object.keys(param).forEach(key => {
            formData.append(key, param[key])
        })

        $('#id-enroll-button').addClass('disable-enroll-button');

        if (this.props.enrollment_status == 'none') {
            fetch("/api/program_enrollments/v1/users/" + this.props.username + "/programs/", {
                method: 'POST',
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken'),
                },
                body: formData,
            })
                .then(res => res.json())
                .then(
                    (result) => {
                        location.reload()
                    },
                )
                .catch(error => {
                    console.error('Error:', error);
                    $('#id-enroll-button').removeClass('disable-enroll-button');
                })
        } else {
            fetch("/api/program_enrollments/v1/users/" + this.props.username + "/programs/", {
                method: 'PATCH',
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken'),
                },
                body: formData,
            })
                .then(res => res.json())
                .then(
                    (result) => {
                        location.reload()
                    },
                )
                .catch(error => {
                    console.error('Error:', error);
                    $('#id-enroll-button').removeClass('disable-enroll-button');
                })
        }

    }

    unenroll () {
        const formData = new FormData()
        const param = {
            'uuid': this.props.program_uuid,
            'status': 'canceled',
            'cascade_courses': 1
        }
        Object.keys(param).forEach(key => {
            formData.append(key, param[key])
        })

        $('#id-unenroll-button').addClass('disable-unenroll-button');

        fetch("/api/program_enrollments/v1/users/" + this.props.username + "/programs/", {
            method: 'PATCH',
            headers: {
                'X-CSRFToken': Cookies.get('csrftoken'),
            },
            body: formData,
        })
            .then(res => res.json())
            .then(
                (result) => {
                    location.reload()
                },
            )
            .catch(error => {
                console.error('Error:', error);
                $('#id-unenroll-button').removeClass('disable-unenroll-button');
            })
    }

    getActiveCourseID () {
        const prg = this.props.program
        if (prg.courses.length <= 0) return ""
        let course = prg.courses.find(p => {
            return p.course_enrollment_status == 'active'
        }) || prg.courses[0]
        return course.course_id
    }

    openStudio (endpoint) {
        window.open(new URL(endpoint, 'http://' + this.props.studioLink))
    }

    openEditProgram () {
        const uuid = this.props.program.uuid
        this.openStudio(`/program_detail/?program_uuid=${uuid}`)
    }

    render () {
        const {program_uuid, theme_dir_name, systemLanguage, username, isAdmin} = this.props
        const program_courses_completed = this.props.program_courses_completed
        const program_courses_total = this.props.program_courses_total
        const enrolled = this.props.enrollment_status === 'enrolled'
        const pr = this.props.program
        const {
            title, card_image_url,
            start: start, end: end,
            non_started,
            courses
        } = this.props.program
        const non_started_program_string = StringUtils.interpolate(gettext('The Learning Path will start on {date}'),
            {
                date: getFormatedDate(start, systemLanguage)
            })
        return <Fragment>
            <div id="program-details-hero">
                <div className="main-banner">
                    <div className="container">
                        <img src={`/static/${theme_dir_name}/images/programs/8.png`} />
                        <div className="rectangle" >
                            <div className="program-process-wrapper" style={{'background-image': 'url("' + card_image_url + '")'}}>
                                {non_started && <div className="mask">
                                    <i className="far fa-calendar-times"></i>
                                    <h2 className="localized-date">{start && non_started_program_string}</h2>
                                </div>}
                                {!non_started && enrolled && <ProgressRing className='progress-ring-ordinary' radius={55} strokeWidth={8} value={program_courses_completed} step={program_courses_total} />}
                                {!non_started && enrolled && <ProgressRing className='progress-ring-tiny' radius={23} strokeWidth={4} value={program_courses_completed} step={program_courses_total} />}
                            </div>
                        </div>
                        <div className="program_summary">
                            <div className='title-wrapper'>
                                <h1 className="program_title" title={title}>{title}</h1>
                                <span className="far fa-print" />
                                {isAdmin && <span className="far fa-pen" onClick={this.openEditProgram.bind(this)} />}
                            </div>
                            <ProgramDescription description={pr.description} />
                            <div className="program_state">
                                <small className="sub-info"><i className="far fa-clock" /><span>{getDuration(pr.duration)}</span></small><i />
                                <small className="sub-info"><i className="far fa-globe" /><span>{formatLanguage(pr.language, systemLanguage)}</span></small><i />
                                <small className="sub-info"><i className="far fa-calendar-week" />
                                    <span>{start && getFormatedDate(start, systemLanguage)}{enrolled && end && `-${getFormatedDate(end, systemLanguage)}`}</span>
                                </small>
                            </div>
                            <div className='buttons'>
                                {!non_started && <a href={`#${this.getActiveCourseID()}`} className="discovery-button">{gettext('Discover the Learning Path')}</a>}
                                {!enrolled && (pr.visibility != 1 || (pr.visibility === 1 && isAdmin)) && <a id="id-enroll-button" className="enroll-button" href="#" onClick={this.enroll.bind(this)}>{gettext('Enroll Now')}</a>}
                            </div>
                            {non_started && <div className="non-started-info">
                                <i className="far fa-calendar-times"></i>
                                <span className="localized-date">{start && non_started_program_string}</span>
                            </div>}
                        </div>


                    </div>
                </div>
            </div>

            <div className="program-details-page-container">
                {courses &&
                    <div className="courses-list-container">
                        {courses.map((course, i) => (
                            <CourseSection
                                program_uuid={program_uuid}
                                username={username}
                                enrollment_status={this.props.enrollment_status}
                                key={course.course_id}
                                prevCourse={courses[i - 1]}
                                course={course}
                                systemLanguage={systemLanguage} />
                        ))}
                    </div>}
                {enrolled &&
                    <div id="id-unenroll-container" className="unenroll_container">
                        <a id="id-unenroll-button" className="unenroll-button" onClick={this.unenroll.bind(this)}>{gettext('Unenroll')}</a>
                    </div>}
            </div>

        </Fragment>
    }
}

function ProgramDescription ({description, maxHeight = '200px'}) {
    const [needToggle, setNeedToggle] = React.useState(false)
    const [isShowMore, setIsShowMore] = React.useState(false)
    const $content = React.useRef()

    const handleShowMore = () => setIsShowMore(true)
    const handleShowLess = () => setIsShowMore(false)

    React.useEffect(() => {
        if (!$content.current) return
        if ($content.current.clientHeight < $content.current.scrollHeight) setNeedToggle(true)
        return () => {
            setNeedToggle(false)
        }
    }, [])

    if (!description || description === 'is_null') return null

    return (
        <div className={`program-description ${needToggle ? 'program-description--need-toggle' : ''} ${isShowMore ? 'program-description--show-more' : ''}`}>
            <div
                ref={$content}
                className="program-description__content"
                style={{maxHeight: isShowMore ? '10000px' : maxHeight}}
                dangerouslySetInnerHTML={{__html: description}}
            />
            {needToggle && (isShowMore
                ? <div className="program-description__toggle" onClick={handleShowLess}>{gettext('Read less')}</div>
                : <div className="program-description__toggle" onClick={handleShowMore}>{gettext('Read more')}</div>
            )}
        </div>
    )
}

class CourseSection extends React.Component {
    constructor (props) {
        super(props)
        this.state = {
        }
    }
    getCourseImg (img) {
        return img
    }
    getFormatedDate (date) {
        return getFormatedDate(date, this.props.systemLanguage)
    }
    showMore (e) {
        console.log(e.currentTarget)
    }

    enroll_course (course_uuid, course_enrollment_status, course_about_url) {
        const formData = new FormData()
        const param = {
            'course_uuid': course_uuid,
            'status': 'active'
        }
        Object.keys(param).forEach(key => {
            formData.append(key, param[key])
        })

        if (course_enrollment_status == null) {
            fetch("/api/program_enrollments/v1/users/" + this.props.username + "/programs/" + this.props.program_uuid + "/courses/", {
                method: 'POST',
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken'),
                },
                body: formData,
            })
                .then(res => res.json())
                .then(
                    (result) => {
                        location.href = course_about_url
                    },
                )
                .catch(error => {
                    console.error('Error:', error)
                })
        } else {
            fetch("/api/program_enrollments/v1/users/" + this.props.username + "/programs/" + this.props.program_uuid + "/courses/", {
                method: 'PATCH',
                headers: {
                    'X-CSRFToken': Cookies.get('csrftoken'),
                },
                body: formData,
            })
                .then(res => res.json())
                .then(
                    (result) => {
                        location.href = course_about_url
                    },
                )
                .catch(error => {
                    console.error('Error:', error)
                })
        }
    }

    render () {
        const pr = this.props.course, st = this.state
        const {
            uuid, course_id, image: {src}, course_enrollment_status, course_detail_description: description,
            course_about_url, title,
            is_course_ended: is_ended, start
        } = pr, prevStatus = this.props.prevCourse ? this.props.prevCourse.course_enrollment_status : ''
        const getActionButton = (text) => {
            return <div className="start_resume_button">
                <a className="nav-link" onClick={() => this.enroll_course(uuid, course_enrollment_status, course_about_url)}>{gettext('%action Course'.replace('%action', text))}</a>
            </div>
        }
        const non_started_course_string = StringUtils.interpolate(gettext('The course will start on {date}'),
        {
            date: getFormatedDate(start, this.props.systemLanguage)
        })

        return <div className="row-course" >
            <a name={course_id}></a>
            <div className="course-image-container">
                {src &&
                    <div className="course-image" style={{"background-image": "linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.5) ), url(" + this.getCourseImg(src) + ")"}}>
                        {
                            !pr.non_started ?
                                (pr.program_enrollment_status == 'enrolled' ?
                                    (pr.user_has_access ?
                                        (course_enrollment_status == 'active' ? (pr.course_completed ? <a id="image-link" href={course_about_url}><div className='lock-wrapper'><span className="fa fa-check"></span></div></a> : getActionButton('Resume')) : getActionButton('Start')) :
                                        <a id="image-link" href={course_about_url}><div className='lock-wrapper'><span className="fa fa-lock"></span></div></a>) :
                                    <a id="image-link" href={course_about_url}></a>) :
                                <div className="mask">
                                    <i className="far fa-calendar-times"></i>
                                    <h2 className="localized-date">{start && non_started_course_string}</h2>
                                </div>
                        }
                    </div>
                }
            </div>
            <div className="course-info">
                <div className="course-title">
                    <a href={course_about_url}><h2>{title}</h2></a>
                </div>

                <ProgramCourseDescription description={description} />

                <div className='sub-info-wrapper'>
                    <small className="sub-info"><i className="far fa-trophy" /><span>{ngettext('%d badge', pr.badges)}</span></small>
                    {!!(pr.duration_availability || pr.duration) && (
                        <small className="sub-info"><i className="far fa-clock" /><span>{getDuration(`${pr.duration} ${pr.duration_unit}`)}</span></small>
                    )}
                    <small className="sub-info"><i className="far fa-calendar-week" /><span>{this.getFormatedDate(start)}</span></small>
                </div>
                {course_enrollment_status == 'active'
                    ? getActionButton('Resume')
                    : (prevStatus == 'active' || prevStatus == '' ? getActionButton('Start') : '')
                }
                {is_ended && (
                    <div>
                        This course is expired.
                    </div>
                )}
            </div>
        </div>
    }
}

function ProgramCourseDescription ({description}) {
    const [isShowMore, setIsShowMore] = React.useState(false)
    const toggleShowMore = React.useCallback(() => setIsShowMore(prev => !prev), [setIsShowMore])
    const [needToggle, setNeedToggle] = React.useState(false)
    const $content = React.useRef()

    React.useEffect(() => {
        if (!$content.current) return
        if ($content.current.clientHeight < $content.current.scrollHeight) setNeedToggle(true)
        return () => {
            setNeedToggle(false)
        }
    }, [])

    if (!description) return null

    return (
        <div className={`description ${isShowMore ? ' displaying-all' : ''}`}>
            <div ref={$content} className='text' dangerouslySetInnerHTML={{__html: description}}></div>
            {needToggle && (
                <div className="see_more_button" onClick={toggleShowMore}>
                    {gettext(isShowMore ? 'See less' : 'Show more')}
                </div>
            )}
        </div>
    )
}


export {ProgramAbout}
