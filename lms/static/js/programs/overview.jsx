import React from "react";
import ReactDOM from "react-dom";

import {CoursesProgramsContainer} from './CoursesProgramsContainer'
import {IsDebug} from '../../../../common/static/js/global_variable'
import {Banner} from '../com/banner'
import {Module} from '../com/tabs'
import {MockedCourseResult, MockedProgramResult} from "../mock_data/program";

class CoursesOverview extends React.Component {
    constructor(props) {
        super(props);
    }

    render() {
        try {
            return (
                <section className="find-courses">
                    <Banner module={Module.explore} showTabs={this.props.is_program_enabled} switcher={this.props.external_button_url} />
                    <div className="courses-wrapper overview_margin">
                        <CoursesProgramsContainer
                            language={this.props.language}
                            programs={IsDebug?MockedProgramResult.results:this.props.programs}
                            courses={IsDebug?MockedCourseResult.results:this.props.courses}
                            programs_title={this.props.programs_title}
                            courses_title={this.props.courses_title}
                        />
                    </div>
                </section>
            )
        } catch(e) {
            console.error('Error:', e);
        }
    }
}

export {CoursesOverview, Banner, Module, React, ReactDOM}
