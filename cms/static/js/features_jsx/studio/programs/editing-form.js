
// please don't reformat this file

import React, {Component} from 'react'
import Dropdown from "lt-react-dropdown"
import {ReactSortable} from "react-sortablejs"
import {pick} from 'lodash'
import {Loading, ProgramBase} from "../shared"

const DurationUnit = {
    minutes: 'minute',
    hours: 'hour',
    days: 'day',
}

const DurationUnitScalarMap = {
    [DurationUnit.minutes]: 1,
    [DurationUnit.hours]: 60,
    [DurationUnit.days]: 60 * 24,
}

const ActionType = {
    attach: 1,
    detach: 0
}

class EditingForm extends ProgramBase {
    constructor (props) {
        super(props)

        this.state = {
            title: '',

            start: '', end: '', enrollment_start: '', enrollment_end: '',

            fileUrl: '',
            temporaryImageUrl: '',
            description: '',
            duration: 0,
            durationUnit: '',
            visibility: 0,

            language: '', languages: [],

            coursesToDetach: [], coursesToAttach: [], allCourses: [], includedCourses: [],
            coursesToSort: [], originalIncludedCourses: [],

            dataLoaded: false,

            uuid: props.uuid,
            data: {}, temporaryData: {},

            fetching: false,
        }
        this.globalVarInit()
    }
    async componentDidMount () {
        const data = await this.fetchData();
        var [fetchedCourses, includedCourses, languageObj] = await Promise.all([
            this.fetchBatchesCourses('', data.partner),
            this.fetchIncludedCourses(),
            this.fetchLanguages()
        ])

        let requested_courses_table = this.state.allCourses;
        requested_courses_table.push(...fetchedCourses);   // Added first batches courses record into cache

        const getDurationUnit = () => {
            const duration = data.duration
            if (duration <= 0) return DurationUnit.minutes
            if (duration % DurationUnitScalarMap[DurationUnit.days] === 0) return DurationUnit.days
            if (duration % DurationUnitScalarMap[DurationUnit.hours] === 0) return DurationUnit.hours
            return DurationUnit.minutes
        }
        const fileUrl = data.card_image_url || this.default_card_image_url
        const durationUnit = getDurationUnit()

        const languages = Object.keys(languageObj).sort().map(key => ({text: languageObj[key], value: key}))

        this.setState({
            dataLoaded: true,
            ...pick(data, this.getFieldKeys()),
            durationUnit,

            ...this.getDates(data),
            data,
            temporaryData: {
                ...pick(data, this.getFieldKeys()),
                durationUnit
            },
            allCourses: requested_courses_table,
            includedCourses, originalIncludedCourses: includedCourses,
            fileUrl,
            languages
        })
        this.descriptionFieldInit()

        setTimeout($.proxy(function(){
            var $marks = $('.question-mark-wrapper');
            _.each($marks, function(mark){
                new LearningTribes.QuestionMark(mark)
            });
        }, this), 500)
    }

    globalVarInit () {
        this.default_card_image_url = '//program_asset_v1:63c25729592a4148a4d634dc1eb91c7c:test_demo.png'
        this.timeOfLastRequest = Date.now()
        this.timeOfLastRequest2 = Date.now()
        this.isRequesting = false;              // true if it's still requesting courses list
        this.keyword_filter = '';               // filter keyword of courses
        this.next_request_pageno = 1;           // the first pageno of courses list for requesting
    }

    getUrl () {
        const {uuid} = this.state
        return `/api/proxy/discovery/api/v1/programs/${uuid}/`
    }
    getFieldKeys () {
        return [
            'title',
            'description',
            'duration',
            'durationUnit',
            'language',
            'visibility'
        ]
    }
    getDates (data) {
        return _.pick(data, ['start', 'end', 'enrollment_start', 'enrollment_end'])
    }
    setDates (data) {
        this.setState(this.getDates(data))
    }
    descriptionFieldInit () {
        this.tinymce = tinymce.init({
            selector: '.tinymce-editor',
            base_url: '/static/studio/js/vendor/tinymce/js/tinymce',
            suffix: '.min',
            theme: 'silver',
            skin: 'oxide',
            statusbar: false,
            plugins: 'link, image, code, lists',
            menubar: false,
            //language: langCode,
            toolbar: 'formatselect | bold italic bullist numlist  forecolor | alignleft aligncenter alignright | numlist bullist',
            setup: (editor) => {
                editor.on('change', (e) => {
                    this.setState((state, props) => {
                        const description = editor.getContent()
                        /*if (state.description != description) {
                            this.partialUpdate({description})
                        }*/
                        return {description}
                    })
                })
                editor.on('blur', this.confirmChange.bind(this))
            }
        })
    }

