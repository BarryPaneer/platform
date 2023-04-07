import ReactDOM from "react-dom";
import React from "react";
import {IsDebug} from "../../../../common/static/js/global_variable";
import {MockedProgramResult} from "../mock_data/program";
import {ProgramAbout} from "../programs/ProgramAbout";

const Initialize2 = (
        {
            language, program_uuid, theme_dir_name, program,
            program_courses_completed, program_courses_total,
            enrollment_status,
            username,
            studioLink,
            isAdmin
        }
    )=>{
    const pageUrl=window.location.href,
        isProgramAboutPage=()=>{return pageUrl.indexOf('/about')>=0 || pageUrl.indexOf('/about2')>=0}
    if (isProgramAboutPage()) {
        ReactDOM.render(
            React.createElement(ProgramAbout, {
                systemLanguage: language,
                program_uuid: program_uuid,
                theme_dir_name: theme_dir_name,
                program: IsDebug?MockedProgramResult.results[0]: program,
                program_courses_completed: program_courses_completed,
                program_courses_total: program_courses_total,
                enrollment_status: enrollment_status,
                username: username,
                isAdmin: isAdmin,
                studioLink,
            }, null),
            document.querySelector('#content')
        );
    }
}

export {ProgramAbout, Initialize2}
