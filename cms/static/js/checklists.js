'use strict';
import Cookies from 'js-cookie';
import React from 'react';
import StringUtils from 'edx-ui-toolkit/js/utils/string-utils';


export function Checklists ({course_key, display, step_1_url, step_2_url, step_3_url, step_4_url, step_5_url, step_6_url, step_7_url}) {

    function getChecklistsURL() {
        return `/api/courses/v1/steps_validation/${course_key}/`;
    }

    const [steps, setSteps] = React.useState([]);

    function switch_checklist(e) {
        if ($('#studio-checklist').hasClass('hide_checklists')) {
            $('#studio-checklist').removeClass('hide_checklists');
            $('#studio-checklist').addClass('show_checklists');
            $('#id_rocket_icon_placeholder').removeClass('show_checklists');
            $('#id_rocket_icon_placeholder').addClass('hide_checklists');
            $('#id_rocket_icon_placeholder').addClass('rocket_icon_placeholder');

            fetch(
                getChecklistsURL(), {
                    method: 'GET',
                    headers: {
                      'Accept': 'application/json',
                      'X-CSRFToken': Cookies.get('csrftoken')
                    }
                }
             )
                .then(response => response.json())
                .then(data => setSteps(data));

        } else {
            $('#studio-checklist').removeClass('show_checklists');
            $('#studio-checklist').addClass('hide_checklists');
            $('#id_rocket_icon_placeholder').removeClass('hide_checklists');
            $('#id_rocket_icon_placeholder').addClass('show_checklists');
            $('#id_rocket_icon_placeholder').addClass('rocket_icon_placeholder');
        }
    }

    function handleCheckBoxEvent (e, step) {
        const {key: field_key, status} = step;
        const payload = {'steps_logs': {}};
        payload['steps_logs'][field_key] = status === 0 ? 1 : 0;

        fetch(
            getChecklistsURL(), {
                method: 'POST',
                headers: {
                  'Accept': 'application/json',
                  'Content-Type': 'application/json',
                  'X-CSRFToken': Cookies.get('csrftoken'),
                },
                body: JSON.stringify(payload)
            }
         )
            .then(response => response.json())
            .then(data => setSteps(data));

        e.stopPropagation();    // stop passing UI event from current div to another html element
    }

    function onCloseChecklists(e) {
        $('#studio-checklist').removeClass('show_checklists');
        $('#studio-checklist').addClass('hide_checklists');
        $('#id_rocket_icon_placeholder').removeClass('hide_checklists');
        $('#id_rocket_icon_placeholder').addClass('show_checklists');
        $('#id_rocket_icon_placeholder').addClass('rocket_icon_placeholder');
    }

    function onRedirectToURL(e, index) {
        const URLs = [step_1_url, step_2_url, step_3_url, step_4_url, step_5_url, step_6_url, step_7_url];
        window.location.replace(URLs[index]);
    }

    React.useEffect(() => {
        const fetchData = async () => {
            const response = await fetch(getChecklistsURL());
            const json = await response.json();

            setSteps(json);
        }

        fetchData();
    }, []);

    return (
        <div>
            <div id="studio-checklist" className={(display === true) ? "show_checklists": "hide_checklists"}>
                <div className="checklist-container" id="checklist-container-id">
                    <div className="checklist-title">
                        <span className="title_string">{gettext('Quick Start')}</span>
                        <span className="close_checklist" onClick={e =>{onCloseChecklists(e)}}>
                            <i className="fa fa-times" aria-hidden="true"></i>
                        </span>
                    </div>
                    <div className="checklist-summary">{gettext('Make sure you don\'t forget anything when creating your course by checking off each step in the list.')}</div>
                    <div className="checklist-summary checklist-help" dangerouslySetInnerHTML={{__html: StringUtils.interpolate(gettext('Find more help {tag_start}here{tag_end}'),{tag_start: '<a target="_blank" href="https://csc.learning-tribes.com/category/create-courses/">', tag_end: '</a>'})}}/>
                    <div className="checklists-scrollable-list">
                    {
                        steps.map((step, index) => (
                            <div className={"checklist-item " + (step.status === 0 ? ' uncheck_status' : '')} onClick={e => {onRedirectToURL(e, index)}}>
                                <div className="checkpoint-wrapper">
                                    <div className="checkpoint-item checkpoint_flow_item" item_name={step.key} item_value={step.status} onClick={e => {handleCheckBoxEvent(e, step)}}>
                                        <div className={"checkbox_icon " + (step.status === 1 ? "checked" : "unchecked")}/>
                                    </div>
                                </div>
                                <div className={"checkpoint-information" + (step.status === 0 ? ' unchecked_status' : '')}>
                                    <div className="step-status">
                                        <span className={"step-name " + (step.status === 1 ? 'checked_step_green' : 'unchecked_step_grey')}>{StringUtils.interpolate(gettext('Step {num}'), {num: step.name})}</span>
                                        <span className={"step-status-value " + (step.status === 1 ? 'checked_status_green' : 'unchecked_status_grey')}>{step.status === 1 ? gettext('Complete') : gettext('Incomplete')}</span>
                                    </div>
                                    <div className="step-description">
                                        <span className={"checkitem-info " + (step.status === 1 ? 'checked_green' : 'unchecked_grey')}>{gettext(step.desc)}</span>
                                        <span className={"external-url-bt " + (step.status === 1 ? 'green_arrow' : 'black_arrow')}>
                                            <i className="fa fa-external-link" aria-hidden="true"></i>
                                        </span>
                                    </div>
                                </div>
                            </div>
                            )
                        )
                    }
                    </div>
                </div>
            </div>
            <div id="id_rocket_icon_placeholder" className={"rocket_icon_placeholder " + ((display === true) ? "hide_checklists": "show_checklists")}>
                <div className="rocket_icon_container" onClick={e => {switch_checklist(e)}}>
                    <i className="fa-light fa-rocket-launch">
                        <span className="rocket_title">{gettext('Quick Start')}</span>
                    </i>
                </div>
            </div>
        </div>
    );
}