    async fetchLanguages () {
        return (await fetch(`/api/all_languages`)).json()
    }
    async fetchData () {
        const {uuid} = this.state
        return await (await fetch(`/api/proxy/discovery/api/v1/programs/${uuid}/`)).json()
    }
    async fetchIncludedCourses (title) {
        const {uuid} = this.props
        const mockJson = []
        if (this.props.isDebug) {
            return new Promise(resolve => {
                resolve(mockJson)
            })
        } else {
            const getCourseID = course => {
                const courseRun = course.course_runs.length ? course.course_runs[0] : {}
                return courseRun ? courseRun.key : ''
            }
            const getCourseVisibility = course => {
                const courseRun = course.course_runs.length ? course.course_runs[0] : {}
                return courseRun.catalog_visibility;
            }
            return (await (await fetch(`/api/proxy/discovery/api/v1/programs/${uuid}/courses/?title=${title || ''}`)).json())
                .map(p => ({title: p.title, course_id: getCourseID(p), catalog_visibility: getCourseVisibility(p)}))
        }
    }
    async fetchBatchesCourses (title, partner='') {
        if (this.next_request_pageno === null) {
            return;
        }

        this.isRequesting = true;

        ///< each time, we load one page only.
        var query_url = `/api/courses/v1/courses/?display_name=${title}&excluded_program_uuid=${this.props.uuid}&org=${partner !== '' ? partner : this.state.data.partner}`;
        return await fetch(`${query_url}&page=${this.next_request_pageno}`).then((response)=>{
            if (response.ok) {
                return response.json();
            }

            throw new Error(response.statusText);
        }).then((response_json)=>{
            var courses = response_json.results ? response_json.results.map(p => ({title: p.name, course_id: p.course_id, catalog_visibility: p.catalog_visibility})) : [];

            this.next_request_pageno++;                                     // increase next pageno

            if (!response_json.pagination.next && this.next_request_pageno != null && this.next_request_pageno > 1) {
                this.next_request_pageno = null;
            }

            this.isRequesting = false;

            return courses;
        }).catch((error)=>{
            console.log(error.message);
            this.isRequesting = false;

            return [];
        })

    }
    async publish (e) {
        if (e.currentTarget.classList.contains('disabled')) return
        LearningTribes.Notification.Info({
            title: 'Are you sure to publish this program?',
            onConfirm: async () => {
                if (this.checkIncludedCourses()) return

                const body = JSON.stringify({status: 'active'})
                const response = await fetch(this.getUrl(), {
                    method: 'PATCH', headers: {'Content-Type': 'application/json'}, body
                })
                if (response.ok) {
                    LearningTribes.Notification.Info({
                        title: gettext('Successfully Published')
                    })

                    const data = await this.fetchData()
                    this.setState({data})
                } else {
                    LearningTribes.Notification.Warning({
                        title: 'error',
                        message: 'Something went wrong.'
                    })
                }
            },
            onCancel: () => {}
        })
    }
    async delete () {
        LearningTribes.Notification.Warning({
            title: 'Warning',
            message: 'You are going to delete this program. All related data including learner data will be permanently deleted and this cannot be undone. We advise you to export the program content before you delete it.',
            onConfirm: async () => {
                const response = await fetch(this.getUrl(), {
                    method: 'DELETE', headers: {'Content-Type': 'application/json'}
                })
                if (response.ok) {
                    const result = await response.json()
                    window.location = '/?tab=program'
                } else {
                    LearningTribes.Notification.Warning({
                        title: 'error',
                        message: 'Something went wrong.'
                    })
                }
            },
            onCancel: () => {}
        })
    }
    async partialUpdate (parameters, options) {
        const response = await fetch(this.getUrl(), {
            method: 'PATCH', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(parameters)
        })
        const result = await response.json()
        if (response.ok) {
            options.success && options.success()
        } else {
            let err_msg = JSON.parse(result)
            LearningTribes.Notification.Error({
                title: gettext('Error'),
                message: err_msg.api_error_message
            })
        }
    }

