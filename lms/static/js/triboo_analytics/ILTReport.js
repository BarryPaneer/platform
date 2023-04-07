/* eslint-disable react/no-danger, import/prefer-default-export */
import React from 'react'
import Tab from "lt-react-tab"
import ILTGlobalReport from './ILTGlobalReport'
import ILTLearnerReport from './ILTLearnerReport'
import {pick} from "lodash"
import 'url-search-params-polyfill'

export class ILTReport extends React.Component {
    constructor (props) {
        super(props)
        this.state = {
            activeTabName: '',
            toolbarData: {}
        }
        this.myRef = React.createRef()
    }

    render () {
        const commonProps = {
            ...pick(this.props, 'defaultLanguage', 'token', 'last_update'),
            defaultToolbarData: this.state.toolbarData,
            defaultActiveTabName: this.state.activeTabName,
            onTabSwitch: activeTabName => this.setState({activeTabName}),
            onChange: toolbarData => this.setState({toolbarData}),
        }
        const data = [
            {text: gettext('ILT Global Report'), value: 'global', component: ILTGlobalReport, props: commonProps},
            {text: gettext('ILT Learner Report'), value: 'learner', component: ILTLearnerReport, props: commonProps}
        ]

        return (
            <>
                <h3>{gettext('ILT Report')}</h3>
                <Tab activeValue={(new URLSearchParams(location.search)).get('report')} data={data}>
                    <div className="last-update">
                        <span className="far fa-rotate"></span>{gettext("Please, note that these reports are not live. Last update:")} {this.props.last_update}
                    </div>
                </Tab>
            </>
        )
    }
}
