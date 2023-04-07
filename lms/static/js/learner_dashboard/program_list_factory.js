import {MockedProgramResult} from '../mock_data/program'
import {IsDebug} from '../../../../common/static/js/global_variable'
import {ProgramList} from '../my_training/overview_container'

import React, {Fragment} from 'react';
import ReactDOM from 'react-dom'
import {ExploreBlock} from "../my_training/explore-block";
const ProgramsListTrimed = pr=>{
    return <Fragment>
        {pr.programs.length<=0 && <ExploreBlock explore={pr.catalog_enabled} url='/programs/' subTitle={gettext('No Learning Path')} title={gettext('You are not enrolled in any Learning Paths yet.')} theme='triboo-flag'/>}
        {pr.programs.length>0 && <ProgramList programs={pr.programs} user_progress={pr.user_progress} language={pr.language}/>}
    </Fragment>
}
function ProgramListFactory(options) {
    ReactDOM.render(
        React.createElement(ProgramsListTrimed, {
            programs:IsDebug?MockedProgramResult.results:options.programs,
            user_progress:options.user_progress || [],
            catalog_enabled:options.catalog_enabled,
            language:options.language,
        }, null),
        document.querySelector('.program-cards-container')
    );

}

export { ProgramListFactory };
