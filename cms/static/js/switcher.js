'use strict';
import React from 'react';
import ReactDOM from 'react-dom';
import PropTypes from 'prop-types';
//import {QuestionMark} from '../../../lms/static/js/QuestionMark';
import Switch from "react-switch";
import Dropdown from "lt-react-dropdown"
import CheckboxGroup from "lt-react-checkbox-group"

export class Switcher extends React.Component {
    constructor(props) {
        super(props);

        // || !!props.value
        this.state = { checked: (props.value === 'true' || props.value === true)?true:false };
        this.handleChange = this.handleChange.bind(this);
        this.myRef = React.createRef()
    }

    handleChange(checked) {
        this.setState({ checked }, ()=>{
            const {onValueChange} = this.props
            onValueChange && onValueChange(this.state.checked);
        });
    }

    render() {
        return (
            <Switch ref={this.myRef} onChange={this.handleChange} checked={this.state.checked}
                    width={40}
                    checkedIcon={false} uncheckedIcon={false} onColor={"#e7413c"}/>
        );
    }
}

Switcher.propTypes = {
    tooltip: PropTypes.string,
};

export class DatePicker extends React.Component {
    constructor(props) {
        super(props);

        this.state = { checked: props.value == 'true' };
        //this.handleChange = this.handleChange.bind(this);
        this.myRef = React.createRef()
    }

    /*handleChange(checked) {
        this.setState({ checked }, ()=>{
            const {onValueChange} = this.props
            onValueChange && onValueChange(this.state.checked);
        });
    }*/

    /*
    * onChange={this.handleChange} checked={this.state.checked}
                    width={40}
                    checkedIcon={false} uncheckedIcon={false} onColor={"#e7413c"}
    * */
    render() {
        return (
            <input ref={this.myRef} className={'date datepicker'} />
        );
    }
}

window.LearningTribes = window.LearningTribes || {};
window.LearningTribes['ReactDOM']=ReactDOM;
window.LearningTribes['React']=React;

window.LearningTribes.Switcher = function (element, value, onValueChange) {
    ReactDOM.unmountComponentAtNode(element)
    ReactDOM.render(
      React.createElement(Switcher, {value, onValueChange}, null),
      element
    );
}

window.LearningTribes.Dropdown = function (element) {
    const arr = [
        {value: 'a3', text: 'gender'},
        {value: 'a4', text: 'country'},
        {value: 'direction', text: 'Direction'},
        {value: 'a6', text: 'time'},
        {value: 'a7', text: 'confirm'},
        {value: 'a8', text: 'unconfirm'},
        {value: 'a9', text: 'get'},
        {value: 'a10', text: 'difference'},
        {value: 'a11', text: 'none'},
        {value: 'a12', text: 'sentence'},

    ]
    const parameterConf = {
        data:arr,
        value:''
    }
    ReactDOM.render(
      React.createElement(Dropdown, {...parameterConf}, null),
      element
    );
}

//checkedList, onChange, options
window.LearningTribes.CheckboxGroup = function (element, options) {
    ReactDOM.render(
      React.createElement(CheckboxGroup, options, null),
      element
    );
}

window.LearningTribes.DatePicker = function (element, value, onValueChange) {
    ReactDOM.unmountComponentAtNode(element)
    ReactDOM.render(
      React.createElement(DatePicker, {value, onValueChange}, null),
      element
    );
}