    async fileUpload (file = this.cardImageFile) {
        var formData = new FormData()
        formData.append('card_image_url', file)

        this.setState({fetching: true})
        const response = await fetch(this.getUrl(), {method: 'PATCH', body: formData})
        const json = await response.json()
        this.setState({fetching: false})

        const data = await this.fetchData()
        this.setState({temporaryImageUrl: '', fileUrl: data.card_image_url + '?uuid=' + json.uuid || this.default_card_image_url})
    }
    async preRelocateCourse (course_id, order_no) {
        this.setState(prev => {
            const coursesToSort = JSON.parse(JSON.stringify(prev.coursesToSort))
            const item = coursesToSort.find(p => p.course_id === course_id)
            if (item) {
                item.order_no = order_no
            } else {
                coursesToSort.push({course_id, order_no})
            }
            return {coursesToSort}
        }, () => {
            this.confirmChange()
        })
    }
    async relocateCourses () {
        const st = this.state
        const objBody = {body: JSON.stringify({param: st.coursesToSort})}

        this.setState({fetching: true})
        const response = await fetch(`${this.getUrl()}courses/`, {
            method: 'PATCH', headers: {'Content-Type': 'application/json'}, ...objBody
        })
        this.setState({fetching: false})

        this.fetchData().then(data => {
            this.setState({data})
        })

        return await response.json()
    }

    renderDates (dates) {
        const t = gettext, {start, end, enrollment_start, enrollment_end} = this.state,
            utc = date => date ? new Date(date).toUTCString() : ''
        return <section className={dates.key}>
            <h4>{dates.text}<small>{dates.description}</small><a name={dates.key}></a></h4>
            <fieldset>
                <div className="field">
                    <label>{t('Learning Path Start Date :')}</label>
                    <span>{utc(start)}</span>
                    <div>
                        <small>{t('Automatically calculated, the learning path will start as soon as one of its course starts.')}</small>
                    </div>
                </div>
                <div className="field">
                    <label>{t('Learning Path End Date :')}</label>
                    <span>{utc(end)}</span>
                    <div>
                        <small>{t('Automatically calculated, the learning path will ends when all its courses ended.')}</small>
                    </div>
                </div>
                <div className="field">
                    <label>{t('Enrollment Start Date :')}</label>
                    <span>{utc(enrollment_start)}</span>
                    <div>
                        <small>{t('Automatically calculated, users can start to enroll in the learning path as soon as the enrollments are started for one of its course.')}</small>
                    </div>
                </div>
                <div className="field">
                    <label>{t('Enrollment End Date :')}</label>
                    <span>{utc(enrollment_end)}</span>
                    <div>
                        <small>{t('Automatically calculated, users cannot longer enroll in the learning path when enrollments are closed in all its courses.')}</small>
                    </div>
                </div>
            </fieldset>
        </section>
    }

