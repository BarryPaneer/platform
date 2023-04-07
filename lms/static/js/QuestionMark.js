/* global gettext */
/* eslint react/no-array-index-key: 0 */

import PropTypes from 'prop-types';
import React, {Fragment} from 'react';
import ReactDOM from 'react-dom'
import Dropdown from 'lt-react-dropdown'
import {DateUtils} from '../js/DateUtils'
import {Notification} from './Notification'
import Cookies from "js-cookie";

function formatDate2(date, userLanguage, userTimezone) {
  var context;
  context = {
    datetime: date,
    language: userLanguage,
    timezone: userTimezone,
    format: 'LL'
  };
  return DateUtils.localize(context);
}
//window.formatDate2 = formatDate2

class QuestionMark extends React.Component {
    constructor(props) {
        super(props);
        this.myRef = React.createRef();

        this.handleResize = this.handleResize.bind(this)
    }

    handleResize(e) {
        if (!this.myRef.current) return

        const docWidth = document.body.offsetWidth
        const elementX = this.myRef.current.getBoundingClientRect().x
        if (docWidth - elementX < 100){
          this.myRef.current.classList.add('icon-question--left')
        } else {
          this.myRef.current.classList.remove('icon-question--left')
        }
    }

    componentDidMount () {
      window.addEventListener('resize', this.handleResize)
      this.handleResize()
    }

    componentWillUnmount () {
      window.removeEventListener('resize', this.handleResize)
    }

    render() {
        return (
            <div className="wrapper">
            <span ref={this.myRef} className="icon-question">
                <span className="before"></span>
                <i className="fas fa-question-circle"></i>
                <span className="after" dangerouslySetInnerHTML={{__html:this.props.tooltip}}></span>
            </span>
            </div>
        );
    }
}

window.LearningTribes = window.LearningTribes || {};

const _Notification = function (obj) {
    var {element }= obj;
    if (element == null){
        var $el = $('#page-notification')
        if ($el.length <= 0) {
            ($('#admin-panel') || $('body')).append('<div id="page-notification"></div>')
            $el = $('#page-notification')
        }
        element = $el[0]
    }
    ReactDOM.render(
      React.createElement(Notification, obj, null),
      element
    );
}
//window.LearningTribes.Notification = window.LearningTribes.Notification || {}
var _NFactory = function(type) {
    return function(obj) {
        //:'warning'
        new _Notification(_.extend(obj, {type}));
    }
}
/*
window.LearningTribes.Notification = {
    Warning:_NFactory('warning'),
    Error:_NFactory('error'),
    Info:_NFactory('info'),
}
*/
//['warning', 'error', 'info']
/*window.LearningTribes.Notification.Warning = function(obj) {
    new _Notification(_.extend(obj, {type:'warning'}));
}
window.LearningTribes.Notification.Error = function(obj) {
    new _Notification(_.extend(obj, {type:'error'}));
}
window.LearningTribes.Notification.Info = function(obj) {
    new _Notification(_.extend(obj, {type:'info'}));
}*/

//temporary placed here, please don't mind~

const MetaType = {
    post: {
        method: 'POST',
        headers: {
            'X-CSRFToken': Cookies.get('csrftoken'),
            'Content-Type': 'application/json',
        },
    },
    patch: {
        method: 'PATCH',
        headers: {
            'X-CSRFToken': Cookies.get('csrftoken'),
            'Content-Type': 'application/json',
        },
    },
    delete: {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        },
    }
},EnrollmentStatus={enrolled:'enrolled',canceled:'canceled'}
/*
- add property isDebug   o
- make api configurable   o
*/
class Registration extends React.Component {
    constructor(props, context) {
        super(props, context);
        this.state = {
            activeTab:'enrolled',
            searchingStr:'',
            enrolledList:[],
            list:[]
        }
    }

    startFetch({userName}){
        this.userName = userName;
        this.fetch()
    }

    fetch(){
        let title = this.state.searchingStr, userName=this.userName
        const load = ()=>{
            Promise.all([this.fetchEnrolled({title, userName}), this.fetchList({title, userName})])
            .then(([enrolled,all])=>{
                this.fetchTime = Date.now();
                this.setState({enrolledList:enrolled.results,list:all.results,
                    enrolledCount:enrolled.count, allCount:all.count
                })
            })
        }
        if (Date.now() - this.fetchTime < 500) {
            this.fetchTime = Date.now()
            this.timer && clearTimeout(this.timer)
            this.timer = setTimeout(load, 500)
        }else{
            load()
        }
    }

