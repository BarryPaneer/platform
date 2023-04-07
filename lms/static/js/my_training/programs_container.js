import React, {Fragment} from "react";
import InfiniteScroll from "react-infinite-scroll-component";

import ProgramCard from "../programs/ProgramCard"
import {ProgramStatus} from '../../../../common/static/js/program-status'  //"../../hawthorn/platform/common/static/js/course-status";
import {TabsTitle} from '.././../../../common/static/js/tabs-title'
import {ExploreBlock} from './explore-block'


const ProgramList = pr => {
    const {new_programs, programs_title, user_progress, language}=pr, programs_list = [];

    (typeof(new_programs) == 'object'?new_programs:JSON.parse(new_programs)).forEach((program, index) => {
            var completed = 0;
            var in_progress = 0;
            var not_started = 0;
            for (var i = 0; i < user_progress.length; i++) {
                if (user_progress[i]['uuid'] == program['uuid']) {
                    completed = user_progress[i]['completed'];
                    in_progress = user_progress[i]['in_progress'];
                    not_started = user_progress[i]['not_started'];
                    break;
                }
            }

            programs_list.push(
                <ProgramCard key={`id-${index}`} systemLanguage={language}
                            {...program} finishedCourseNum={completed} allCourseNum={completed+in_progress+not_started}
                />
            )
        });
    const defaultMessage = pr.defaultMessage || <ExploreBlock url='/programs/' subTitle={gettext('No Learning Path')} title={gettext('You are not enrolled in any Learning Paths yet.')}/>
    return <Fragment>
        {programs_list.length<=0 && defaultMessage}
        {programs_list.length>0 && <div
            className={'container-for-program-cards'}
            dataLength={programs_list.length}
        >
            {programs_list}
        </div>}
    </Fragment>
}


class ProgramsContainer extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            tab_value : 0
        };

        this.not_started_set = new Set();
        this.in_progress_set = new Set();
        this.completed_set = new Set();

        for (var i = 0; i < props.user_progress.length; i++) {
            var completed = props.user_progress[i]['completed'];
            var in_progress = props.user_progress[i]['in_progress'];
            var not_started = props.user_progress[i]['not_started'];

            if (completed === 0 && in_progress === 0) {
                this.not_started_set.add(props.user_progress[i]['uuid']);
            } else if (in_progress > 0) {
                this.in_progress_set.add(props.user_progress[i]['uuid']);
            } else if (completed > 0 && in_progress === 0 && not_started === 0) {
                this.completed_set.add(props.user_progress[i]['uuid']);
            }
        }
    }

    fireOnChange(e, tabItem) {
        const {onChange:onC}=this.props
        this.setState({tab_value: tabItem.value})
        onC && onC(e, tabItem)
    }

    render() {
        const {programs, user_progress, container_title, catalog_enabled, language} = this.props;

        let new_programs = [];

        if (this.state.tab_value === 0) {
            new_programs = programs;
        } else if (this.state.tab_value === 1) {
            for (var i = 0; i < programs.length; i++) {
                if (this.not_started_set.has(programs[i]['uuid'])) {
                    new_programs.push(programs[i]);
                }
            }
        } else if (this.state.tab_value === 2) {
            for (var j = 0; j < programs.length; j++) {
                if (this.in_progress_set.has(programs[j]['uuid'])) {
                    new_programs.push(programs[j]);
                }
            }
        } else if (this.state.tab_value === 4) {
            for (var k = 0; k < programs.length; k++) {
                if (this.completed_set.has(programs[k]['uuid'])) {
                    new_programs.push(programs[k]);
                }
            }
        }

        return (
            <main className="course-container">
                {programs.length<=0 && <ExploreBlock explore={catalog_enabled} url='/programs/' subTitle={gettext('No Learning Path')} title={gettext('You are not enrolled in any Learning Paths yet.')}/>}
                {programs.length>0 && <div>
                    <TabsTitle data={ProgramStatus} onChange={(e,tabItem)=>this.fireOnChange(e,tabItem)}/>
                    <ProgramList {...{new_programs, user_progress, container_title}}
                        language={language}
                        defaultMessage={<div className="empty-message-wrapper"><ExploreBlock subTitle={false} explore={false} title={gettext('There is no Learning Path to display.')}/></div>}
                    />
                </div>}
            </main>
        )
    }
}

export {ProgramsContainer}
