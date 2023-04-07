import React from "react";
import Cookies from "js-cookie";
import {SideBar} from './EdflexCoursesSidebar'
import InfiniteScroll from "react-infinite-scroll-component";

import {EdflexCourseCard} from './ExternalCourseCard'
import CatalogTabs from "./ExternalCatalogTabs";


export class EdflexCatalogCourses extends React.Component {
    constructor(props) {
        super(props);
        let sidebarStatus = true;
        try {
            const triboo = localStorage.getItem('triboo');
            sidebarStatus = triboo === '' ? {} : JSON.parse(triboo).sidebarStatus;
        } catch (e) {
            localStorage.setItem('triboo', {})
        }

        this.state = {
            firstTimeLoading:true,
            sidebarStatus: sidebarStatus,
            sidebarData:{
                courseTypes: [],
                courseCategories: [],
                languages: []
            },
            courses: [],
            searchParameters: {},
            isFetching: false,
            hasMore: false,
            recordCount: 0,
            searchString: '',
            sort_type: '-start_date',
            pageSize: 60,
            pageNo: 1
        };
        this.fetchData = this.fetchData.bind(this);
    }

    componentDidMount() {
        this.fetchSidebarData();
        this.fetchData({}).then(()=>{
            this.setState({firstTimeLoading:false})
        });
    }

    fetchSidebarData() {
        fetch("/edflex_catalog", {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': Cookies.get('csrftoken'),
            },
        })
            .then(res => res.json())
            .then(
                (result) => {
                    this.setState({
                        sidebarData: this.parseSidebarData(result.facet_content)
                    })
                }
            )
    }

    parseSidebarData({type, categories, language}){
        const sortFn = (a, b) => {
            if (a.text < b.text) {
                return -1;
            }
            if (a.text > b.text) {
                return 1;
            }
            return 0;
        };
        const languageNameObj = {
            fr: gettext('French'), en: gettext('English'), es: gettext('Spanish'),
            pt: gettext('Portuguese'), it: gettext('Italian'), de: gettext('German'),
            zh: gettext('Mandarin')
        };
        language.forEach(function(item, index, arr) {
            if(item.value == null) {
                arr.splice(index, 1);
            }
        });
        return {
            courseTypes: type.map(p => ({...p, text: gettext(p.value), label: p.count})),
            courseCategories: categories.sort(sortFn),
            languages: language.map(p => ({text: languageNameObj[p.value], value: p.value, label: p.count}))
        }
    }

    fetchData(p) {
        const {filterValue, topic, selectedCourseTypes, selectedLanguages} = p || this.state.searchParameters;
        const {pageSize, pageNo, sort_type} = this.state;
        const obj = {
            search_content: filterValue || '',
            filter_content: {},
            page_size: pageSize,
            page_no: pageNo,
            sort_type: sort_type
        };
        if (topic && topic.value) {
            obj.filter_content['categories'] = topic.text
        }

        if (selectedCourseTypes && selectedCourseTypes.length > 0) {
            obj.filter_content['type'] = selectedCourseTypes.map(p => p.value)
        }
        if (selectedLanguages && selectedLanguages.length > 0) {
            obj.filter_content['language'] = selectedLanguages.map(p => p.value)
        }
        this.setState({isFetching:true});
        return fetch("/edflex_catalog/courses", {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': Cookies.get('csrftoken'),
            },
            body: JSON.stringify(obj),
        })
            .then(res => res.json())
            .then(
                (result) => {
                    const {facet_content,course_list,course_count,search_content}=result;
                    this.setState(prev=>{
                        return {
                            isFetching:false,
                            recordCount: course_count,
                            searchString: search_content,
                            hasMore: this.getHasMore(course_count),
                            sidebarData: this.parseSidebarData(facet_content),
                            courses: prev.courses.concat(course_list)
                        }
                    });
                    document.getElementById('id_show_loading').style.display = 'none';
                    if (this.getHasMore(course_count) || (0 === course_count && this.state.searchString != "")) {
                        document.getElementById('id_show_more_btn').style.display = 'block';
                    }
                },
            )
            .catch(error => {
                this.setState({
                    recordCount: 0,
                    searchString: '',
                    hasMore: false,
                    sidebarData: {},
                    courses: []
                });
                console.error('Error:', error);
            })
    }

    startFetch(searchParameters){
        this.setState({
            pageNo:1,
            searchParameters,
            courses:[]
        },this.fetchData)
    }

    updateSidebarDisplayStatus(sidebarStatus) {
        this.setState({sidebarStatus}, ()=>{
            localStorage.setItem('triboo', JSON.stringify({sidebarStatus}))
        })
    }

    getHasMore(course_count){
        const {pageSize, pageNo} = this.state;
        return ((pageSize * pageNo) < course_count)
    }

    sortPage(sort_type) {
        this.setState(
            {sort_type: sort_type, courses: [], pageNo: 1},
            this.fetchData
        )
    }

    fetchMoreData() {
        if (
            (
                this.getHasMore(this.state.recordCount)
                ||
                (   // Case: search nothing, but still need to scroll down for `all`
                    0 === this.state.recordCount && this.state.searchString != ""
                )
            )
            && !this.state.isFetching
        ) {
            if (0 === this.state.recordCount) {
                this.state.searchString = '';
            }

            this.setState(() => {
                return {pageNo: this.state.pageNo + 1}
            }, this.fetchData)
        }
    }

    render() {
        const {sidebarStatus, courses, sidebarData} = this.state;
        const {edflex_title, crehana_title, anderspink_title, external_catalogs} = this.props;

        const Switcher = props => {
            return <a href="/courses"><span className="switcher"><span className="round-button">{gettext("Internal")}</span><span className="round-button active">{gettext("External")}</span></span></a>
        }

        return (
            <section className="find-courses">
                <section className="banner">
                    <section className="welcome-wrapper">
                        <h2>{gettext("Explore")}</h2>
                        <Switcher/>
                    </section>
                    <CatalogTabs external_catalogs={external_catalogs} current="EDFLEX" />
                </section>
                <div className="courses-wrapper">
                    <SideBar
                        {...sidebarData}
                        status={this.state.sidebarStatus}
                        onToggle={this.updateSidebarDisplayStatus.bind(this)}
                        onApply={this.startFetch.bind(this)}
                        onChange={this.startFetch.bind(this)}
                    />
                    <CourseContainer
                        indent={sidebarStatus}
                        {..._.pick(this.state, ['hasMore', 'recordCount', 'searchString', 'firstTimeLoading'])}
                        {..._.pick(this.props, ['language', 'edflex_url', 'edflex_button_name'])}
                        onNext={this.fetchMoreData.bind(this)}
                        onChange={this.sortPage.bind(this)}
                        onIndentClick={() => this.setState({sidebarStatus: true}, ()=>{
                            localStorage.setItem('triboo', JSON.stringify({sidebarStatus:true}))
                        })}
                        data={courses}
                    />
                </div>
            </section>
        )
    }
}

