/* eslint-disable react/no-danger, import/prefer-default-export */
import React from 'react';
import {Toolbar} from './Toolbar'
import DataList from "lt-react-data-list"
import {ReportType} from "./Config";
import BaseReport from './BaseReport'
import {DatalistToolbarFooter} from './Common'

export class LearnerReport extends BaseReport {
    constructor(props) {
        super(props);

        this.state = {
            ...this.state,
            properties:[],
        };
    }

    setting = {
        reportType:ReportType.LEARNER,
        dataUrl:'/analytics/learner/json/'
    }

    getDynamicFields () {
        return {
            dynamicFields: [
                {name: gettext('Enrollments'), fieldName: 'Enrollments'},
                {name: gettext('Successful'), fieldName: 'Finished'},
                {name: gettext('Unsuccessful'), fieldName: 'Failed'},
                {name: gettext('In Progress'), fieldName: 'In Progress'},
                {name: gettext('Not Started'), fieldName: 'Not Started'},
                {name: gettext('Average Final Score'), fieldName: 'Average Final Score'},
                {name: gettext('Badges'), fieldName: 'Badges'},
                {name: gettext('Posts'), fieldName: 'Posts'},
                {name: gettext('Total Time Spent'), fieldName: 'Total Time Spent'},
                {name: gettext('Last Login'), fieldName: 'Last Login'}
            ]
        }
    }

    getConfig() {
        return {...this.getBaseConfig()}
    }

    render() {
        const config = this.getConfig()
        return (
            <section className="analytics-wrapper learner">
                <div className="report-wrapper">
                    <Toolbar
                        onChange={(data, isExcluded) => this.toolbarDataUpdate(data, isExcluded || 'isExcluded')}
                        onGo={this.startExport.bind(this)}
                        onInit={properties => this.setState({properties})}
                        enabledItems={['filters', 'properties', 'period', 'export']}
                        periodTooltip={gettext('Display the state of learners at the end of the selected period '
                            + 'for learners who visited the platform during this period. '
                            + 'The total time spent shows the time learners spent on the platform '
                            + 'during the selected period.')}
                    >
                        <h3>{gettext('Learner Report')}</h3>
                    </Toolbar>
                    <DatalistToolbarFooter lastUpdate={this.props.last_update} onApply={this.applyQuery.bind(this)} disabled={this.state.applyDisabled} />
                    <DataList useFontAwesome={true} ref={this.myRef} className="data-list" defaultLanguage={this.props.defaultLanguage}
                              enableRowsCount={true} {...config}
                              fields={this.state.fields}
                              doubleScroll
                    />
                </div>
            </section>
        )
    }
}
