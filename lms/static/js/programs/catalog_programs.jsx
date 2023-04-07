import React from "react";
import Cookies from "js-cookie";
import {ProgramsContainer} from './catalog_container.js'
import {ProgramsSideBar} from './catalog_sidebar.js'
import {formatLanguage} from '../LanguageLocale.js'
import {Banner} from '../com/banner'
import {Module} from '../com/tabs'
import {IsDebug} from '../../../../common/static/js/global_variable'
import {MockedFacetResult} from '../mock_data/course'
import {MockedProgramResult} from '../mock_data/program'

class CatalogPrograms extends React.Component {
    constructor(props) {
        super(props);
        let sidebarStatus = true;
        try {
            const triboo = localStorage.getItem('triboo');
            sidebarStatus = triboo === '' ? {} : JSON.parse(triboo).sidebarStatus;
        } catch (e) {
            localStorage.setItem('triboo', {})
        }

        this.firstTimeLoading = true;
        this.isFetching = false;
        this.state = {
            sidebarStatus,
            sidebarData:[],
            program_list: [],
            searchParameters: {},
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
        this.fetchData({}).then(()=>{
            this.firstTimeLoading = false;
        });
    }

    formatAvailability (availability_term) {
        if (availability_term == 'current') {
            return gettext('Current');
        } else if( availability_term == 'new' ) {
            return gettext('New');
        } else if( availability_term == 'soon' ) {
            return gettext('Starts soon');
        } else if( availability_term == 'future' ) {
            return gettext('Future');
        }

        return 'unknow keyword';
    }

    parseSidebarData({facets}){
        const languages = Object.keys(facets.language.terms).map(key => ({
            text: formatLanguage(key, this.props.language),
            value: key,
            label: facets.language.terms[key]
        }))

        const starts = Object.keys(facets.start.terms).map(key => ({
            text: this.formatAvailability(key),
            value: key,
            label: facets.start.terms[key]
        }))

        const vendors = Object.keys(facets.vendor.terms).map(key => ({
            text: key,
            value: key,
            label: facets.vendor.terms[key]
        }))

        return [
            {text:gettext('Language'), value:'language', items:languages},
            {text:gettext('Availability'), value:'availability', items:starts},
            {text:gettext('Tag'), value:'vendor', items:vendors}
            ]
    }

    fetchData(p) {
        const {
            filterValue,
            selectedLanguages,
        } = p || this.state.searchParameters;
        const {pageSize, pageNo, sort_type} = this.state,st=this.state,
            searchParameterKeys = Object.keys(st.searchParameters).filter(key=>!['filterValue', 'selectedLanguages'].includes(key));
        var serializedSearchParameters = searchParameterKeys.reduce((obj, key)=>{
                return {...obj, [key]:st.searchParameters[key]}
            }, {})

        const obj = {
            'search_string': filterValue || '',
            'page_size': pageSize,
            'page_no': pageNo,
            'sort_type': sort_type
        };
        if (serializedSearchParameters.hasOwnProperty('language')) {
            if (serializedSearchParameters['language'].length === 0) {
                delete obj['language'];
            } else {
                obj['language'] = serializedSearchParameters['language'].map(lang => lang.value);
            }
        }
        if (serializedSearchParameters.hasOwnProperty('availability')) {
            if (serializedSearchParameters['availability'].length === 0) {
                delete obj['start'];
            } else {
                obj['start'] = serializedSearchParameters['availability'].map(lang => lang.value);
            }
        }
        if (serializedSearchParameters.hasOwnProperty('vendor')) {
            if (serializedSearchParameters['vendor'].length === 0) {
                delete obj['vendor'];
            } else {
                obj['vendor'] = serializedSearchParameters['vendor'].map(lang => lang.value);
            }
        }
        const formData = new FormData()
        Object.keys(obj).forEach(key => {
            formData.append(key, obj[key])
        })
        this.isFetching=true
        return fetch("/search/program_discovery/", {
            method: 'POST',
            headers: {
                'X-CSRFToken': Cookies.get('csrftoken'),
            },
            body: formData,
        })
            .then(res => res.json())
            .then(
                (result) => {
                    const {total, results, facets} = result;

                    var programs_array = [];
                    for (var i in results) {
                        if (results[i].data.released_date !== null) {
                            programs_array.push(results[i]['data']);
                        }
                    }
                    this.isFetching = false;
                    this.setState(prev => {
                        return {
                            recordCount: total,
                            hasMore: this.getHasMore(total),
                            sidebarData: this.parseSidebarData(result),
                            program_list: prev.program_list.concat(programs_array)
                        }
                    });
                    document.getElementById('id_show_loading').style.display = 'none';
                    if (this.getHasMore(total) || (0 === total && this.state.searchString != "")) {
                        document.getElementById('id_show_more_btn').style.display = 'block';
                    }
                },
            )
            .catch(error => {
                this.setState({
                    recordCount: 0,
                    searchString: '',
                    hasMore: false,
                    program_list: []
                });
                console.error('Error:', error);
            })
    }

    startFetch(searchParameters=this.state.searchParameters){
        this.setState({
            pageNo:1,
            searchParameters,
            program_list:[]
        }, this.fetchData)
    }

    updateSidebarDisplayStatus(sidebarStatus) {
        this.setState({sidebarStatus}, ()=>{
            localStorage.setItem('triboo', JSON.stringify({sidebarStatus}))
        })
    }

    resetSearchParamaters() {
        let sidebarStatus = true;
        try {
            const triboo = localStorage.getItem('triboo');
            sidebarStatus = triboo === '' ? {} : JSON.parse(triboo).sidebarStatus;
        } catch (e) {
            localStorage.setItem('triboo', {})
        }

        this.setState({
            sidebarStatus,
            sidebarData:[],
            program_list: [],
            searchParameters: {},
            hasMore: false,
            recordCount: 0,
            searchString: '',
            sort_type: '+display_name',
            pageSize: 60,
            pageNo: 1
        });
    }

    getHasMore(course_count) {
        const {pageSize, pageNo} = this.state;
        return ((pageSize * pageNo) < course_count)
    }

    sortPage(sort_type) {
        this.setState(
            {sort_type: sort_type, program_list: [], pageNo: 1},
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
            && !this.isFetching
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
        const {sidebarStatus, program_list, sidebarData} = this.state;

        return (
            <section className="find-courses">
                <Banner module={Module.explore} showTabs={this.props.is_program_enabled} switcher={this.props.external_button_url}/>
                <div className="courses-wrapper">
                    <ProgramsSideBar
                        {...sidebarData}
                        data={IsDebug?MockedFacetResult.results:sidebarData}
                        status={this.state.sidebarStatus}
                        onToggle={this.updateSidebarDisplayStatus.bind(this)}
                        onApply={this.startFetch.bind(this)}
                        onChange={this.startFetch.bind(this)}
                        resetSearchParams={this.resetSearchParamaters.bind(this)}
                    />
                    <ProgramsContainer
                        indent={sidebarStatus} searchString={this.state.searchParameters.filterValue || ''} firstTimeLoading={this.firstTimeLoading}
                        {..._.pick(this.state, ['hasMore', 'recordCount'])}
                        {..._.pick(this.props, ['language'])}
                        onNext={this.fetchMoreData.bind(this)}
                        onChange={this.sortPage.bind(this)}
                        onIndentClick={() => this.updateSidebarDisplayStatus(true)}
                        language={this.props.language}
                        data={IsDebug?MockedProgramResult.results:program_list}
                    />
                </div>
            </section>
        )
    }
}

export {CatalogPrograms};
