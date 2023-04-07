import React from "react";
import Cookies from "js-cookie";
import {CoursesSideBar} from './CrehanaCoursesSidebar'
import {CoursesContainer} from './CrehanaCoursesContainer'
import CatalogTabs from "./ExternalCatalogTabs"


export class CrehanaCatalogCourses extends React.Component {
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
                courseCategories: [],
                durations: [],
                languages: [],
                ratingRange: []
            },
            course_list: [],
            searchParameters: {},
            isFetching: false,
            hasMore: false,
            recordCount: 0,
            searchString: '',
            sort_type: '+display_name',
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
        fetch("/crehana_catalog/data", {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': Cookies.get('csrftoken'),
            },
        })
            .then(res => res.json())
            .then(
                (result) => {

                    this.setState({
                        sidebarData: this.parseSidebarData(result.sidebar_data)
                    })
                }
            )
    }

    parseSidebarData({categories, language, duration, rating_range}){
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
            fr: gettext('French'), en: gettext('English'), it: gettext('Italian'), ge: gettext('German'), es: gettext('Spanish'), pt: gettext('Portuguese')
        };
        language.forEach(function(item, index, arr) {
            if(item.value === '') {
                arr.splice(index, 1);
            }
        });
        let prev_count = 0;
        for (let i=0; i < rating_range.length; i++) {
            let raw_number = rating_range[i].count;
            if (i>0) {
                rating_range[i].count = prev_count + rating_range[i].count;
            }
            prev_count += raw_number;
        }
        const genDuration = (durationLevel) => {
            if (durationLevel == 1) {
                return '0 - 2 ' + gettext('hours');
            } else if (durationLevel == 2) {
                return '2 - 6 ' + gettext('hours');
            } else if (durationLevel == 3) {
                return '6 - 16 ' + gettext('hours');
            } else if (durationLevel == 4) {
                return '16 + ' + gettext('hours');
            } else {
                return 'unknow level';
            }
        };
        return {
            courseCategories: categories.sort(sortFn),
            durations: duration.map(p => ({text: genDuration(p.value), value: p.value, label: p.count})),
            languages: language.map(p => ({text: languageNameObj[p.value], value: p.value, label: p.count})),
            ratingRange: rating_range.map(p => ({text: p.value, value: p.value, label: p.count}))
        }
    }

    fetchData(p) {
        const {
            filterValue,
            topic,
            selectedDurations,
            selectedLanguages,
            selectedRatingRange
        } = p || this.state.searchParameters;
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
        if (selectedDurations && selectedDurations.length > 0) {
            obj.filter_content['duration'] = selectedDurations.map(p => p.value)
        }
        if (selectedLanguages && selectedLanguages.length > 0) {
            obj.filter_content['language'] = selectedLanguages.map(p => p.value)
        }
        if (selectedRatingRange && selectedRatingRange.length > 0) {
            obj.filter_content['rating_range'] = selectedRatingRange.map(p => p.value)
        }
        this.setState({isFetching: true});
        return fetch("/crehana_catalog/data", {
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
                    const {sidebar_data, course_list, course_count, search_content} = result;
                    this.setState(prev => {
                        return {
                            isFetching: false,
                            recordCount: course_count,
                            searchString: search_content,
                            hasMore: this.getHasMore(course_count),
                            sidebarData: this.parseSidebarData(sidebar_data),
                            course_list: prev.course_list.concat(course_list)
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
                    course_list: []
                });
                console.error('Error:', error);
            })
    }

    startFetch(searchParameters){
        this.setState({
            pageNo:1,
            searchParameters,
            course_list:[]
        },this.fetchData)
    }

    updateSidebarDisplayStatus(sidebarStatus) {
        this.setState({sidebarStatus}, ()=>{
            localStorage.setItem('triboo', JSON.stringify({sidebarStatus}))
        })
    }

    getHasMore(course_count) {
        const {pageSize, pageNo} = this.state;
        return ((pageSize * pageNo) < course_count)
    }

    sortPage(sort_type) {
        this.setState(
            {sort_type: sort_type, course_list: [], pageNo: 1},
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
        const {sidebarStatus, course_list, sidebarData} = this.state;
        const {external_catalogs} = this.props

        const Switcher = props => {
            return <a href="/courses"><span className="switcher"><span
                className="round-button">{gettext("Internal")}</span><span
                className="round-button active">{gettext("External")}</span></span></a>
        }

        return (

            <section className="find-courses">
                <section className="banner">
                    <section className="welcome-wrapper">
                        <h2>{gettext("Explore")}</h2>
                        <Switcher/>
                    </section>
                    <CatalogTabs external_catalogs={external_catalogs} current="CREHANA" />
                </section>
                <div className="courses-wrapper">
                    <CoursesSideBar
                        {...sidebarData}
                        status={this.state.sidebarStatus}
                        onToggle={this.updateSidebarDisplayStatus.bind(this)}
                        onApply={this.startFetch.bind(this)}
                        onChange={this.startFetch.bind(this)}
                    />
                    {/* <Switcher/> */}
                    <CoursesContainer
                        indent={sidebarStatus}
                        {..._.pick(this.state, ['hasMore', 'recordCount', 'searchString', 'firstTimeLoading'])}
                        {..._.pick(this.props, ['language', 'crehana_url', 'crehana_button_name'])}
                        onNext={this.fetchMoreData.bind(this)}
                        onChange={this.sortPage.bind(this)}
                        onIndentClick={() => this.setState({sidebarStatus: true}, () => {
                            localStorage.setItem('triboo', JSON.stringify({sidebarStatus: true}))
                        })}
                        data={course_list}
                    />
                </div>
            </section>
        )
    }
}
