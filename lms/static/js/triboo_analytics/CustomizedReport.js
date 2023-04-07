/* eslint-disable react/no-danger, import/prefer-default-export */
import React from 'react'
import PropTypes from 'prop-types'
import 'select2'
import 'select2/dist/css/select2.css'
import {ReactRenderer} from '../../../../common/static/js/src/ReactRenderer'
import {pick} from 'lodash'
import ReportTypeAndCourseReport from './ReportTypeAndCourseReport'

export class CustomizedReport {
  constructor (props) {
    //comes from beginning of customized_report.js
    this.log = console.log.bind(console)
    this.savedProps = props

    $(() => {
      this.initDom()
    })

    window.customizedReport = this
  }

  initDom () {
    new ReactRenderer({
      component: ReportTypeAndCourseReport,
      selector: '.report_type_and_course_selected',
      componentName: 'CustomizedReport',
      props: {
        ...this.savedProps,
        onChange: (
          reportTypeValue,
          selectedCourses,
          query_tuples,
          startDate,
          endDate,
          selectedEnrollments,
          limit
        ) => {
          this.reportTypeValue = reportTypeValue
          this.selectedCourses = selectedCourses
          this.query_tuples = query_tuples
          this.startDate = startDate
          this.endDate = endDate
          this.selectedEnrollments = selectedEnrollments
          this.limit = limit
          this.goButtonStatusUpdate()
          this.sectionStatusUpdate()
        }
      }
    })
    this.$submitButton = $('input[type=submit]')
    this.$courseReport = $('#course_selected')
    this.oldCourseValues = []
    this.oldCourseTexts = []
    this.$courseReportSelect2 = this.$courseReport.select2()
    this.eventInit()
  }

  onSubmit (e) {
    e.preventDefault()
    setTimeout(async () => {
      const json = await this.submit()
      LearningTribes.dialog.show(json.message)
    }, 200)
  }

  onSelectExportFormat (e) {
    requestAnimationFrame(() => {
      const checked = $('#table-export-selection input[name=format]:checked')[0]
      if (checked) {
        const formatBar = document.getElementById('format_bar')
        const text = checked.parentNode.querySelector('label').textContent
        if (formatBar.querySelector('button')) {
          formatBar.querySelector('button span').innerHTML = text
        } else {
          const button = document.createElement('button')
          button.className = 'property-option option-label'
          formatBar.appendChild(button)
          const span = document.createElement('span')
          span.innerText = text
          button.appendChild(span)
        }
        if (window.reportTypeAndCourseReport && window.reportTypeAndCourseReport.changeLimitByFormat) {
          window.reportTypeAndCourseReport.changeLimitByFormat()
        }
      }

      this.goButtonStatusUpdate()
    })
  }

  onSelectProperty (e) {
    const prop_name = $(e.currentTarget)[0].innerText
    const cur_input = $(e.currentTarget.querySelector('input'))
    const prop_id = 'tag_' + cur_input[0].id
    const target_tag = $("#property_bar").children('#' + prop_id)
    const add_class = "property-option"

    function addTagToBar (tag_bar, tag_class, tag_name, tag_id) {
      $("<button/>", {
        "id": tag_id,
        "class": tag_class + " option-label"
      }).appendTo(tag_bar)
      $("<span/>", {
        "class": "query",
        text: tag_name
      }).appendTo("#" + tag_id)
      $("<span/>", {
        "class": "fa fa-times"
      }).appendTo("#" + tag_id)
    }

    if (!target_tag.length && cur_input[0].checked) {
      addTagToBar('#property_bar', add_class, prop_name, prop_id)
    } else if (target_tag.length && !cur_input[0].checked) {
      $("#property_bar button").remove('#' + prop_id)
    }
    this.goButtonStatusUpdate()
  }

  onReset () {
    const clearNode = node => {
      if (!node) return
      while (node.firstChild) {
        node.firstChild.remove()
      }
    }
    const clearNodeById = elementId => clearNode(document.getElementById(elementId))
    const resetSelections = (elementId, inputName) => {
      const $el = document.getElementById(elementId)
      if (!$el) return

      $el.querySelectorAll(`input[name="${inputName}"]`).forEach(e => {
        e.checked = false
      })
    }

    if (window.reportTypeAndCourseReport && window.reportTypeAndCourseReport.reset) {
      window.reportTypeAndCourseReport.reset()
      const hideSection = id => {
        const $el = document.getElementById(id)
        if ($el) {
          $el.classList.add('is-hidden')
        }
      }
      hideSection('report_bar')
      hideSection('course_bar')
      hideSection('filter-bar2')
    }
    clearNodeById('property_bar')
    resetSelections('user-properties', 'selected_properties')

    clearNodeById('format_bar')
    resetSelections('table-export-selection', 'format')

    this.eventInit()

    this.reportTypeAndCourseInit()
  }

  onUnselectProperty (e) {
    const this_button = $(e.currentTarget)
    const input_id = this_button[0].id
    const prop_id = input_id.substr(4)
    e.preventDefault()
    $(this_button).parent().children('button').remove('#' + input_id)
    $('#' + prop_id).attr("checked", false)
  }

