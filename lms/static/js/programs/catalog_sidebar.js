import React from "react";
import CheckboxGroup from 'lt-react-checkbox-group'
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
        const {status} = this.state, pr=this.props;
        return <li key={pr.data.value || ''} className="dropdown-panel">
            <h4 onClick={this.toggleDisplayStatus.bind(this)}><span>{this.props.title}</span><i
                className={`fa fa-sort-${status ? 'up' : 'down'}`}></i></h4>
            <div className={`component-wrapper ${!status ? 'hide-status' : ''}`}>
                {this.props.children}
            </div>
        </li>
    }
}

// properties
//  data: []   an json list, example: ./mock_data/course:MockedFacetResult.results
class ProgramsSideBar extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            filterValue: '',
            selectedLanguages: [],
            selectedObject:{}
        };
        this.refFilter = React.createRef();
        this.refLanguages = React.createRef();

        this.fireOnChange.bind(this);
    }

    updateFilterValue(filterValue) {
        this.setState({filterValue}, this.fireOnChange)
    }

    updateLanguages(selectedLanguages) {
        this.setState({
            selectedLanguages
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
        return {..._.pick(this.state, ['filterValue', 'selectedLanguages']),
            ...this.state.selectedObject}
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
        this.state.selectedObject = {};
        const {resetSearchParams} = this.props;
        resetSearchParams();
        onReset && onReset(this.getData());
    }

    updateSelectedObject(key, items){
        this.setState(prev=>{
            return {selectedObject:{...prev.selectedObject, [key]:items}}
        })
        this.fireOnChange()
    }

    render() {
        const {status, languages} = this.props, pr=this.props;
        return (
            <aside className={`sidebar ${status ? '' : ' hide-status'}`}>
                <div className="filters-wrapper" onClick={this.toggle.bind(this)}>
                    <h4>{gettext("Filters")}</h4>
                    <i className={`far ${status ? 'fa-outdent' : ' fa-indent'}`}></i>
                </div>
                <Filter ref={this.refFilter} onChange={this.updateFilterValue.bind(this)}
                        onEnterKeyDown={this.apply.bind(this)}/>
                <ul>{pr.data.map(p=>{
                    return <DropdownPanel data={p} key={'id-'+p.value} status={true} title={p.text}>
                        <CheckboxGroup data={p.items}
                                       onChange={item=>this.updateSelectedObject(p.value, item)}/>
                    </DropdownPanel>})}
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

export {ProgramsSideBar}
