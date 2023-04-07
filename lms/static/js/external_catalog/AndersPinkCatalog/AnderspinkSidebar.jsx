import React from "react";
import Dropdown from "lt-react-dropdown";
import CheckboxGroup from 'lt-react-checkbox-group';
import _ from 'underscore';


class Filter extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            fireChangeCallback: null,
            start: Date.now(),
            value: ''
        }
    }

    fireChange() {
        const {onChange} = this.props;
        onChange && onChange(this.state.value)
    }

    updateValue(e) {
        const DELAY = 600;
        if (Date.now()-this.state.start < DELAY) {
            clearTimeout(this.state.fireChangeCallback)
        }
        this.setState({
            start:Date.now(),
            value: e.target.value,
            fireChangeCallback: setTimeout(this.fireChange.bind(this),DELAY)
        })
    }

    clean() {
        this.setState({value: ''}, this.fireChange.bind(this))
    }

    fireEnterEvent(e) {
        if (e.key == 'Enter') {
            const {onEnterKeyDown} = this.props;
            onEnterKeyDown && onEnterKeyDown(e)
        }
    }

    render() {
        return <div className="searching-field">
            <div className="input-wrapper">
                <input type="text"
                       value={this.state.value}
                       onChange={this.updateValue.bind(this)}
                       onKeyDown={this.fireEnterEvent.bind(this)}
                       placeholder={gettext("Search")}
                />
                <i className="far fa-search"></i>
            </div>
        </div>
    }
}

class DropdownPanel extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            status: props.status
        }
    }

    toggleDisplayStatus() {
        this.setState(prev => {
            return {status: !prev.status}
        })
    }

    render() {
        const {status} = this.state;
        return <li className="dropdown-panel">
            <h4 onClick={this.toggleDisplayStatus.bind(this)}><span>{this.props.title}</span><i
                className={`fa fa-sort-${status ? 'up' : 'down'}`}></i></h4>
            <div className={`component-wrapper ${!status ? 'hide-status' : ''}`}>
                {this.props.children}
            </div>
        </li>
    }
}


class AnderspinkSidebar extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            initializing: true,
            filterValue: '',
            topic: '',
            selectedResources: [],
            selectedReadingTime: [],
            selectedLanguages: [],
        };
        this.refFilter = React.createRef();
        this.refTopic = React.createRef();
        this.refReadingTime = React.createRef();
        this.refLanguages = React.createRef();
        this.refRatingRange = React.createRef();

        this.fireOnChange.bind(this);
        setTimeout(()=>{
            this.setState({initializing:false})
        },1000)
    }

    updateFilterValue(filterValue) {
        this.setState({filterValue}, this.fireOnChange)
    }


    updateDurations(selectedReadingTime) {
        this.setState({
            selectedReadingTime
        }, this.fireOnChange)
    }

    updateLanguages(selectedLanguages) {
        this.setState({
            selectedLanguages
        }, this.fireOnChange)
    }

    updateTopic(topic) {
        this.setState({
            topic
        }, this.fireOnChange)
    }

    fireOnChange() {
        const {props} = this, {onChange} = props;

        const DELAY = 500;
        if (Date.now()-this.start < DELAY) {
            clearTimeout(this.timer)
        }
        this.start = Date.now();

        this.timer = setTimeout(()=>{
            onChange && onChange(this.getData());
        }, DELAY)
    }

    getData() {
        return _.pick(this.state, ['filterValue', 'topic', 'selectedResources', 'selectedReadingTime', 'selectedLanguages',
    ])
    }

    toggle() {
        const {onToggle,status} = this.props;
        onToggle && onToggle(!status)
    }

    apply() {
        const {onApply} = this.props;
        onApply && onApply(this.getData())
    }

    reset() {
        const {onReset} = this.props;
        this.refFilter.current.clean();
        this.refTopic.current.clean();
        this.refReadingTime.current && this.refReadingTime.current.clean();
        this.refLanguages.current && this.refLanguages.current.clean();
        this.refRatingRange.current && this.refRatingRange.current.clean();
        onReset && onReset(this.getData());
    }

    render() {
        const {status, resources, briefings, reading_time, languages, ratingRange} = this.props;
        const optionRender = text => gettext(text);
        return (
            <aside className={`sidebar ${status ? '' : ' hide-status'} ${this.state.initializing?' hidden':''}`}>
                <div className="filters-wrapper" onClick={this.toggle.bind(this)}>
                    <h4>{gettext("Filters")}</h4>
                    <i className={`fal ${status ? 'fa-outdent' : ' fa-indent'}`}></i>
                </div>
                <Filter ref={this.refFilter} onChange={this.updateFilterValue.bind(this)}
                        onEnterKeyDown={this.apply.bind(this)}/>
                <div className="topic-wrapper">
                    <h4>{gettext("Briefing")}</h4>
                    <Dropdown ref={this.refTopic} className={'topics'} data={briefings}
                              searchable={true} optionRender={optionRender}
                              onChange={this.updateTopic.bind(this)}/>
                </div>
                <ul>
                     <DropdownPanel status={true} title={gettext('Reading Time')}>
                        <CheckboxGroup ref={this.refReadingTime} data={reading_time}
                                       onChange={this.updateDurations.bind(this)}/>
                    </DropdownPanel>
                    <DropdownPanel status={true} title={gettext('Language')}>
                        <CheckboxGroup ref={this.refLanguages} data={languages}
                                       onChange={this.updateLanguages.bind(this)}/>
                    </DropdownPanel>
                </ul>
                <div className="actions">
                    <input type="button" className="apply-button" value={gettext("Apply")} onClick={this.apply.bind(this)}/>
                    <button className="reset-button" onClick={this.reset.bind(this)}>
                        <i className="far fa-rotate"></i>
                        <span>{gettext("Reset")}</span>
                    </button>
                </div>
            </aside>
        )
    }
}

export {AnderspinkSidebar}