  eventInit () {
    const listen = (parentSelector, childrenSelector, handler, events = 'click') => {
      $(parentSelector).off(events, childrenSelector, handler)
      $(parentSelector).on(events, childrenSelector, handler)
    }

    listen('input[type=submit]', '', this.onSubmit.bind(this))

    listen('#table-export-selection', 'label', this.onSelectExportFormat.bind(this))

    listen('#id_selected_properties', 'li label', this.onSelectProperty.bind(this))

    listen('#property_bar', 'button', this.onUnselectProperty.bind(this))

    listen('#report_bar', 'button', this.preventDefault.bind(this))
    listen('.accordion-trigger', '', this.preventDefault.bind(this))
    listen('#format_bar', 'button', this.preventDefault.bind(this))

    listen('#reset-button', '', this.onReset.bind(this))

    document.querySelectorAll('.accordion-trigger').forEach(section => {
      section.removeEventListener('click', this.onToggleSection.bind(this))
      section.addEventListener('click', this.onToggleSection.bind(this))
    })

    this.reportTypeAndCourseInit()
  }

  preventDefault (e) {
    e.preventDefault()
  }

  reportTypeAndCourseInit () {
    this.$courseReport.val('').trigger('change')
    $('#report_type').val('course_summary').trigger('change')
    $('#report_bar').addClass('is-hidden')
  }

  goButtonStatusUpdate () {
    setTimeout(() => {
      if (this.checkFieldsSuccess()) {
        this.$submitButton.removeClass('disabled')
      } else if (!this.$submitButton.hasClass('disabled')) {
        this.$submitButton.addClass('disabled')
      }
    }, 200)
  }

  sectionStatusUpdate () {
    if (this.reportTypeValue == 'ilt_global') {
      $('.filter-form').hide()
      $('.table-user-properties-form-customized').hide()
    } else {
      $('.filter-form').show()
      $('.table-user-properties-form-customized').show()
    }
  }

  checkFieldsSuccess () {
    const reportTypeVal = this.reportTypeValue
    const courseReportVal = this.selectedCourses
    const selectedCoursesNum = courseReportVal ? (courseReportVal.length || courseReportVal.value) : 0
    const isFormatChecked = $('#table-export-selection input[name=format]:checked').length
    const isBelowlimit = this.selectedEnrollments <= this.limit
    if (reportTypeVal == 'learner' || reportTypeVal == 'ilt_global' || reportTypeVal == 'ilt_learner') {
      return reportTypeVal && isFormatChecked && isBelowlimit
    }
    return reportTypeVal && selectedCoursesNum && isFormatChecked && isBelowlimit
  }

  async submit () {
    const data = {
      report_type: this.reportTypeValue,
      courses_selected: this.selectedCourses.value || this.selectedCourses.map(p => p.value).join(','),
      query_tuples: (this.query_tuples || []).map(p => {
        const {value, key} = pick(p, ['key', 'value'])
        return [value, key]
      }),
      from_day: this.startDate,
      to_day: this.endDate,
      selected_properties: []
    }
    $('#form-customized-report').serializeArray().forEach(function ({name, value}) {
      if (name == 'selected_properties') {
        data['selected_properties'].push(value)
      } else {
        data[name] = value
      }
    })
    console.log('data', data)
    if (window.listenDownloads) {
        const cancel = window.listenDownloads((data, foundNewFile) => foundNewFile && cancel())
        window.addEventListener('beforeunload', cancel)
    }
    return $.post({
      url: 'export/',
      data: JSON.stringify(data),
    })
  }

  expandSection (sectionToggleButton) {
    const $toggleButtonChevron = $(sectionToggleButton).children('.fa-chevron-down')
    const $contentPanel = $(document.getElementById(sectionToggleButton.getAttribute('aria-controls')))

    //$contentPanel.slideDown();
    $contentPanel.removeClass('is-hidden')
    $toggleButtonChevron.addClass('fa-rotate-180')
    sectionToggleButton.setAttribute('aria-expanded', 'true')
  }

  collapseSection (sectionToggleButton) {
    const $toggleButtonChevron = $(sectionToggleButton).children('.fa-chevron-down')
    const $contentPanel = $(document.getElementById(sectionToggleButton.getAttribute('aria-controls')))

    //$contentPanel.slideUp();
    $contentPanel.addClass('is-hidden')
    $toggleButtonChevron.removeClass('fa-rotate-180')
    sectionToggleButton.setAttribute('aria-expanded', 'false')
  }

  onToggleSection (event) {
    const sectionToggleButton = event.currentTarget
    const sectionToggleButtons = document.querySelectorAll('.section-button')
    if (sectionToggleButton.classList.contains('accordion-trigger')) {
      event.preventDefault()
      event.stopImmediatePropagation()
      const isExpanded = sectionToggleButton.getAttribute('aria-expanded') === 'true'
      if (!isExpanded) {
        for (const button of sectionToggleButtons) {
          this.collapseSection(button)
          $(button).siblings('.label-bar').removeClass('is-hidden')
        }
        this.expandSection(sectionToggleButton)
        const $labelBar = $(sectionToggleButton).siblings('.label-bar')
        $labelBar.addClass('is-hidden')
      } else if (isExpanded) {
        this.collapseSection(sectionToggleButton)
        $(sectionToggleButton).siblings('.label-bar').removeClass('is-hidden')
      }
    }
  }
}


CustomizedReport.propTypes = {
  translation: PropTypes.shape({
    report_type: PropTypes.string,
    course: PropTypes.string
  }),
  report_types: PropTypes.arrayOf(PropTypes.shape({
    type: PropTypes.string,
    title: PropTypes.string
  })),
  courses: PropTypes.arrayOf(PropTypes.shape({
    cid: PropTypes.string,
    course_title: PropTypes.string
  }))
}