    renderIntroduction (data, intro) {
        const t = gettext, st = this.state, {description, duration} = this.state, {is_frozen_visibility} = data
        const previewCardImage = e => {
            const file = e.currentTarget.files[0]
            const reader = new FileReader()
            reader.onload = e => this.setState({temporaryImageUrl: e.target.result})
            reader.readAsDataURL(e.currentTarget.files[0])
            this.cardImageFile = file
            this.confirmChange()
        }
        return <section className={intro.key}>
            <h4>{intro.text}<small>{intro.description}</small><a name={intro.key}></a></h4>
            <fieldset>
                <div className="field frame-wrapper">
                    <div className="image-frame">
                        <div className="img-wrapper"><img src={st.temporaryImageUrl || st.fileUrl} /></div>
                        <small>{t('Dimension')}: 400x310px</small>
                        <label htmlFor="file-card-image" className="btn-upload">{t('Upload Image')}</label>
                        <input type="file" id="file-card-image"
                            onChange={previewCardImage} />
                    </div>
                    <div className="text-frame">
                        <label>{t('Learning Path Card Image')}</label>
                        <small>{t('You can manage this image along with all of your other files and uploads')}</small>
                        <small>{t('Note: the ideal image is 400px wide by 310px tall, in JPEG format')}</small>
                    </div>
                </div>
                <div className="field description">
                    <label>{t('Learning Path Description')}</label>
                    <small>{t('Displayed on the Learning Path details page. Limit to 1000 characters.')}</small>
                    <textarea className="tinymce-editor" value={description}></textarea>
                </div>
                <div className="field duration">
                    <label>{t('Learning Path Duration :')}</label>
                    <input type="text" onKeyDown={e => this.handleDurationKeyDown(e)}
                        onBlur={this.confirmChange.bind(this)}
                        onChange={e => this.setDuration(e.currentTarget.value)}
                        defaultValue={this.getCalculatedDuration()}
                    />
                    <Dropdown value={st.durationUnit}
                        onChange={p => this.setDurationUnit(p.value)}
                        data={[
                            {text: gettext('Minutes'), value: DurationUnit.minutes},
                            {text: gettext('Hours'), value: DurationUnit.hours},
                            {text: gettext('Days'), value: DurationUnit.days},
                        ]}
                    />
                </div>
                <div className="field visibility">
                    <label>{t('Learning Path Visibility in Catalog')}</label>
                    <Dropdown value={st.visibility}
                        onChange={val => this.setVisibility(val.value, is_frozen_visibility)}
                        data={[
                            {text: gettext('Full public'), value: 0},
                            {text: gettext('Accessible by URL'), value: 1},
                            {text: gettext('Private'), value: 2},
                        ]}
                    />
                    <span className="question-mark-wrapper"
                          data-title={t("Defines the access permissions for showing the Learning Path in the catalog. This can be set to one of three values: \"full public\", \"accessible by URL\", \"private\".")}></span>
                    <div id="visibility_wraning" className="warning_message">{gettext('You cannot change the visibility status, because this learning path contains "Private" course(s).')}</div>
                </div>
            </fieldset>
        </section>
    }

    setDuration (val) {
        const {durationUnit} = this.state
        const duration = (val | 0) * (DurationUnitScalarMap[durationUnit] || 1)

        this.setState({duration})
    }

    setDurationUnit (durationUnit) {
        this.setState(prev => ({
            duration: Math.round(prev.duration / (DurationUnitScalarMap[prev.durationUnit] || 1) * (DurationUnitScalarMap[durationUnit] || 1)),
            durationUnit,
        }), this.confirmChange.bind(this))
    }

    setVisibility(val, is_frozen_visibility) {
        if (this.state.visibility === 2 && val != 2) {
            function saveChanges(self) {
                const changedFields = {}
                self.getFieldKeys().forEach(key => {
                    if (self.state[key] != self.state.temporaryData[key]) {
                        changedFields[key] = self.state[key]
                    }
                })

                if (Object.entries(changedFields).length > 0) {
                    self.confirmChange();
                }
            }

            // [Published LP] IF private courses included in Published version of this LP, then cannot change visibility.
            if (is_frozen_visibility === true) {
                this.setState({visibility: val}, ()=> this.setState({visibility: 2} ) );
                document.getElementById('visibility_wraning').style.display = 'block';

                saveChanges(this);

                return;
            }
            // [Draft LP] IF "Private" LP contains Private courses, then we can NOT change the visibility of the LP.
            for (let i = 0; i < this.state.includedCourses.length; i++) {
                if (this.state.includedCourses[i].catalog_visibility === 'none') {
                    // we have to change the visibility in callback method
                    this.setState({visibility: val}, ()=> this.setState({visibility: 2} ) );
                    document.getElementById('visibility_wraning').style.display = 'block';

                    saveChanges(this);

                    return;
                }
            }
        }

        document.getElementById('visibility_wraning').style.display = 'none';
        this.setState({visibility: val}, this.confirmChange.bind(this));
    }

