/* eslint-disable react/no-danger, import/prefer-default-export */
import React from 'react';
import { pick, get } from 'lodash'

import Dropdown from 'lt-react-dropdown'
import LabelValue from 'lt-react-label-value'
import {Exporter} from './Exporter'
import {Properties} from './Properties'
import {PeriodFilter} from './PeriodFilter'


const debounce = (f, time) => {
    let debounced
    return function (...args) {
        const actor = () => f.apply(this, args)
        clearTimeout(debounced)
        debounced = setTimeout(actor, time)
    }
}

export class Toolbar extends React.Component {
    constructor(props) {
        super(props);
        this.fireOnChange = debounce(this.doFireChange.bind(this), 100).bind(this)

        const {enabledItems} = props
        const toolbarItems = this.getToolbarItems(enabledItems)
        this.state = {
            selectedFilterItems:[],
            selectedProperties:[],
            selectedCourses: [],
            startDate:'',
            endDate:'',
            activeButton:'',
            exportType:'',
            dataList: [],
            courses: [],

            toolbarItems,
            activeTabName: props.defaultActiveTabName || '' //toolbarItems.length > 0 ? toolbarItems[0].name : ''
        }
    }

    componentDidMount () {
        fetch('/analytics/common/get_properties/json/')
            .then(response => response.json())
            .then(data => {
                this.setState((prev) => {
                    const dataList = data.list.map(item => pick(item, ['text', 'value']))
                    const courses = data.courses.map(item => pick(item, ['text', 'value']))

                    return {
                        dataList,
                        courses,
                    }
                })

                const {onInit} = this.props
                onInit && onInit(data.list)
            })
            .catch(console.error)
    }

    export() {
        const {onGo}=this.props
        onGo && onGo(this.state.exportType)

        if (window.listenDownloads) {
            const cancel = window.listenDownloads((data, foundNewFile) => foundNewFile && cancel())
            window.addEventListener('beforeunload', cancel)
        }
    }

    fireExportTypeChange() {
        setTimeout(() => {
            this.doFireChange(true)
        }, 100)
    }

    doFireChange(isExcluded=false) {
        const {onChange}=this.props
        const json = pick(this.state, 'selectedFilterItems','selectedProperties', 'selectedCourses', 'startDate','endDate', 'activeButton', 'exportType')
        onChange && onChange(json, isExcluded);
    }

    getToolbarItems(enabledItems=[]) {
        const {
            selectedFilterItems = [],
            selectedProperties=[],
            exportType='',
            startDate='',
            endDate='',
            activeButton=''
        } = get(this, 'props.defaultToolbarData', {})

        return [
            {
                name: 'filters',
                text: gettext('Filters'),
                icon: 'fa-search',
                Component: ({dataList}) => {
                    return (
                        <LabelValue
                            data={[{text: gettext('Name'), value: 'user_name'}].concat(dataList)}
                            selectedList={selectedFilterItems}
                            useFontAwesome
                            placeholder={gettext('Press enter to add')}
                            onChange={(selectedFilterItems) => this.setState({selectedFilterItems}, this.fireOnChange)}
                        />
                    )
                },
            },
            {
                name: 'ILTGlobalFilters',
                className: ' ',
                text: gettext('Filters'),
                icon: 'fa-search',
                Component: ({active, courses}) => {
                    return (
                        <ILTGlobalFilters
                            active={active}
                            courses={courses}
                            useFontAwesome
                            placeholder={gettext('Press enter to add')}
                            onChange={state => this.setState(state, this.fireOnChange)}
                        />
                    )
                },
            },
            {
                name: 'ILTLearnerFilters',
                className: ' ',
                text: gettext('Filters'),
                icon: 'fa-search',
                Component: ({active, dataList, courses}) => {
                    return (
                        <ILTLearnerFilters
                            active={active}
                            data={[{text: gettext('Name'), value: 'user_name'}].concat(dataList)}
                            courses={courses}
                            selectedList={selectedFilterItems}
                            useFontAwesome
                            placeholder={gettext('Press enter to add')}
                            onChange={state => this.setState(state, this.fireOnChange)}
                        />
                    )
                },
            },
            {
                name: 'properties',
                text: gettext('Properties'),
                icon: 'fa-sliders-h',
                Component: ({dataList}) => {
                    return (
                        <Properties
                            data={dataList}
                            checkedList={selectedProperties.map(p => p.value)}
                            onChange={selectedProperties => this.setState({selectedProperties}, this.fireOnChange)}
                        />
                    )
                }
            },
            {
                name: 'period',
                text: gettext('Period'),
                icon: 'fa-calendar-alt',
                Component: () => {
                    return (
                        <PeriodFilter
                            label={gettext('Select a time range')}
                            buttonText={gettext('Last * days')}
                            startDate={startDate}
                            endDate={endDate}
                            activeButton={activeButton}
                            useFontAwesome
                            periodTooltip={this.props.periodTooltip}
                            onChange={(startDate, endDate, activeButton) => this.setState({startDate, endDate, activeButton}, this.fireOnChange)}
                        />
                    )
                }
            },
            {
                name: 'export',
                text: gettext('Export'),
                icon: 'fa-file-download',
                Component: () => {
                    return (
                        <Exporter
                            onGo={this.export.bind(this)}
                            defaultValue={exportType}
                            onChange={exportType => this.setState({exportType}, this.fireExportTypeChange.bind(this))}
                        />
                    )
                }
            },
        ].filter(p => enabledItems.includes(p.name) || enabledItems.length <= 0)
    }

