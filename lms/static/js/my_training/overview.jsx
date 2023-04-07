import React from "react";
import {OverviewContainer} from './overview_container'
import {IsDebug} from '../../../../common/static/js/global_variable'
import {MockedProgramResult, MockedCourseResult} from '../mock_data/program'
import {Banner} from '../com/banner'
import {Module} from '../com/tabs'

class MyTrainingOverview extends React.Component {
    constructor(props) {
        super(props);
    }

    render() {
        try {
            return (
                <section className="find-courses">
                    <Banner module={Module.myTraining} showTabs={this.props.is_program_enabled}/>

                    <div className="courses-wrapper overview_margin">
                        <OverviewContainer
                            language={this.props.language}
                            programs={IsDebug?MockedProgramResult.results:this.props.programs}
                            courses={IsDebug?MockedCourseResult.results:this.props.courses}
                            user_progress={JSON.parse(this.props.user_progress)}
                            programs_title={this.props.programs_title}
                            courses_title={this.props.courses_title}
                            catalog_enabled={this.props.catalog_enabled}
                        />
                    </div>
                </section>
            )
        } catch(e) {
            console.error('Error:', e);
        }
    }
}

export {MyTrainingOverview};
