import BaseReport from "./BaseReport";
import {ReportType} from "./Config";
import {Toolbar} from "./Toolbar";
import DataList from "lt-react-data-list";
import React from "react";
import {LastUpdate,StatusRender,PercentRender} from "./Common"
import {pick} from 'lodash'

export class Transcript extends BaseReport {
    constructor(props) {
        super(props);

        this.state = {

            ...this.state,
            properties:[],
        };
        console.log(pick(this.state, ['userID']))

        this.setting = {
            extraParams: this.getExtraParams(),
            reportType:ReportType.TRAN_SCRIPT,
            dataUrl: props.dataUrl || '/analytics/transcript/json/',
        }
    }

    getExtraParams() {
        const matches = window.location.pathname.match(/[transcript|pdf]\/(\d+)/)
        return matches && matches.length ? {user_id: matches[1]} : {}
    }

    getFields () {
        const statusRender = { render:StatusRender}, percentRender = { render:PercentRender}
        return {
            fields: [
                {name: gettext('Course Title'), fieldName: 'Course Title', render:(value)=>{
                    return <div dangerouslySetInnerHTML={{__html: value}} />
                }},
                ...(this.props.withGradebookLink ? [{
                    name: ' ', fieldName: 'Gradebook Link', render:(value)=>{
                        return <div dangerouslySetInnerHTML={{__html: value}} />
                    }
                }] : []),
                {name: gettext('Status'), fieldName: 'Status', ...statusRender, className:'status'},
                {name: gettext('Progress'), fieldName: 'Progress', ...percentRender},
                {name: gettext('Badges'), fieldName: 'Badges'},
                {name: gettext('Current Score'), fieldName: 'Current Score', ...percentRender},
                {name: gettext('Total Time Spent'), fieldName: 'Total Time Spent'},
                {name: gettext('Enrollment Date'), fieldName: 'Enrollment Date'},
                {name: gettext('Completion Date'), fieldName: 'Completion Date'}
            ],
        }
    }

    getConfig() {
        return {...{
            enableRowsCount:true,
        }, ...this.getBaseConfig()}
    }

    render() {
        let config = this.getConfig()
        const {last_update,disable_last_update,defaultLanguage, disablePagination}=this.props
        if (disablePagination) {
            config = {...config, pagination:false}
        }
        return (
            <>
                <Toolbar
                    enabledItems={['export']}
                    onChange={this.toolbarDataUpdate.bind(this)}
                    onGo={this.startExport.bind(this)}
                    onInit={properties=>this.setState({properties})}
                />
                {!disable_last_update && <LastUpdate last_update={last_update} />}
                <DataList useFontAwesome={true} ref={this.myRef} className="data-list" defaultLanguage={defaultLanguage}
                          {...config}
                          fields={this.state.fields}
                          doubleScroll
                />
            </>
        )
    }
}
