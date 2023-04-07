/* global gettext */
/* eslint react/no-array-index-key: 0 */

import PropTypes from 'prop-types';
import React, {useState, Fragment} from 'react';
import ReactDOM from 'react-dom'
import Dropdown from 'lt-react-dropdown'
import '../../../../../common/static/js/vendor/tinymce/js/tinymce/tinymce.full.min'
import {EditingForm as PathEditingForm, CreatingForm as PathCreatingForm} from './programs/forms'
import {ProgramTeam, Menu}from './program_teams/index'
import {Info, IsDebug} from './shared'

export const NavActions = (props) => {
    var [activeButton, setActiveButton] = useState('')
    const {
        course_creator_status = 'granted',
        STUDIO_REQUEST_EMAIL,
        show_new_library_button = true
    } = props
    const actviateButton = (name) => {
        const {onActviated} = props
        onActviated && onActviated(name)
        setActiveButton(name)
    }
    return <li className="nav-item">
        {course_creator_status == 'granted'
            ? <a href="#"
               className={"button new-button new-course-button" + (activeButton == 'course' ? ' is-disabled' : '')}
               title={gettext('Create a new course')} onClick={() => {
                actviateButton('course')
               }}>
                <span
                className="icon fa fa-plus icon-inline" aria-hidden="true"></span>{gettext("New Course")}</a>
            : <a href={`mailto:${STUDIO_REQUEST_EMAIL}`}>{gettext("Email staff to create course")}</a>
        }
        {props.is_program_enabled && <a href="#" className={"button new-button new-path-button" + (activeButton == 'path' ? ' is-disabled' : '')}
           title={gettext('Create a new path')} onClick={() => {
            actviateButton('path')
        }}><span
            className="icon fa fa-plus icon-inline" aria-hidden="true"></span>
            {gettext("New Learning Path")}</a>}
        {show_new_library_button
        && <a href="#"
              className={"button new-button new-library-button" + (activeButton == 'library' ? ' is-disabled' : '')}
              title={gettext('Create a new library')} onClick={() => {
            actviateButton('library')
        }}><span className="icon fa fa-plus icon-inline" aria-hidden="true"></span>
            {gettext("New Library")}</a>}
    </li>
}

export const Tabs = (props) => {
    const tabs = props.is_program_enabled
        ? {
            'courses': {title: 'See the courses', text: gettext('Courses')},
            'paths': {title: 'See my paths', text: gettext('Learning Paths')},
            'libraries': {title: 'See my libraries', text: gettext('Libraries')}
        }
        : {
            'courses': {title: 'See the courses', text: gettext('Courses')},
            'libraries': {title: 'See my libraries', text: gettext('Libraries')}
        }
    const [activeTabKey, setActiveTabKey] = useState('courses')
    const showTab = (e, key) => {
        setActiveTabKey(key)
        props.onTabActive && props.onTabActive(e, key)
    }
    return <React.Fragment>
        {Object.keys(tabs).map(key => <li key={key} onClick={e => {
            showTab(e, key)
        }} className={`${key}-tab${key == activeTabKey ? ' active' : ''}`}
                                          title={tabs[key].title}>{tabs[key].text}</li>)}
    </React.Fragment>
}

class Toolbar extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            query: '',
            selectedLanguages: []
        };
    }

    fireOnChange() {
        const {query, selectedLanguages} = this.state
        const {onChange} = this.props;
        onChange && onChange({query, languages: selectedLanguages})
    }

    reset() {
        this.setState({selectedLanguages: [], query: ''}, this.fireOnChange)
    }

    render() {
        const {query, selectedLanguages} = this.state
        return <div className="toolbar">
            <div className="text-search">
                <span className="far fa-search"></span>
                <input type="text" value={query} onChange={e => {
                    this.setState({query: e.currentTarget.value}, this.fireOnChange)
                }}/>
            </div>
            <Dropdown data={this.props.languages} multiple={true} placeHolderStr={gettext('Language')} value={selectedLanguages.map(p => p.value).join(',')}
                      onChange={arr => {
                          this.setState({selectedLanguages: arr}, this.fireOnChange)
                      }}/>
            <span className="far fa-sync-alt reset" onClick={this.reset.bind(this)}></span>
        </div>
    }
}

