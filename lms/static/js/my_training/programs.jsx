import React from "react";
import {ProgramsContainer} from './programs_container.js'
import {IsDebug} from '../../../../common/static/js/global_variable'
import {MockedProgramResult} from '../mock_data/program'
import {Banner} from '../com/banner'
import {Module} from '../com/tabs'


class MyTrainingPrograms extends React.Component {
    constructor(props) {
        super(props);
    }

    render() {
        return (
            <section className="find-courses">
                <Banner module={Module.myTraining} showTabs={this.props.is_program_enabled}/>

                <div className="courses-wrapper">
                    <ProgramsContainer
                        container_title={this.props.programs_title}
                        programs={IsDebug?MockedProgramResult.results:JSON.parse(this.props.programs)}
                        user_progress={JSON.parse(this.props.user_progress)}
                        catalog_enabled={this.props.catalog_enabled}
                        language={this.props.language}
                    />
                </div>
            </section>
        )
    }
}

export {MyTrainingPrograms};
