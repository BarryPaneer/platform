import React from "react";
import Cookies from "js-cookie";
import {AnderspinkSidebar} from './AnderspinkSidebar';
import {AndersPinkArticleContainer} from './AndersPinkArticleContainer'
import CatalogTabs from "../ExternalCatalogTabs"


export class AndersPinkCatalogArticles extends React.Component {
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
                briefings: [],
                reading_time: [],
                languages: [],
                ratingRange: []
            },
            article_list: [],
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

        fetch("/anderspink_catalog/data", {
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

    parseSidebarData({briefings, language, reading_time}){
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

        const genDuration = (durationLevel) => {
            if (durationLevel == 1) {
                return '0 - 3 ' + gettext('mins');
            } else if (durationLevel == 2) {
                return '3 - 5 ' + gettext('mins');
            } else if (durationLevel == 3) {
                return '5 - 8 ' + gettext('mins');
            } else if (durationLevel == 4) {
                return '8 + ' + gettext('mins');
             } else {
                return 'unknow level';
            }
        };
        return {
            briefings: briefings.sort(sortFn),
            reading_time: reading_time.map(p => ({text: genDuration(p.value), value: p.value, label: p.count})),
            languages: language.map(p => ({text: languageNameObj[p.value], value: p.value, label: p.count})),
        }
    }

    fetchData(p) {
        const {
            filterValue,
            topic,
            selectedReadingTime,
            selectedLanguages,
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
            obj.filter_content['briefing'] = topic.text
        }
        if (selectedReadingTime && selectedReadingTime.length > 0) {
            obj.filter_content['reading_time'] = selectedReadingTime.map(p => p.value)
        }
        if (selectedLanguages && selectedLanguages.length > 0) {
            obj.filter_content['language'] = selectedLanguages.map(p => p.value)
        }

        this.setState({isFetching: true});

        return fetch("/anderspink_catalog/data", {
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
                    const {sidebar_data, article_list, article_count, search_content} = result;
                    this.setState(prev => {
                        return {
                            isFetching: false,
                            recordCount: article_count,
                            searchString: search_content,
                            hasMore: this.getHasMore(article_count),
                            sidebarData: this.parseSidebarData(sidebar_data),
                            article_list: prev.article_list.concat(article_list)
                        }
                    });
                    document.getElementById('id_show_loading').style.display = 'none';
                    if (this.getHasMore(article_count) || (0 === article_count && this.state.searchString != "")) {
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
                    article_list: []
                });
                console.error('Error:', error);
            })
    }


    startFetch(searchParameters){
        this.setState({
            pageNo:1,
            searchParameters,
            article_list:[]
        },this.fetchData)
    }

    updateSidebarDisplayStatus(sidebarStatus) {
        this.setState({sidebarStatus}, ()=>{
            localStorage.setItem('triboo', JSON.stringify({sidebarStatus}))
        })
    }

    getHasMore(article_count) {
        const {pageSize, pageNo} = this.state;
        return ((pageSize * pageNo) < article_count)
    }

    sortPage(sort_type) {
        this.setState(
            {sort_type: sort_type, article_list: [], pageNo: 1},
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
        const {sidebarStatus, article_list, sidebarData} = this.state;
        const {external_catalogs} = this.props;
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
                    <CatalogTabs external_catalogs={external_catalogs} current="ANDERSPINK" />
                </section>
                <div className="courses-wrapper">
                    <AnderspinkSidebar
                        {...sidebarData}
                        status={this.state.sidebarStatus}
                        onToggle={this.updateSidebarDisplayStatus.bind(this)}
                        onApply={this.startFetch.bind(this)}
                        onChange={this.startFetch.bind(this)}
                    />
                    <AndersPinkArticleContainer
                        indent={sidebarStatus}
                        {..._.pick(this.state, ['hasMore', 'recordCount', 'searchString', 'firstTimeLoading'])}
                        {..._.pick(this.props, ['language'])}
                        onNext={this.fetchMoreData.bind(this)}
                        onChange={this.sortPage.bind(this)}
                        onIndentClick={() => this.setState({sidebarStatus: true}, () => {
                            localStorage.setItem('triboo', JSON.stringify({sidebarStatus: true}))
                        })}
                        data={article_list}
                    />
                </div>
            </section>
        )
    }
}
