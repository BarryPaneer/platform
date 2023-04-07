import React, {Fragment} from "react"
import InfiniteScroll from "react-infinite-scroll-component"
import ProgramCard from "../programs/ProgramCard"
import {CourseCard} from "../programs/CourseCard"
import {ExploreBlock} from "./explore-block"

const ProgramList = pr => {
    const {programs, programs_title, user_progress, language} = pr, programs_list = [];

    (typeof (programs) == 'object' ? programs : JSON.parse(programs)).forEach((program, index) => {
        var completed = 0
        var in_progress = 0
        var not_started = 0
        for (var i = 0; i < user_progress.length; i++) {
            if (user_progress[i]['uuid'] == program['uuid']) {
                completed = user_progress[i]['completed']
                in_progress = user_progress[i]['in_progress']
                not_started = user_progress[i]['not_started']
                break
            }
        }

        programs_list.push(
            <ProgramCard key={`id-${index}`} systemLanguage={language}
                {...program} finishedCourseNum={completed} allCourseNum={completed + in_progress + not_started}
            />
        )
    })
    return <Fragment>
        {programs_list.length > 0 && <div
            className={'container-for-program-cards'}
            dataLength={programs_list.length}
        >
            {programs_list}
        </div>}
    </Fragment>
}

class OverviewContainer extends React.Component {
    constructor (props) {
        super(props)
    }

    fireIndentClick () {
        const {onIndentClick} = this.props
        onIndentClick && onIndentClick()
    }

    fireNext () {
        const {onNext} = this.props
        onNext && onNext()
    }

    render () {
        try {
            const {programs, user_progress, courses, programs_title, courses_title, catalog_enabled, language} = this.props

            const courses_list = [];

            //const maxOfProgramList = 4
            (typeof (courses) == 'object' ? courses : JSON.parse(courses)).forEach((course, index) => {
                courses_list.push(
                    <CourseCard key={`id-${index}`} enableProgress={true} linkType={'course'}
                        {...course} systemLanguage={language}
                    />
                )
            })

            const programs_list = typeof (programs) == 'object' ? programs : JSON.parse(programs)

            // the user is not enrolled in any LP or course
            var explore_mode = ''
            if (courses_list.length > 0 && programs_list.length <= 0) {
                explore_mode = 'programs'
            } else if (programs_list.length > 0 && courses_list.length <= 0) {
                explore_mode = 'course'
            } else if (programs_list.length <= 0 && courses_list.length <= 0) {
                explore_mode = 'all'
            }

            return (
                <main className="course-container">

                    {explore_mode == 'all' && <ExploreBlock explore={catalog_enabled} url='/courses_overview/' subTitle={gettext('Begin a Learning Path or a Course now')} title={gettext('You are not enrolled in any Trainings yet.')} />}

                    {explore_mode != 'all' && <div className="program-list-wrapper">
                        <div className='catalog_name-wrapper'>
                            <span className={'category_name'}>{gettext(programs_title)}</span>
                            <span className={'view_all_button'}>
                                <a className={'button_underline'} href="/my_training_programs/">{gettext("View all")}</a> &gt;
                            </span>
                        </div>
                        {explore_mode == 'programs' && <ExploreBlock explore={catalog_enabled} url='/programs/' subTitle={gettext('No Learning Path')} title={gettext('You are not enrolled in any Learning Paths yet.')} />}
                        {programs_list.length > 0 && <div>
                            <ProgramList {...{programs: programs_list, user_progress, programs_title}} language={language} />
                        </div>}
                    </div>}
                    {explore_mode != 'all' && <div className="course-list-wrapper">
                        <div className='catalog_name-wrapper'>
                            <span className={'category_name'}>{gettext(courses_title)}</span>
                            <span className={'view_all_button'}>
                                <a className={'button_underline'} href="/my_courses/all-courses/">{gettext("View all")}</a> &gt;
                            </span>
                        </div>
                        {explore_mode == 'course' && <ExploreBlock explore={catalog_enabled} url='/courses/' subTitle={gettext('No Course')} title={gettext('You are not enrolled in any courses yet.')} />}
                        {courses_list.length > 0 && <InfiniteScroll
                            dataLength={courses_list.length}
                        >
                            {courses_list}
                        </InfiniteScroll>}
                    </div>}
                </main>
            )
        } catch (e) {
            console.error('Error  :  ', e)
        }
    }
}

export {OverviewContainer, ProgramList}