    getCalculatedDuration () {
        const {durationUnit, duration} = this.state

        return Math.round(duration / (DurationUnitScalarMap[durationUnit] || 1))
    }

    handleDurationKeyDown (e) {
        if (e.key !== 'Backspace' && !e.key.startsWith('Arrow') && String(Number(e.key)) !== e.key) e.preventDefault()
    }

    async filterCourseLists (keyword_filter) {
        const delay = 500 // minimal seconds between each api request
        if (this.timer != null) {
            clearTimeout(this.timer)
            this.timer = null
        }
        if (Date.now() - this.timeOfLastRequest < delay && keyword_filter) {
            this.timer = setTimeout(async () => {
                await this.filterCourseLists(keyword_filter)
            }, delay)
            this.timeOfLastRequest = Date.now()
            return false
        }
        this.timeOfLastRequest = Date.now()

        // reset status of courses requesting IF the keyword filter changed.
        let requested_courses_table = this.state.allCourses;
        if (this.keyword_filter != keyword_filter) {
            this.next_request_pageno = 1;
            requested_courses_table = [];
            this.keyword_filter = keyword_filter;
        }

        const [fetchedCourses = [], includedCourses = []] = await Promise.all([this.fetchBatchesCourses(keyword_filter), this.fetchIncludedCourses(keyword_filter)])
        requested_courses_table.push(...fetchedCourses);   // Added first batches courses record into cache

        this.setState({
            allCourses: requested_courses_table,
            includedCourses,
            originalIncludedCourses: includedCourses
        })
    }

    openLMS (endpoint) {
        window.open(new URL(endpoint, 'http://' + this.props.lmsLink))
    }

    openPreview () {
        const {uuid} = this.state
        this.openLMS(`/programs/${uuid}/about/?viewtype=preview`)
    }

    openViewLive () {
        const {uuid} = this.state
        this.openLMS(`/programs/${uuid}/about/`)
    }

    openCourse(course_key) {
        window.open(`/settings/details/${course_key}`)
    }

