import React from "react"
import LabelValue from "lt-react-label-value"
import DateRange from "lt-react-date-range"
import Dropdown from 'lt-react-dropdown'
import {get} from 'lodash'
import {useState, useCallback, useEffect} from "react"


let version = 0

class ReportTypeAndCourseReport extends React.Component {
  constructor (props) {
    super(props)

    this.initState = {
      version: 0,
      reportType: get(props, ['report_types', '0']) || {},
      reportTypeValue: get(props, ['report_types', '0', 'value']) || '',
      selectedCourses: [],
      selectedCourseValues: [],
      selectedKeyValues: [],
      isMultiple: true,
      selectedEnrollments: 0,
      limit: 300000,
      hideCourseReportSelect: false,
      hideCourseReportInfo: true,
    }

    this.state = {...this.initState}

    window.reportTypeAndCourseReport = this
  }

  reset () {
    this.setState({
      ...this.initState,
      version: ++version,
    })
    this.recreateCourseSelect(this.state.reportType)
  }

  componentDidMount () {
    this.recreateCourseSelect(this.state.reportType)
  }

  changeLimitByFormat () {
    const $el = $('#table-export-selection input[name=format]:checked')[0]
    if (!$el) return
    const limit = $el.value == 'xls' ? 65000 : 300000
    this.setState({limit}, this.fireOnChange)
    this.checkLimit()
  }

  recreateCourseSelect (reportType) {
    const courseReportType = reportType.courseReportType
    this.setState({reportType, reportTypeValue: reportType.value}, this.fireOnChange)
    if (courseReportType == 'multiple' || courseReportType == 'single') {
      const isMultiple = courseReportType == 'single' ? false : true
      this.setState({
        isMultiple,
        selectedCourses: [],
        hideCourseReportSelect: false,
        hideCourseReportInfo: courseReportType === 'single',
      }, this.fireOnChange)
    } else {
      this.setState({
        hideCourseReportSelect: true
      })
    }
  }

  onSectionChange (state) {
    this.setState(state, this.fireOnChange)
    if (state.selectedEnrollments) this.checkLimit()
  }

  fireOnChange () {
    const {onChange} = this.props
    const {reportTypeValue, selectedCourses, selectedKeyValues, startDate, endDate, selectedEnrollments, limit} = this.state
    onChange && onChange(reportTypeValue, selectedCourses, selectedKeyValues, startDate, endDate, selectedEnrollments, limit)
  }

  checkLimit () {
    const {isMultiple, limit, selectedEnrollments} = this.state
    if (isMultiple && selectedEnrollments > limit) {
      alert(gettext('With the selected courses, the report exceeds the maximum number of lines. Please unselect some courses.'))
    }
  }

  render () {
    const {courses, report_types} = this.props
    const {isMultiple, hideCourseReportInfo, hideCourseReportSelect, reportType, reportTypeValue} = this.state

    const courseChoices = courses.filter(course => reportType.value.startsWith('ilt_')
      ? course.type === reportType.value
      : (!course.type || !course.type.startsWith('ilt_'))
    )

    return (
      <React.Fragment key={this.state.version}>
        <ReportTypeSection
          report_types={report_types}
          reportType={reportType}
          reportTypeValue={reportTypeValue}
          onChange={this.recreateCourseSelect.bind(this)}
        />
        <CourseSection
          courses={courseChoices}
          isMultiple={isMultiple}
          hideCourseReportInfo={hideCourseReportInfo}
          hideCourseReportSelect={hideCourseReportSelect}
          onChange={this.onSectionChange.bind(this)}
        />
        <FilterSection onChange={this.onSectionChange.bind(this)} />
      </React.Fragment>
    )
  }
}

function ReportTypeSection ({report_types, reportType, reportTypeValue, onChange}) {

  return (
    <div className="custom-section" id="report_type_section">
      <button className="section-button accordion-trigger"
        type="button"
        aria-expanded="true"
        aria-controls="report_section_contents"
        id="report_section">
        <p className="section-title">{gettext("Select a report")}</p>
        <span className="fa fa-chevron-down fa-rotate-180" aria-hidden="true"></span>
      </button>
      <div id="report_section_contents" className="section-content">
        <div className="report-type">
          <Dropdown sign='caret' data={report_types} value={get(report_types, ['0', 'value'])} onChange={onChange} />
          <input type="hidden" id='report_type' value={reportTypeValue} />
        </div>
      </div>
      <div id="report_bar" className="reports label-bar is-collapsed is-hidden">
        {reportTypeValue && <button className="filter-option option-label" type="button">
          <span className="query">{gettext(reportType.text)}</span>
        </button>}
      </div>
    </div>
  )
}

