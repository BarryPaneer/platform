import React from "react";
import InfiniteScroll from "react-infinite-scroll-component";

import ProgramCard from "./ProgramCard"


class InfiniteManuallyScroll extends InfiniteScroll {
    constructor(props) {
        super(props);
    }

    isElementAtBottom(target, scrollThreshold) {
        return false;
    }
}

class ProgramsContainer extends React.Component {
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
            ['-display_name', gettext('Title Z-A').trim()]
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
                <ProgramCard key={`id-${index}`}
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
                        <a key={'id-'+index} href="#">
                            <div onClick={this.applySortType.bind(this)} className="discovery-sort-item" sort_type={option[0]}>{option[1]}</div>
                        </a>
                    );
                }
            }
        )

        return (
            <main className="course-container">
                <div className="discovery-message-wrapper">
                    <i className={`far fa-indent ${this.props.indent ? 'hidden' : ''}`}
                      onClick={this.fireIndentClick.bind(this)}></i><span id='discovery-message'>{firstTimeLoading ? '' :
                    (recordCount ? gettext('${recordCount} learning paths found').replace('${recordCount}', recordCount) : gettext('We couldn\'t find any results for "${searchString}".').replace('${searchString}', searchString) )}</span>
                    <span id="discovery-courses-sort-options" className="discovery-sort-options">
                        <span>{gettext('Sort by')} |</span>
                        <span className="discovery-selected-item">{this.state.selected_name}<span
                            className="sort_icon"/></span>
                        <div className="discovery-sort-menu">
                            {sort_items}
                        </div>
                    </span>
                </div>
                <InfiniteManuallyScroll
                    className={'container-for-program-cards'}
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

export {ProgramsContainer}