    setActiveTab (json) {
        const {onTabSwitch} = this.props
        let activeTabName = ''
        this.setState((prev) => {
            if (prev.activeTabName !== json.name) {
                activeTabName = json.name
            }
            return {activeTabName}
        }, () => {
            onTabSwitch && onTabSwitch(activeTabName)
        })
    }

    render() {
        const {activeTabName, dataList, courses} = this.state

        return (
            <div className="toolbar">
                <ul className="toolbar-tabs">
                    {this.props.children}
                    {this.state.toolbarItems.map(toolbarItem => (
                        <li key={toolbarItem.name}
                            onClick={this.setActiveTab.bind(this, toolbarItem)}
                            className={toolbarItem.name + (activeTabName == toolbarItem.name ? ' active' : '')}
                        >
                            <i className={'far ' + toolbarItem.icon}></i><span>{toolbarItem.text}</span>
                        </li>
                    ))}
                </ul>
                <div className="toolbar-contents">
                    {this.state.toolbarItems.map(toolbarItem => (
                        <div key={toolbarItem.name}
                            className={
                                (toolbarItem.className || 'toolbar-content ') +
                                toolbarItem.name +
                                (activeTabName === toolbarItem.name ? ' active' : '')
                            }
                        >
                            {!!toolbarItem.Component && (
                                <toolbarItem.Component
                                    active={activeTabName === toolbarItem.name}
                                    dataList={dataList}
                                    courses={courses}
                                />
                            )}
                        </div>
                    ))}
                </div>
            </div>
        )
    }
}

function ILTGlobalFilters (props) {
    return (
        <CoursesFilters {...props} />
    )
}

function ILTLearnerFilters (props) {
    const {active, onChange} = props
    const handleLabelValueChange= selectedFilterItems => onChange && onChange({selectedFilterItems})

    return (
        <>
            <CoursesFilters {...props} />

            <div className={`toolbar-content filters ${active ? ' active' : ''}`}>
                <LabelValue {...props} onChange={handleLabelValueChange} />
            </div>
        </>
    )
}

function CoursesFilters (props) {
    const {active, onChange} = props

    const [selectedCourses, setSelectedCourses] = React.useState(props.selectedCourses || [])
    const $dropdown = React.useRef(null)

    const handleCourseSelect = React.useCallback((selectedCourses) => {
        setSelectedCourses(selectedCourses)
        onChange && onChange({selectedCourses})
    }, [onChange])

    const handleCourseLabelClick = React.useCallback((course) => {
        if (!$dropdown.current) return
        $dropdown.current.selectMultiple({
            currentTarget: {
                checked: false,
            },
        }, course)
    }, [$dropdown])

    const handleClear = React.useCallback(() => {
        if (!$dropdown.current) return
        $dropdown.current.clean()
    }, [selectedCourses, $dropdown, handleCourseLabelClick])

    return (
        <div className={`toolbar-content filters ${active ? ' active' : ''}`}>
            <div className="field-courses">
                <div className="select-courses">
                    <label>{gettext('Select course(s)')}</label>
                    <Dropdown
                        ref={$dropdown}
                        data={props.courses || []}
                        multiple
                        searchable
                        onChange={handleCourseSelect}
                        valueRender={selected => gettext('{nb} course(s) selected').replace('{nb}', selectedCourses.length)}
                    />
                    <span className="data-clear" onClick={handleClear}>
                        <i className="far fa-trash-alt sync-icon"/>
                    </span>
                </div>
                <div className="selected-courses">
                    {selectedCourses.map(selectedCourse => (
                        <div key={selectedCourse.value} className="selected-course">
                            <span>{selectedCourse.text}</span>
                            <i role="button" onClick={() => handleCourseLabelClick(selectedCourse)} className="far fa-times icon" />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