function CourseSection ({courses, isMultiple, hideCourseReportInfo, hideCourseReportSelect, onChange}) {
  const [selectedCourses, setSelectedCourses] = useState([])
  const [selectedEnrollments, setSelectedEnrollments] = useState(0)

  const optionRender = (text, item) => `${text} (${item.course_enrollments || '0'})`

  const handleCourseSelect = useCallback((selectedCourses) => {
    const selectedEnrollments = isMultiple
      ? selectedCourses.reduce((r, c) => r + c.course_enrollments, 0)
      : selectedCourses.course_enrollments || '0'
    setSelectedCourses(selectedCourses)
    setSelectedEnrollments(selectedEnrollments)
    onChange && onChange({
      selectedCourses,
      selectedEnrollments,
    })
  }, [isMultiple])

  return (
    <div className={`custom-section${hideCourseReportSelect ? ' hidden' : ''}`} id="custom_course_section">
      <button className="section-button accordion-trigger"
        type="button"
        aria-expanded="false"
        aria-controls="course_section_contents"
        id="course_section">
        <p className="section-title">{gettext("Select course(s)")}</p>
        <span className="fa fa-chevron-down" aria-hidden="true"></span>
      </button>

      <div id="course_section_contents" className="section-content is-hidden">
        <div className={'course-report'}>
          <p className={"section-label " + (hideCourseReportInfo ? 'hide' : '')}>
            <p>{gettext('With the selected courses, the report will count * lines.').replace('*', selectedEnrollments)}</p>
            <p>{gettext('The limit is 300,000 for CSV and JSON, 65,000 for XLS.')}</p>
          </p>
          <Dropdown key="key-select-course" data={courses} multiple={isMultiple} searchable={true} optionRender={optionRender} onChange={handleCourseSelect} />
        </div>
      </div>
      <div id="course_bar" className="courses label-bar is-collapsed">
        {isMultiple && selectedCourses.map(({key, value, text}) => (<button className="filter-option option-label" type="button">
          <span className="query">{`${text}`}</span>
        </button>))}
        {!isMultiple && selectedCourses.text && <button className="filter-option option-label" type="button">
          <span className="query">{`${selectedCourses.text}`}</span>
        </button>}
      </div>
    </div>
  )
}


function FilterSection ({onChange}) {
  const [selectedKeyValues, setSelectedKeyValues] = useState([])
  const [{startDate, endDate}, setPeriod] = useState({startDate, endDate})

  const filterOnChange = (selectedKeyValues) => {
    setSelectedKeyValues(selectedKeyValues)
    onChange && onChange({
      selectedKeyValues,
    })
  }

  const periodOnChange = (startDate, endDate) => {
    setPeriod({startDate, endDate})
    onChange && onChange({startDate, endDate})
  }

  const stopEvent = e => {
    e.stopPropagation()
    e.preventDefault()
    return false
  }

  const [filterData, setFilterData] = useState([{value: '', text: 'loading'}])
  useEffect(() => {
    const nameList = [{text: gettext('Name'), value: 'user_name'}]
    fetch('/analytics/common/get_properties/json/')
      .then(response => response.json())
      .then(data => setFilterData(nameList.concat(data.list)))
  }, [])

  return (
    <div className="custom-section" id="filter-section">
      <button className="section-button accordion-trigger"
        type="button"
        aria-expanded="false"
        aria-controls="filter_section_contents"
        id="filter_section">
        <p className="section-title">{gettext("Filter the data")}</p>
        <span className="fa fa-chevron-down" aria-hidden="true"></span>
      </button>
      <div id="filter_section_contents" className="section-content is-hidden">
        <section className="filter-form">
          <div id="filter-form">
            <div className="table-filter-form">
              <LabelValue
                data={filterData}
                onChange={filterOnChange}
                placeholder={gettext('Press enter to add')}
                useFontAwesome={true}
                stopEventSpread={true}
              />
            </div>
          </div>
        </section>
        <section className="period-form">
          <p className="section-label">{gettext("Select a time range") + ':'}</p>
          <div id="period-table">
            <DateRange
              onChange={periodOnChange}
              buttonText={gettext('Last * days')}
              useFontAwesome={true}
              startDateName='from_day'
              endDateName='to_day'
            />
          </div>
        </section>
      </div>
      <div id="filter-bar2" className="filters label-bar is-collapsed">
        {selectedKeyValues.map(({key, value, text}) => (
          <button key={key} className="filter-option option-label" onClick={stopEvent} type="button">
            <span className="query">{`${text}:${value}`}</span>
          </button>
        ))}
        {startDate && (
          <button className="filter-option option-label start-date" onClick={stopEvent} type="button">
            <span className="query">{startDate}</span>
          </button>
        )}
        {(startDate && endDate) ? <span>-</span> : ''}
        {endDate && (
          <button className="filter-option option-label end-date" onClick={stopEvent} type="button">
            <span className="query">{endDate}</span>
          </button>
        )}
      </div>
    </div>
  )
}

export default ReportTypeAndCourseReport
