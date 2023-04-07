/* eslint-disable react/no-danger, import/prefer-default-export */
import React from 'react';
import {Toolbar} from './Toolbar'
import DataList from "lt-react-data-list"
import {PaginationConfig, ReportType} from "./Config";
import BaseReport from './BaseReport'
import {pick, get} from "lodash";
import {DatalistToolbarFooter} from './Common'

export default class ILTGlobalReport extends BaseReport {
    constructor(props) {
        super(props);
        this.state = {
            ...this.state,
            properties:[],
        };
    }

    setting = {
        reportType: ReportType.ILT_GLOBAL,
        dataUrl: '/analytics/ilt/json/'
    }

    generateParameter () {
        const {toolbarData} = this.state
        const getVal = (key, defaultValue) => {
            return toolbarData && toolbarData[key] ? toolbarData[key] : defaultValue || ''
        }

        return {
            report_type: get(this.setting, 'reportType', ''),
            query_tuples: get(toolbarData, 'selectedFilterItems', []).map(p => [p.value, p.key]),
            selected_properties: get(toolbarData, 'selectedProperties', []).map(p => p.value),
            selected_courses: get(toolbarData, 'selectedCourses', []).map(p => p.value).join(','),
            from_day: getVal('startDate'),
            to_day: getVal('endDate'),
            csrfmiddlewaretoken: this.props.token,
            page: {
                size: this.props.pageSize || PaginationConfig.PageSize
            },
            ...get(this.setting, 'extraParams', {}),
        }
    }

    getFields () {
        const translationRender={
            render:v=>gettext(v)
        }
        return {
            fields: [
                {name: gettext('Geographical area'), fieldName: 'Geographical area', ...translationRender},
                {name: gettext('Course country'), fieldName: 'Course country', ...translationRender},
                {name: gettext('Zone/Region'), fieldName: 'Zone/Regionn', ...translationRender},
                {name: gettext('Course tags'), fieldName: 'Course tags'},

                {name: gettext('Course code'), fieldName: 'Course code'},
                {name: gettext('Course name'), fieldName: 'Course name'},
                {name: gettext('Section'), fieldName: 'Section'},
                {name: gettext('Subsection'), fieldName: 'Subsection'},

                {name: gettext('Session ID'), fieldName: 'Session ID'},
                {name: gettext('Start date'), fieldName: 'Start date'},
                {name: gettext('Start time'), fieldName: 'Start time'},
                {name: gettext('End date'), fieldName: 'End date'},

                {name: gettext('End time'), fieldName: 'End time'},
                {name: gettext('Duration (in hours)'), fieldName: 'Duration (in hours)'},
                {name: gettext('Max capacity'), fieldName: 'Max capacity'},
                {name: gettext('Enrollees'), fieldName: 'Enrollees'},

                {name: gettext('Attendees'), fieldName: 'Attendees', ...translationRender},
                {name: gettext('Attendance sheet'), fieldName: 'Attendance sheet'},
                {name: gettext('Location ID'), fieldName: 'Location ID'},
                {name: gettext('Location name'), fieldName: 'Location name'},

                {name: gettext('Location address'), fieldName: 'Location address'},
                {name: gettext('Zip code'), fieldName: 'Zip code'},
                {name: gettext('City'), fieldName: 'City'},
            ],
        }
    }

    getConfig() {
        return {...this.getBaseConfig()}
    }

    render() {
        const config = this.getConfig()
        return (
            <>
                <Toolbar onChange={(data, isExcluded) => this.toolbarDataUpdate(data, isExcluded || 'isExcluded')}
                    enabledItems={['ILTGlobalFilters', 'period', 'export']}
                     onGo={this.startExport.bind(this)}
                     {...pick(this.props, ['onTabSwitch', 'defaultToolbarData', 'defaultActiveTabName'])}
                     onInit={properties=>this.setState({properties})}
                     periodTooltip={gettext('Filter the sessions starting in the selected period.')}/>
                <DatalistToolbarFooter lastUpdate={this.props.last_update} onApply={this.applyQuery.bind(this)} disabled={this.state.applyDisabled} />
                <DataList useFontAwesome={true} ref={this.myRef} className="data-list" defaultLanguage={this.props.defaultLanguage}
                          enableRowsCount={true} {...config}
                          fields={this.state.fields}
                          doubleScroll
                />
            </>
        )
    }
}