    fetchEnrolled ({title,userName}) {
        const pr = this.props
        return new Promise((resolve, reject)=>{
            if (pr.isDebug && !pr.isMockRequest) {
                resolve({
                    "page_no":1,
                    "page_size":10,
                    "count":36,
                    "results":[{
                        "uuid":"addffb-a123f",
                        "title":"edX Demonstration Program1",
                        "enrollment_start":"Tue, 05 Feb 2013 05:00:00 GMT",
                        "end":"Tue, 08 Feb 2014 07:00:00 GMT"
                    }, {
                        "uuid":"kdkkafas-asdf",
                        "title":"edX Demonstration Program2",
                        "enrollment_start":"Fri, 04 Feb 2012 06:00:00 GMT",
                        "end":"Mon, 01 Feb 2014 07:00:00 GMT"
                    }]
                })
            }else {
                fetch(pr.isMockRequest?'/admin_panel/enrolled/':pr.enrolledListAPI.replace('${userName}', userName) + `&title=${title}&page_size=99`)
                    .then(res=>res.json())
                    .then(json=>resolve(json))
            }
        })
    }
    fetchList({title,userName}){
        const pr = this.props
        return new Promise((resolve, reject)=>{
            if (pr.isDebug && !pr.isMockRequest) {
                resolve({
                    "page_no":1,
                    "page_size":10,
                    "count":106,
                    "results":[{
                        "uuid":"kldasklfads",
                        "title":"edX Demonstration Program3",
                        "enrollment_start":"Tue, 05 Feb 2013 05:00:00 GMT",
                        "end":"Tue, 08 Feb 2014 07:00:00 GMT"
                    }, {
                        "uuid":"kldkllkaijf",
                        "title":"edX Demonstration Program4",
                        "enrollment_start":"Fri, 04 Feb 2012 06:00:00 GMT",
                        "end":"Mon, 01 Feb 2014 07:00:00 GMT"
                    }, {
                        "uuid":"aaadf",
                        "title":"edX Demonstration Program5",
                        "enrollment_start":"Fri, 04 Feb 2012 06:00:00 GMT",
                        "end":"Mon, 01 Feb 2014 07:00:00 GMT"
                    }]
                })
            } else {
                fetch(pr.isMockRequest?'/admin_panel/list/':pr.allListAPI.replace('${userName}', userName) + `&title=${title}&page_size=99`)
                    .then(res=>res.json())
                    .then(json=>resolve(json))
                    .catch(err=>console.log(err))
            }
        })
    }
    manageEnrollment(uuid, action_type, enrollment_status){
        const pr = this.props
        const trigerSuccess=()=>{
            this.setState(prev => {
                if (action_type === 'unenroll') {
                    LearningTribes.Notification.Info({
                        title:gettext("Successfully unenrolled"),
                        message:gettext("The user is no longer enrolled in the learning path(s)."),
                    })
                    const enrolledList = prev.enrolledList.filter(p => p.uuid != uuid)
                    const list = [...prev.list, prev.enrolledList.find(p => p.uuid == uuid)]
                    return {
                        enrolledList,
                        list,
                        enrolledCount: enrolledList.length,
                        allCount: list.length,
                    }
                } else {
                    LearningTribes.Notification.Info({
                        title:gettext("Successfully enrolled"),
                        message:gettext('The user have been successfully enrolled.'),
                    })
                    const enrolledList = [...prev.enrolledList, prev.list.find(p => p.uuid == uuid)]
                    const list = prev.list.filter(p => p.uuid != uuid)
                    return {
                        enrolledList,
                        list,
                        enrolledCount: enrolledList.length,
                        allCount: list.length,
                    }
                }
            })
        }

        const program_enrollment_url = pr.enrollmentAPI.replace('${userName}', this.userName);

        if (action_type === 'enroll') {
            var param = (enrollment_status === null) ? MetaType.post : MetaType.patch;

            fetch(program_enrollment_url, {
                ...param,
                body: JSON.stringify({status: EnrollmentStatus.enrolled, cascade_courses: true, uuid})
            })
                .then(res => {
                    if ([200, 201].includes(res.status)) {
                        trigerSuccess()
                    }
                    return res.json()
                })
                .catch(err => console.log(err))
        } else if (action_type === 'unenroll') {
            fetch(program_enrollment_url, {
                ...MetaType.patch,
                body: JSON.stringify({status: EnrollmentStatus.canceled, cascade_courses: true, uuid})
            })
                .then(res => {
                    if ([200, 201].includes(res.status)) {
                        trigerSuccess()
                    }
                    return res.json()
                })
                .catch(err => console.log(err))
        }

    }

