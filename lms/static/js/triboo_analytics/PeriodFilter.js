import React from "react";
import DateRange from 'lt-react-date-range';
import {QuestionMark} from '../QuestionMark';


class PeriodFilter extends React.Component {
    constructor(props, context) {
        super(props, context);
    }

    render() {
        return (
            <div className="period-wrapper">
                <div id="id-period-filter" className="question-mark">
                    <QuestionMark tooltip={this.props.periodTooltip} />
                </div>
                <DateRange name={this.name}
                           text={this.text}
                           icon={this.icon}
                           {...this.props} />
            </div>
        )
    }
}
export {PeriodFilter}


