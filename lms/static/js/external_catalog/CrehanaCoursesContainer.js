import React from "react";
import InfiniteScroll from "react-infinite-scroll-component";

import {CrehanaCourseCard} from './ExternalCourseCard'


class InfiniteManuallyScroll extends InfiniteScroll {
    constructor(props) {
        super(props);
    }

    isElementAtBottom(target, scrollThreshold) {
        return false;
    }
}

export class CoursesContainer extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            selected_option: '+display_name',
            selected_name: gettext('Title A-Z').trim()
        };

        this.all_options = Array(
                ['+display_name', gettext('Title A-Z').trim()],
                ['-display_name', gettext('Title Z-A').trim()],
        );
    }

    fireIndentClick() {
        const {onIndentClick} = this.props;
        onIndentClick && onIndentClick();
    }

    fireNext(){
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
                <CrehanaCourseCard key={`id-${index}`}
                            systemLanguage={this.props.language}
                            {...course}
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
                    <a target="_blank" href={`${this.props.crehana_url}`}>{`${this.props.crehana_button_name}`}</a>
                </div>
                <div><i className={`far fa-indent ${this.props.indent ? 'hidden' : ''}`}
                      onClick={this.fireIndentClick.bind(this)}></i>{firstTimeLoading ? '' :
                    (recordCount ? gettext('${recordCount} resources found').replace('${recordCount}', recordCount) : gettext('We couldn\'t find any results for "${searchString}".').replace('${searchString}', searchString) )}
                    <span id="discovery-courses-sort-options" className="crehana-discovery-sort-options">
                        <span>{gettext('Sort by')} |</span>
                        <span className="discovery-selected-item">{this.state.selected_name}<span
                            className="sort_icon"/></span>
                        <div className="discovery-sort-menu">
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
