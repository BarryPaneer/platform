import React from "react";

class Exporter extends React.Component {
    constructor(props, context) {
        super(props, context);
        this.state={
            buttonStatus:'disabled',
            value:props.defaultValue || ''
        }
    }

    componentDidMount() {
        const {defaultValue}=this.props
        if (defaultValue != '') {
            this.fireChange(defaultValue)
        }
    }

    handleChange(item) {
        const {value}=item
        this.setState({
            value,
            buttonStatus:''
        },()=>{
            this.fireChange(value)
        })
    }

    fireChange(value) {
        const {onChange}=this.props
        onChange && onChange(value)
        this.setState({buttonStatus:''})
    }

    render() {
        const EXPORT_TYPES = [
            {value: 'csv', text: gettext('CSV report')},
            {value: 'xls', text: gettext('XLS report')},
            {value: 'json', text: gettext('JSON report')},
        ]
        const {onGo}=this.props
        return (
            <div className="exporter-wrapper">
                <ul>
                {(this.props.data || EXPORT_TYPES).map((item, index)=>{
                    const key = 'radio-'+index
                    return (
                        <li key={key}>
                            <input type="radio" name="radio0" id={key} checked={this.state.value == item.value?true:false} onChange={this.handleChange.bind(this, item)}/>
                            <label htmlFor={key}>{item.text}</label>
                        </li>
                    )
                })}
                </ul>
                <input type="button" value={gettext("Go")} className={this.state.buttonStatus} onClick={onGo}/>
            </div>
        )
    }
}

export {Exporter}
