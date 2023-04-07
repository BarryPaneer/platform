import React from 'react';
import {Toolbar} from "./Toolbar";
import DataList from "lt-react-data-list";
import {PaginationConfig, ReportType} from "./Config";
import BaseReport from './BaseReport'
import {pick, flatten} from "lodash";
import {DatalistToolbarFooter} from './Common'

export default class CourseReportTimeSpent extends BaseReport {
    constructor(props) {
        super(props);

        this.state = {
            ...this.state,
            properties:[],
        };
    }

    setting = {
        extraParams:{course_id: this.props.course_id},
        reportType:ReportType.COURSE_TIME_SPENT,
        dataUrl:'/analytics/course/json/'
    }

    getDynamicFields() {
        const {data, columns} = this.state
        const propertiesValues = this.state.properties.map(p=>p.value)

        let dynamicFields = [], subFields = []
        if (data && data.length > 0) {
            const firstRow = data[0]
            const dynamicKeys = Object.keys(firstRow)
                .filter(key=>{
                    return !propertiesValues.includes(key) && key != 'Name' // && !key.split('/')[1]
                })
            const complexDynamicKeys = columns.length > 0 ? columns :
                dynamicKeys.filter(key=>key.split('/')[1])
            const complexDynamicKeysL1 = complexDynamicKeys.map(key=>key.split('/')[0])
            const normalDynamicFields = dynamicKeys.filter(key=>!key.split('/')[1])
            const complexDynamicFields = [...new Set(complexDynamicKeys.map(key=>key.split('/')[0]))]
            const countSpan = (key)=>{
                return complexDynamicKeysL1.filter(l1key=>key==l1key).length
            }

            dynamicFields = [...normalDynamicFields.map(key=>({name:key,fieldName:key})),
                ...complexDynamicFields.map(key=>({name:key,fieldName:key, colSpan:countSpan(key)}))]
            subFields = flatten(complexDynamicFields.map(keyL1=>{
                return complexDynamicKeys.filter(key=>{
                    return key.split('/')[0] == keyL1
                }).map(key=>{
                    const arr = key.split('/')
                    const keyL2 = arr[1]
                    return {name:keyL2,fieldName:key}
                })
            }))
        }
        return {dynamicFields, subFields}
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
                         periodTooltip={gettext('Display the time learners spent in the course during the selected period '
                                              + 'for learners who visited the course during this period.')}/>
                <DatalistToolbarFooter lastUpdate={this.props.last_update} onApply={this.applyQuery.bind(this)} disabled={this.state.applyDisabled} />
                <DataList useFontAwesome={true} ref={this.myRef} className="data-list" defaultLanguage={this.props.defaultLanguage}
                          enableRowsCount={true} {...config}
                          fields={this.state.fields}
                          subFields={this.state.subFields}
                          doubleScroll
                />
            </>
        )
    }
}