    renderCourses ({key, text, description}) {
        const Icon = ({name, onClick}) => {
            return <i onClick={onClick} className={`far fa-${name}-circle icon`} />
        }
        const t = gettext, st = this.state, pr = this.props

        const getFilteredIncludedCourses = () => {
            return st.includedCourses.filter(p => {
                return !st.coursesToDetach.map(p => p.course_id).includes(p.course_id)
            })
        }, getFilterAllCourses = () => {
            const allCourses = st.allCourses, includedCourses = getFilteredIncludedCourses() //this.state.includedCourses
            const includedCourseKeys = includedCourses.map(p => p.course_id)
            const filteredCourses = allCourses.filter(p => {
                return !includedCourseKeys.includes(p.course_id) &&
                    !st.coursesToAttach.map(p => p.course_id).includes(p.course_id)
            })
            return filteredCourses
        }, filteredAllCourses = [...getFilterAllCourses(), ...st.coursesToDetach.map(p => ({...p, abstract: true}))],
            filteredIncludedCourses = [...getFilteredIncludedCourses(), ...st.coursesToAttach.map(p => ({...p, abstract: true}))]
        const preAdjustCourse = async (type, course, key) => {
            this.setState(prev => {
                return {[key]: [...prev[key], course]}
            })
            this.confirmChange()
        }
        const {released_date, status, creator_username} = this.state.data
        const EmptyListMessage = () => {
            return <li className="empty-list-message">{t('List is empty')}</li>
        }

        const publishDisabled = this.state.fetching || status === 'active' || st.includedCourses.length <= 1
        const publishButtonClassName = publishDisabled ? ' is-disabled secondary' : ' primary'
        const hide_draft_tag = status === 'active' || st.includedCourses.length <= 1

        const onScrollDownCoursesList = async (isRequesting, next_request_pageno, requested_courses_table) => {
            if (isRequesting || next_request_pageno === null) {
                return;     // return if the previous requesting is not completed OR reached the latest page already
            }

            const [fetchedCourses = []] = await Promise.all([this.fetchBatchesCourses(this.keyword_filter)]);
            requested_courses_table.push(...fetchedCourses);

            this.setState({allCourses: requested_courses_table});
        }

        return <section className={key}>
            <h4>{text}<small>{description}</small><a name={key}></a></h4>
            <div className="search-box"><i className="far fa-search"></i><input type="text" onKeyUp={async ({currentTarget: {value: val}}) => this.filterCourseLists(val)} /></div>
            <div className="courses">
                <div className="included">
                    <h5>{t('Already included in the Learning Path')}</h5>
                    {filteredIncludedCourses.length <= 0 ? <ul><EmptyListMessage /></ul> :
                        <ReactSortable list={filteredIncludedCourses} tag="ul"
                            onEnd={evt => {
                                const newIndex = evt.newIndex, item = filteredIncludedCourses[newIndex]
                                this.preRelocateCourse(item.course_id, newIndex)
                            }}
                            setList={includedCourses => this.setState({
                                includedCourses: includedCourses.filter(p => !st.coursesToAttach.map(p => p.course_id).includes(p.course_id))
                            })}>
                            {filteredIncludedCourses.map(
                                course => <li key={course.course_id} className={`${course.abstract ? 'abstract' : ''}${st.coursesToSort.find(p => course.course_id == p.course_id) ? ' sorting' : ''}`}>
                                    <span className="hand_cursor" onClick={() => this.openCourse(course.course_id)}>{course.title}</span>
                                    {course.catalog_visibility === 'none' && <span className="private_tag">{t('Private')}</span>}
                                <i onClick={async () => {
                                    if (!course.abstract) {
                                        preAdjustCourse(ActionType.detach, course, 'coursesToDetach')
                                    } else {
                                        this.setState(prev => {
                                            return {coursesToAttach: prev.coursesToAttach.filter(p => p.course_id != course.course_id)}
                                        })
                                    }
                                }} className="far fa-times-circle icon" />
                                <i className="far fa-grip-vertical handler"></i></li>)}
                        </ReactSortable>
                    }
                </div>
                <div className="all">
                    <h5>{t('Add to the Learning Path')}</h5>
                    <ul onScroll={async () => {onScrollDownCoursesList(this.isRequesting, this.next_request_pageno, this.state.allCourses)}}>
                        {
                        filteredAllCourses.length <= 0 ? <EmptyListMessage /> :
                        filteredAllCourses.sort(
                            function( c1, c2 ) {
                                if (st.visibility != 2) {
                                    if (c1.catalog_visibility === 'none' && c2.catalog_visibility != 'none') {
                                        return 1;
                                    }
                                    if (c1.catalog_visibility != 'none' && c2.catalog_visibility === 'none') {
                                        return -1;
                                    }
                                    return 0;
                                } else {
                                    return 0;
                                }
                            }
                        ).map(
                            course => <li key={course.course_id} className={course.abstract ? 'abstract' : (course.catalog_visibility === 'none' && st.visibility != 2) ? 'private_course' : ''}>
                                <span className="hand_cursor" onClick={() => this.openCourse(course.course_id)}>{course.title}</span>
                                {course.catalog_visibility === 'none' && <span className="private_tag">{t('Private')}</span>}
                                {(course.catalog_visibility != 'none' || st.visibility === 2 ) && <Icon name="plus" onClick={() => preAdjustCourse(ActionType.attach, course, 'coursesToAttach')} />}
                            </li>
                        )
                        }
                    </ul>
                </div>
            </div>
            <fieldset>
                {!hide_draft_tag &&
                    <div className="draft_lp_tag">
                        <div className="status-label">{t('Draft (Unpublished changes)')}</div>
                    </div>
                }
                <div className="field publishing">
                    {released_date && <span dangerouslySetInnerHTML={{
                        __html: '<strong>' + t('Release:') + ' ' + new Date(released_date).toUTCString() + '</strong> ' + t('By ') + (creator_username || '')
                    }}></span>}
                    <input type="button" className="primary preview"
                        onClick={this.openPreview.bind(this)}
                        value={t('Preview')} />
                    <input type="button" className={`secondary view-live${!released_date ? ' is-disabled' : ' primary'}`}
                        onClick={this.openViewLive.bind(this)}
                        disabled={!released_date}
                        value={t('View live')}
                    />
                    <input id="id_program_publish_bt" type="button" className={`publish ${publishButtonClassName}`}
                        onClick={this.publish.bind(this)}
                        disabled={publishDisabled}
                        value={t('Publish')}
                    />
                </div>
            </fieldset>
        </section>
    }
    async adjustCourses (type, courses) {
        const ids = (courses || []).map(p => (p.course_id))
        const objBody = {
            body: JSON.stringify(type == ActionType.attach ?
                {course_ids: ids} :
                {course_ids: ids, course_uuids: ids, courses_uuids: ids})
        }
        const {uuid} = this.state
        this.setState({fetching: true})
        try {
            const response = await fetch(`/api/proxy/discovery/api/v1/programs/${uuid}/courses/`, {
                method: type ? 'POST' : 'DELETE', //should be another method that can accept parameter title
                headers: {
                    'Content-Type': 'application/json',
                }, ...objBody
            })
            await response.json()
        } finally {
            this.setState({fetching: false})
        }

    }