class Paths extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            activeRowID:'',
            editing: false,
            displayGuideMessage:false,
            displayNoResultMessage:false,

            facetOptions: {},

            filterTerms: props.filterTerms || {},
            languages: [], //[{text:'english', value:'en'},{text:'french', value:'fr'},{text:'chinese', value:'zh-CN'}],
            paths: []
        };

    }

    componentDidMount() {
        this.fetchFacet().then(()=>{
            const languageObj = {"fr": 'Français', "en": 'English', "de": "DE", "es": "ES", 'zh-CN': '中文'}
            const termKeys = Object.keys(this.state.facetOptions.language.terms)
            const languages = Object.keys(languageObj).filter(key => termKeys.includes(key)).map(key => ({
                text: languageObj[key],
                value: key
            }))
            this.setState({languages}, ()=>{
                this.fetchData({}).then(data=>{
                    this.setState({
                        paths: data.results,
                        displayGuideMessage: data.results?.length > 0?false:true
                    })
                });
            })
        })
    }

    async fetchFacet() {
        return fetch('/course_search/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                search_string: '', page_index: 0, page_size: 1500
            })
        })
            .then(response => response.json())
            .then(data => {
                this.setState({
                    facetOptions: data.facets
                })
            });
    }

    async fetchData(filter) {
        if (!this.props.is_program_enabled) {
            return
        }

        var formData = new FormData();
        if (filter.query) {
            formData.append('search_string', filter.query);
        }
        if (filter.languages && filter.languages.length > 0) {
            formData.append('language', filter.languages.map(p => p.value))
        }

        return fetch('/program_search/', {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
    }

    edit(uuid){
        window.location=`/program_detail/?program_uuid=${uuid}`
        /* please keep it, it may be used in the future.
        const {onEdit, languages} = this.props
        this.setState({activeRowID: uuid, editing: true}, ()=>{
            onEdit && onEdit({uuid, languages});
        })*/
    }

    handleClickGetStarted () {
        const $button = document.querySelector('.new-path-button.new-button')
        $button.click()
    }

    render() {
        const {languages, paths, editing} = this.state, state=this.state
        const rowRender = (field) => {
            const {title, courses_count, uuid} = field.data;
            return <tr key={uuid}>
                <th><a href={`/program_detail/?program_uuid=${uuid}`}>{title}</a></th>
                <td>{courses_count}</td>
                <td><span className="icon far fa-ellipsis-h"></span>
                    <ul className="menu">
                        <li><i className="far fa-eye"></i><span>{gettext('View live')}</span></li>
                        <li onClick={this.edit.bind(this, uuid)}><i className="far fa-edit"></i><span>{gettext('Edit')}</span></li>
                    </ul>
                </td>
            </tr>
        }

        return <Fragment>
            {!state.displayGuideMessage && (
                <Toolbar languages={languages} onChange={filter=>{
                    this.fetchData(filter).then(data=>{
                        const resultLength=data.results?.length
                        if (resultLength && resultLength > 0) {
                            this.setState({
                                filter,
                                displayNoResultMessage: false,
                                paths: data.results
                            })
                        } else {
                            this.setState({ filter,displayNoResultMessage: true })
                        }
                    })
                }} />
            )}

            {state.filter?.query && state.displayNoResultMessage && (
                <div className="search-status-label">
                    <span id="discovery-message">We couldn't find any results for "{state.filter?.query || ''}".</span>
                </div>
            )}

            {state.displayGuideMessage ? (
                <div className={`welcome-view ${!state.displayGuideMessage?'hidden':''}`}>
                    <div className="description">
                        <h3>{gettext('Start creating your first Learning Path')}</h3>
                        <p>{gettext('You do not have any Learning Paths created yet. To create and publish your first Learning Path, click on the button below.')}</p>
                        <input type="button" onClick={this.handleClickGetStarted.bind(this)} value={gettext('Let’s get started')}/>
                    </div>
                    <img src={`/static/studio/images/learning-paths-illustration.png`}/>
                </div>
            ) : (
                <div className="list-wrapper">
                    <div id="discovery-message" className="search-status-label"></div>
                    <table className="list">
                        <thead>
                        <tr>
                            <td>{gettext('Learning Path Name')}</td>
                            <td>{gettext('Number of Courses')}</td>
                            <td>{gettext('Action')}</td>
                        </tr>
                        </thead>
                        <tbody>{
                            paths.map((p, i) => rowRender(p, i))
                        }

                        </tbody>
                    </table>
                </div>
            )}
        </Fragment>
    }


}

function CourseOrLibraryListing(props) {
    const allowReruns = props.allowReruns;
    const linkClass = props.linkClass;
    const idBase = props.idBase;

    return (
        <div className="list-wrapper program-list">
            <ul className="list-courses">
                {
                    props.items.map((item, i) =>
                        (
                            <li key={i} className="course-item" data-course-key={item.course_key}>
                                <a className={linkClass} href={item.url}>
                                    <h3 className="course-title" id={`title-${idBase}-${i}`}>{item.display_name}</h3>
                                    <div className="course-metadata">
                      <span className="course-org metadata-item">
                        <span className="label">{gettext('Organization:')}</span>
                        <span className="value">{item.org}</span>
                      </span>
                                        <span className="course-num metadata-item">
                        <span className="label">{gettext('Course Number:')}</span>
                        <span className="value">{item.number}</span>
                      </span>
                                        {item.run &&
                                        <span className="course-run metadata-item">
                        <span className="label">{gettext('Course Run:')}</span>
                        <span className="value">{item.run}</span>
                      </span>
                                        }
                                        {item.can_edit === false &&
                                        <span className="extra-metadata">{gettext('(Read-only)')}</span>
                                        }
                                    </div>
                                </a>
                                {item.lms_link && item.rerun_link &&
                                <ul className="item-actions course-actions">
                                    {allowReruns &&
                                    <li className="action action-rerun">
                                        <a
                                            href={item.rerun_link}
                                            className="button rerun-button"
                                            aria-labelledby={`re-run-${idBase}-${i} title-${idBase}-${i}`}
                                            id={`re-run-${idBase}-${i}`}
                                            title={gettext('Re-run Course')}
                                        >{gettext('Re-run Course')}</a>
                                    </li>
                                    }
                                    <li className="action action-view">
                                        <a
                                            href={item.lms_link}
                                            rel="external"
                                            className="button view-button"
                                            aria-labelledby={`view-live-${idBase}-${i} title-${idBase}-${i}`}
                                            id={`view-live-${idBase}-${i}`}
                                            title={gettext('View Live')}
                                        >{gettext('View Live')}</a>
                                    </li>
                                </ul>
                                }
                            </li>
                        ),
                    )
                }
            </ul>
        </div>
    );
}

const Initialize = ({lmsLink, enable_delete_program})=>{
    const program_uuid = (new URLSearchParams(window.location.search)).get('program_uuid'), pageUrl=window.location.href,
        isProgramTeamPage=()=>{return pageUrl.indexOf('/program_team')>=0},
        isProgramDetailPage=()=>{return pageUrl.indexOf('/program_detail')>=0}
    var  h2 = null, programData = {}
    var programTeam = null
    if (isProgramTeamPage() || isProgramDetailPage()) {
        //create a dom element
        h2 = document.createElement('h2')
        document.querySelector('.branding').after(h2)
        // create nav dom element
        const nav = document.createElement('nav')
        nav.className = 'nav-program nav-dd'
        h2.after(nav)

        ReactDOM.render(React.createElement(Menu, {
            menus:[
                {text:'Schedule & Details', onClick:()=>{
                    window.location = `/program_detail/?program_uuid=${program_uuid}`
                }},
                {text:'Learning Path Team', onClick:()=>{
                    window.location = `/program_team/?program_uuid=${program_uuid}`
                }},
            ]
        }),nav);
        ReactDOM.render(React.createElement(Info, { uuid:program_uuid, onLoad:(p)=>{
            programTeam ? programTeam.programData = p : ''
            } }),h2);

    }
    if (isProgramTeamPage()) {
        programTeam = ReactDOM.render(
            React.createElement(ProgramTeam, {
                isDebug: IsDebug,
                uuid: program_uuid,  //'2b29ab30-0db2-496c-9ba0-d731273d0410'
                programData
            }, null),
            document.querySelector('#content')
        );
    }
    if (isProgramDetailPage()) {
        ReactDOM.render(
            React.createElement(PathEditingForm, {
                isDebug:IsDebug,
                uuid:program_uuid,
                active: true,
                lmsLink,
                enable_delete_program
            }, null),
            document.querySelector('#content')
        );
    }
}

export {ProgramTeam, Paths, PathCreatingForm, PathEditingForm, CourseOrLibraryListing, Initialize}

CourseOrLibraryListing.propTypes = {
    allowReruns: PropTypes.bool.isRequired,
    idBase: PropTypes.string.isRequired,
    items: PropTypes.arrayOf(PropTypes.object).isRequired,
    linkClass: PropTypes.string.isRequired,
};
