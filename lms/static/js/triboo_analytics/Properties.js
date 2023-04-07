import React from "react";
import {pick} from "lodash";
import CheckboxGroup from "lt-react-checkbox-group"

class Properties extends React.Component {

    constructor(props, context) {
        super(props, context);
        this.myRef = React.createRef()
    }

    clean() {
        this.myRef.current.clean()
    }

    handleChange(selectedItems) {
        const {onChange}=this.props
        onChange && onChange(selectedItems)
    }

    render() {
        return (
            <div className="properties-wrapper">
                <h4>{gettext('Select the user properties to display')}</h4>
                <CheckboxGroup ref={this.myRef} {...pick(this.props, ['data', 'checkedList'])}
                               onChange={this.handleChange.bind(this)}/>
            </div>
        )
    }
}
export {Properties}