    checkIncludedCourses () {
        const {includedCourses} = this.state
        if (includedCourses.length < 2) return LearningTribes.Notification.Error({
            title: gettext('Error'),
            message: gettext('At least two courses should be included.')
        })
    }

    save () {
        const state = this.state
        const parameterObj = {}
        this.getFieldKeys().forEach(key => {
            if (state[key] != state.temporaryData[key]) {
                parameterObj[key] = state[key]
            }
        })

        if (state.temporaryImageUrl) {
            setTimeout(() => {
                this.fileUpload()
            }, 2000)
        }

        const {coursesToAttach, coursesToDetach, coursesToSort} = this.state

        if (coursesToAttach.length > 0) this.attachCourses()
        if (coursesToDetach.length > 0) this.detachCourses()
        if (coursesToSort.length > 0) this.relocateCourses()

        if (Object.entries(parameterObj).length <= 0) return
        this.partialUpdate(parameterObj, {
            success: () => {
                this.setState({
                    temporaryData: {
                        ...pick(this.state, this.getFieldKeys()),
                        ...parameterObj
                    }
                })
            }
        })
    }
    detachCourses () {
        const st = this.state
        this.adjustCourses(ActionType.detach, st.coursesToDetach)
            .then(() => {
                let allCourses = st.allCourses, includedCourses = st.includedCourses, failedCourses = []
                allCourses = allCourses.concat(st.coursesToDetach)
                includedCourses = includedCourses.filter(p => !st.coursesToDetach.map(p => p.course_id).includes(p.course_id))
                this.setState({allCourses, coursesToDetach: [], includedCourses}, () => {
                    if (failedCourses.length > 0) {
                        LearningTribes.Notification.Error({
                            title: gettext('Error'),
                            message: gettext('can\'t delete courses from included courses')
                        })
                    }
                    this.fetchData().then(data => {
                        this.setDates(data)
                        this.setState({data})
                    })
                })
            })

    }
    attachCourses () {
        const st = this.state
        this.adjustCourses(ActionType.attach, st.coursesToAttach)
            .then(() => {
                var includedCourses = st.includedCourses, allCourses = st.allCourses, failedCourses = []
                includedCourses = includedCourses.concat(st.coursesToAttach)
                allCourses = allCourses.filter(p => !st.coursesToAttach.map(p => p.course_id).includes(p.course_id))
                this.setState({includedCourses, coursesToAttach: [], allCourses}, () => {
                    if (failedCourses.length > 0) {
                        LearningTribes.Notification.Error({
                            title: gettext('Error'),
                            message: gettext('can\'t add new courses to included courses')
                        })
                    }
                    this.fetchData().then(data => {
                        this.setDates(data)
                        this.setState({data})
                    })
                })
            })
    }
    confirmChange () {
        const t = gettext
        LearningTribes.Notification.Warning({
            title: t('You\'ve made some changes'),
            message: t('Your changes will not take effect until you save your progress.'),
            onConfirm: this.save.bind(this),
            onCancel: () => {
                const st = this.state, tData = st.temporaryData
                this.setState({
                    ...pick(st.temporaryData, this.getFieldKeys()),
                    includedCourses: st.originalIncludedCourses,
                    coursesToSort: [],
                    coursesToAttach: [],
                    coursesToDetach: [],
                    temporaryImageUrl: ''
                }, () => {
                    if (tData && tData.description !== undefined) tinyMCE.activeEditor.setContent(tData.description || '')
                })
            }
        })
    }

