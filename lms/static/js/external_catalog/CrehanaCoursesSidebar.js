import React from "react";
import Dropdown from "lt-react-dropdown"
import CheckboxGroup from 'lt-react-checkbox-group'
import _ from 'underscore';
import PropTypes from 'prop-types'
import styled from 'styled-components'


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

const CheckboxWrapperEx = styled.ul`
    list-style: none;
    padding:0;
    margin:0;

    li {
        display: inline-block;
        width: 20%;
    }
`

class StarCheckboxGroup extends React.Component {
    constructor(props, context) {
        super(props, context);

        const checkedList = props.checkedList || []

        this.state = {
            prefire: props.prefire,
            checkedList
        };
    }

    componentDidMount() {
        if (this.props.data.length > 0 && (this.props.checkedList || []).length > 0 && this.state.prefire){
            this.fireChange()
        }
    }

    UNSAFE_componentWillReceiveProps(nextProps, nextContext) {
        if (nextProps.data.length > 0 &&
            JSON.stringify(this.props.data) != JSON.stringify(nextProps.data) &&
            (this.props.checkedList || []).length > 0 && this.state.prefire) {
            setTimeout(this.fireChange.bind(this), 100)
        }
    }

    clean(){
        this.setState({checkedList:[]}, this.fireChange.bind(this))
    }

    changeCheckboxStatus(e, item) {
        let checkedList =this.state.checkedList;
        if (e.target.checked){
             checkedList.push(item.value)
            this.setState({checkedList}, this.fireChange.bind(this))
        }else{
            checkedList = checkedList.filter(val=>val !== item.value)
            this.setState({ checkedList }, this.fireChange.bind(this))
        }
    }

    fireChange(){
        const {onChange, data} = this.props
        const checkedItems = data.filter(p=>this.state.checkedList.includes(p.value))
        onChange && onChange(checkedItems)
    }

    render() {
        const {data, optionRender} = this.props;
        const getItemText=(item)=>{
            return optionRender ? optionRender(item.text, item) : (item.text || item.value)
        }

        return (
            <CheckboxWrapperEx className={'lt-react-checkbox-group ' + (this.props.className || '')}>
                {data.map(item => {
                    var stars = [];
                    const id = 'star-lt-react-checkbox-group-box' + item.value;
                    for(var i = 1; i <= 5; i++) {
                        if( item.value >= i ) {
                            stars.push(<i className="fa fa-star"></i>);
                        } else if( item.value >= (i-0.5) && item.value < i ) {
                            stars.push(<i className="far fa-star-half-stroke"></i>);
                        } else {
                            stars.push(<i className="far fa-star"></i>);
                        }
                    }
                    return (
                        <li key={item.value}>
                            <input type="checkbox" id={id} value={item.value}
                                   checked={this.state.checkedList.includes(item.value)} onChange={e => this.changeCheckboxStatus(e, item)}/>
                            <label htmlFor={id} title={getItemText(item)}>{stars}</label>
                            {item.label && <span>{item.label}</span>}
                        </li>
                    )
                })}
            </CheckboxWrapperEx>
        );
    }
}

StarCheckboxGroup.propTypes = {
    data:PropTypes.arrayOf(PropTypes.shape({
        value:PropTypes.oneOfType([
            PropTypes.string,
            PropTypes.number
        ]),
        text:PropTypes.string,
        label:PropTypes.oneOfType([
            PropTypes.string,
            PropTypes.number
        ])
    })),
    prefire:PropTypes.bool,
    checkedList:PropTypes.arrayOf(PropTypes.string),
    onChange:PropTypes.func,
}


class CoursesSideBar extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            initializing: true,
            filterValue: '',
            topic: '',
            selectedResources: [],
            selectedDurations: [],
            selectedLanguages: [],
            selectedRatingRange: [],
        };
        this.refFilter = React.createRef();
        this.refTopic = React.createRef();
        this.refDurations = React.createRef();
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

    updateRatingRange(selectedRatingRange) {
        this.setState({
            selectedRatingRange
        }, this.fireOnChange)
    }

    updateDurations(selectedDurations) {
        this.setState({
            selectedDurations
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
        return _.pick(this.state, ['filterValue', 'topic', 'selectedResources', 'selectedDurations', 'selectedLanguages', 'selectedRatingRange'])
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
        this.refDurations.current && this.refDurations.current.clean();
        this.refLanguages.current && this.refLanguages.current.clean();
        this.refRatingRange.current && this.refRatingRange.current.clean();
        onReset && onReset(this.getData());
    }

    render() {
        const {status, resources, courseCategories, durations, languages, ratingRange} = this.props;
        const optionRender = text => gettext(text);
        return (
            <aside className={`sidebar ${status ? '' : ' hide-status'} ${this.state.initializing?' hidden':''}`}>
                <div className="filters-wrapper" onClick={this.toggle.bind(this)}>
                    <h4>{gettext("Filters")}</h4>
                    <i className={`far ${status ? 'fa-outdent' : ' fa-indent'}`}></i>
                </div>
                <Filter ref={this.refFilter} onChange={this.updateFilterValue.bind(this)}
                        onEnterKeyDown={this.apply.bind(this)}/>
                <div className="topic-wrapper" style={{display:'none'}}>
                    <h4>{gettext("Category")}</h4>
                    <Dropdown ref={this.refTopic} className={'topics'} data={courseCategories}
                              searchable={true} optionRender={optionRender}
                              onChange={this.updateTopic.bind(this)}/>
                </div>
                <ul>
                    <DropdownPanel status={true} title={gettext('Rating')}>
                        <StarCheckboxGroup ref={this.refRatingRange} data={ratingRange}
                                       onChange={this.updateRatingRange.bind(this)}/>
                    </DropdownPanel>
                    <DropdownPanel status={true} title={gettext('Video Duration')}>
                        <CheckboxGroup ref={this.refDurations} data={durations}
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
                        <i className="far fa-sync-alt"></i>
                        <span>{gettext("Reset")}</span>
                    </button>
                </div>
            </aside>
        )
    }
}

export {CoursesSideBar}