class InfiniteManuallyScroll extends InfiniteScroll {
    constructor(props) {
        super(props);
    }

    isElementAtBottom(target, scrollThreshold) {
        return false;
    }
}

class CourseContainer extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            selected_option: '-start_date',
            selected_name: gettext('Most Recent').trim()
        };

        this.all_options = Array(
                ['-start_date', gettext('Most Recent').trim()],
                ['+start_date', gettext('Oldest').trim()],
                ['+display_name', gettext('Title A-Z').trim()],
                ['-display_name', gettext('Title Z-A').trim()],
        );
    }

    fireIndentClick() {
        const {onIndentClick} = this.props;
        onIndentClick && onIndentClick();
    }

    fireNext() {
        const {onNext}=this.props;
        document.getElementById('id_show_loading').style.display = 'block';
        document.getElementById('id_show_more_btn').style.display = 'none';
        onNext && onNext();
    }

    fireOnChange() {
        const {props} = this, {onChange} = props;

        const DELAY = 500;
        if (Date.now()-this.start < DELAY) {
            clearTimeout(this.timer)
        };
        this.start = Date.now();

        this.timer = setTimeout(()=>{
            onChange && onChange(this.state.selected_option);
        }, DELAY);
    }

    applySortType(event) {
        let el = $(event.target);
        this.state.selected_name = el.text();
        let selected_option = el.attr("sort_type");

        this.setState({
            selected_option
        }, this.fireOnChange)
    }

    render() {
        const {data, hasMore, recordCount, searchString, firstTimeLoading} = this.props;
        const items = [];
        data.forEach((course, index) => {
            items.push(
                <EdflexCourseCard key={`id-${index}`}
                            systemLanguage={this.props.language}
                            {...course}
                            image={course.image || course.image_url}
                />
            )
        });
        const skeletons = Array(12).fill(1).map((val,index)=><div key={'index'+index} className="skeleton"></div>);

        const sort_items = [];
        this.all_options.forEach(
            (option, index) => {
                if (option[0] != this.state.selected_option) {
                    sort_items.push(
                        <a href="#">
                            <div onClick={this.applySortType.bind(this)} class="discovery-sort-item" sort_type={option[0]}>{option[1]}</div>
                        </a>
                    );
                }
            }
        )

        return (
            <main className="course-container">
                <div className="open-external-catalog-buttons">
                    <a target="_blank" href={`${this.props.edflex_url}`}>{`${this.props.edflex_button_name}`}</a>
                </div>
                <div>
                    <i className={`far fa-indent ${this.props.indent ? 'hidden' : ''}`} onClick={this.fireIndentClick.bind(this)}></i>
                    {firstTimeLoading ? '' : (recordCount
                        ? gettext('${recordCount} resources found').replace('${recordCount}', recordCount)
                        : gettext('We couldn\'t find any results for "${searchString}".').replace('${searchString}', searchString)
                    )}
                    <span id="discovery-courses-sort-options" className="discovery-sort-options">
                        <span>{gettext('Sort by')} |</span>
                        <span class="discovery-selected-item">{this.state.selected_name}<span class="sort_icon"/></span>
                        <div class="discovery-sort-menu">
                            {sort_items}
                        </div>
                    </span>
                </div>
                <InfiniteManuallyScroll
                    className={'courses-listing'}
                  dataLength={items.length}
                  next={this.fireNext.bind(this)}
                  hasMore={hasMore}
                >
                    {data.length<=0 && firstTimeLoading ? skeletons : items}
                </InfiniteManuallyScroll>
                <div className="show_more_button_container">
                    <h5 id="id_show_loading" style={{display: 'none'}}><i className={'far fa-spinner fa-spin'}></i><span> Loading...</span></h5>
                    <a id="id_show_more_btn" style={{display: hasMore ? 'block' : 'none'}} className="show_more_button" onClick={this.fireNext.bind(this)}>{gettext('Show more')}</a>
                </div>
            </main>
        )
    }
}