    unenroll({uuid, enrollment_status}){
        LearningTribes.Notification.Warning({
            ...NOTICE.unenrollConfirmation,
            cancelText:gettext('Cancel'),
            confirmText:gettext('Confirm'),
            onCancel:function(){},
            onConfirm:()=>{
                this.manageEnrollment(uuid, 'unenroll', enrollment_status)
            }
        })
    }
    enroll({uuid, enrollment_status}) {
        LearningTribes.Notification.Warning({
            ...NOTICE.enrollConfirmation,
            cancelText:gettext('Cancel'),
            confirmText:gettext('Confirm'),
            onCancel:function(){},
            onConfirm:()=>{
                this.manageEnrollment(uuid, 'enroll', enrollment_status)
            }
        })
    }

    render() {
        const t = gettext
        const {enrolledList, list, activeTab} = this.state
        const st = this.state
        const resultsFormat = n => ngettext('{results} Result', '{results} Results', n || 0).replace('{results}', n || 0)

        return (
            <>
                <div className="search-wrapper">
                    <form className="user-search">
                        <input className="search-input" onChange={e=>{this.setState({searchingStr:e.currentTarget.value}, this.fetch)}} type="text" placeholder={t('Search...')} />
                        <button className="button input-submit" type="submit" title="${_('Search')}" onClick={e => e.preventDefault()}>
                            <span className="icon far fa-search"></span>
                        </button>
                    </form>
                </div>
                <h3 className="enrollment-titles">
                    <span onClick={()=>this.setState({activeTab:'enrolled'})} className={`enrolled${activeTab=='enrolled'?' active':''}`}>{t('Is currently enrolled in...')}</span>
                    <span onClick={()=>this.setState({activeTab:'list'})} className={`unenrolled${activeTab=='list'?' active':''}`}>{t('Could be enrolled in...')}</span>
                </h3>
                <div className="enrollments">
                    <ul className={`currently-enrolled${activeTab=='enrolled'?' visible':''}`}>
                        <h3>{t('Is currently enrolled in...')}</h3>
                        <div className="class-list-wrapper">
                            {enrolledList.map(p => (
                                <RegistrationItem key={p.uuid} {...p}
                                    displayDetail={true}
                                    onClick={this.unenroll.bind(this, p)}
                                    icon="times-circle"
                                />
                            ))}
                        </div>
                        <span className="result-number">{resultsFormat(st.enrolledCount)}</span>
                    </ul>
                    <ul className={`not-enrolled${activeTab=='list'?' visible':''}`}>
                        <h3>{t('Could be enrolled in...')}</h3>
                        <div className="class-list-wrapper">
                            {list.map(p => (
                                <RegistrationItem key={p.uuid} {...p}
                                    onClick={this.enroll.bind(this, p)}
                                    icon="plus-circle"
                                />
                            ))}
                        </div>
                        <span className="result-number">{resultsFormat(st.allCount)}</span>
                    </ul>
                </div>
            </>
        )
    }
}

function RegistrationItem (props) {
    const dateFormat = dateStr => {
        if (dateStr && dateStr !== 'is_null') return new Date(dateStr).toLocaleDateString()
        return '–'
    }

    return (
        <li>
            <div className="enrollment-info">
                <p className="display-name"><a style={{color: 'inherit'}} target="_blank" href={`/programs/${props.uuid}/about`}>{props.title}</a></p>
                {props.displayDetail && (
                    <Fragment>
                        <p className="enrollment-date">{gettext('Enrollment Date')}: {dateFormat(props.enrollment_created)}</p>
                        <p className="enrollment-date">{gettext('Completion Date')}: {dateFormat(props.enrollment_completed)}</p>
                    </Fragment>
                )}
            </div>
            <div className="enrollment-button">
                <i onClick={props.onClick} className={`far fa-${props.icon}`}/>
            </div>
        </li>
    )
}

export {formatDate2, Notification, QuestionMark, Dropdown, ReactDOM, React, Registration}

QuestionMark.propTypes = {
    tooltip: PropTypes.string,
};