    renderLabel (label) {
        const t = gettext, {data} = this.state, st = this.state
        return <section className={label.key}>
            <h4>{label.text}<small>{label.description}</small><a name={label.key}></a></h4>
            <fieldset>
                <div className="field">
                    <label>{t('Learning Path Language')}</label>
                    <small>{t('Identify the main language of your course, this is used to assist users find courses that are taught in a specific language.')}</small>
                    <Dropdown data={this.state.languages} searchable={true}
                        onChange={val => this.setState({language: val.value}, this.confirmChange.bind(this))}
                        value={st.language} />
                </div>
            </fieldset>
        </section>
    }
    getN () {
        const t = gettext
        return {
            basic: {text: t('Basic Information'), key: t("basic")},
            dates: {text: t('Important Dates'), key: t("dates"), description: t('Dates that control when your Learning Path can be viewed')},
            introduction: {text: t('Introduce Your Learning Path'), key: t("introduction"), description: t('Information for prospective learners')},
            label: {text: t('Label Your Learning Path'), key: t("label"), description: t('Provide useful information about your Learning Path')},
            adding: {text: t('Add Courses'), key: t("adding"), description: t('Add courses to your Learning Path')},
            deleting: {text: t('Delete Learning Path'), key: t("deleting"), description: t('Delete your entire learning path and all data')}
        }
    }

    render () {
        const t = gettext, N = this.getN()
        const {data, title: title1} = this.state, st = this.state

        if (!this.props.enable_delete_program) {
            delete N['deleting']
        }

        return !st.dataLoaded ? <Loading /> : <div className={`program-editing-form ${this.props.active ? 'active' : ''}`}>
            <div className={"nav"}>{Object.keys(N).map(id => <a href={`#${id}`} key={id} className={id}>{N[id].text}</a>)}</div>
            <article>
                <h2>{t('Schedule & Details')}</h2>
                <section className={N.basic.key}>
                    <h4>{N.basic.text}<a name={N.basic.key}></a></h4>
                    <fieldset>
                        <div className="field">
                            <label>{t('Learning Path Title')}</label>
                            <small>{t('Displayed as title on the Learning Path details page. Limit to 50 characters.')}</small>
                            <input type="text"
                                onChange={e => this.setState({title: e.currentTarget.value})}
                                onBlur={this.confirmChange.bind(this)}
                                placeholder={t('Learning Path title')} value={title1} />
                        </div>
                    </fieldset>
                </section>
                {this.renderDates(N.dates)}
                {this.renderIntroduction(data, N.introduction)}
                {this.renderLabel(N.label)}
                {this.renderCourses(N.adding)}

                {this.props.enable_delete_program &&
                    <section className={N.deleting.key}>
                        <h4>{N.deleting.text}<small>{N.deleting.description}</small><a name={N.deleting.key}></a></h4>
                        <fieldset>
                            <div className="field">
                                <div>
                                    <p dangerouslySetInnerHTML={{__html: t('%i Please note $i : Deleting a learning path and all related data is permanent and cannot be undone.').replace('%i', '<strong>').replace('$i', '</strong>')}}></p>
                                    <p>{t('We will not be able to recover the learning path or the data that is deleted.')}</p>
                                </div>
                                <button onClick={this.delete.bind(this)}><i className="far fa-trash-alt"></i><span>{t('Delete Learning Path')}</span></button>
                            </div>
                        </fieldset>
                    </section>
                }

            </article>

        </div>
    }
}

export default EditingForm
