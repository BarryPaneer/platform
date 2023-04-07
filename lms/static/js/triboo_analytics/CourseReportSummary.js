import React from 'react';
import {Toolbar} from "./Toolbar";
import DataList from "lt-react-data-list";
import {ReportType} from "./Config";
import BaseReport from './BaseReport'
import {pick} from "lodash";
import PropTypes from "prop-types";
import {PercentRender, StatusRender, DatalistToolbarFooter} from "./Common";

export default class CourseReportSummary extends BaseReport {
    constructor(props) {
        super(props);

        this.state = {
            ...this.state,
            properties:[],
        };
    }

    setting = {
        extraParams:{course_id: this.props.course_id},
        reportType:ReportType.COURSE_SUMMARY,
        dataUrl:'/analytics/course/json/'
    }

    getDynamicFields () {
        const statusRender = { render:StatusRender}, percentRender = { render:PercentRender}
        return {
            dynamicFields: [
                {name: gettext('Status'), fieldName: 'Status', ...statusRender, className:'status'},
                {name: gettext('Progress'), fieldName: 'Progress', ...percentRender},
                {name: gettext('Current Score'), fieldName: 'Current Score'},
                {name: gettext('Badges'), fieldName: 'Badges'},
                {name: gettext('Posts'), fieldName: 'Posts'},
                {name: gettext('Total Time Spent'), fieldName: 'Total Time Spent'},
                {name: gettext('Enrollment Date'), fieldName: 'Enrollment Date'},
                {name: gettext('Completion Date'), fieldName: 'Completion Date'},
            ]
        }
    }

    getConfig() {
        return {...{
            keyField:"ID",
        }, ...this.getBaseConfig()}
    }

    render() {
        const config = this.getConfig()
        return (
            <>
                <Toolbar onChange={(data, isExcluded) => this.toolbarDataUpdate(data, isExcluded || 'isExcluded')}
                         onGo={this.startExport.bind(this)}
                         enabledItems={['filters', 'properties', 'period', 'export']}
                         {...pick(this.props, ['onTabSwitch', 'defaultToolbarData', 'defaultActiveTabName'])}
                         onInit={properties=>this.setState({properties})}
                         periodTooltip={gettext('Display the state of learners at the end of the selected period '
                                             + 'for learners who visited the course during this period.')}/>
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

CourseReportSummary.propTypes = {
    defaultLanguage: PropTypes.string,
    token: PropTypes.string,
    course_id: PropTypes.string,
    defaultToolbarData:PropTypes.object,
    onChange:PropTypes.func
}
