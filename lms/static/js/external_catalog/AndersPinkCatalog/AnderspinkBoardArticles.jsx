import React, { Component } from 'react'
import InfiniteScroll from "react-infinite-scroll-component";
import Cookies from "js-cookie";
import {AnderspinkArticleCard} from '../ExternalCourseCard';

class InfiniteManuallyScroll extends InfiniteScroll {
    constructor(props) {
        super(props);
    }

    isElementAtBottom(target, scrollThreshold) {
        return false;
    }
}

class AnderspinkBoardArticles extends Component {
    constructor(props) {
        super(props)
        this.state = {
            article_list : [],
            pageSize : 20,
            pageNo : 1,
            hasMore: false,
            recordCount : 0
        }
        this.fetchBoardsArticles = this.fetchBoardsArticles.bind(this);
        this.getHasMore = this.getHasMore.bind(this);


    }

    fetchBoardsArticles (){
        const obj = {
            page_no : this.state.pageNo,
            page_size : this.state.pageSize,
            board_id : this.props.anerspink_board
        }

        fetch("/anderspink_boards/data", {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': Cookies.get('csrftoken'),
            },
            body: JSON.stringify(obj),

        })
            .then(res => res.json())
            .then(result => {
                const {article_count, article_list} = result;
                const hasMore = this.getHasMore(article_count);
                this.setState(prev => {
                    return {
                        article_list : prev.article_list.concat(article_list),
                        hasMore,
                        recordCount : article_count }})
                document.getElementById('id_show_loading').style.display = 'none';
                    if (hasMore) {
                        document.getElementById('id_show_more_btn').style.display = 'block';
                    }
            })
    }


    componentDidMount(){
        document.getElementById('id_show_loading').style.display = 'block';
        this.fetchBoardsArticles()

    }

    fireNext(){
        document.getElementById('id_show_loading').style.display = 'block';
        document.getElementById('id_show_more_btn').style.display = 'none';
        if(this.getHasMore(this.state.recordCount)){

            this.setState(() => {
                return {pageNo: this.state.pageNo + 1}
            }, this.fetchBoardsArticles)
        }
    }

    getHasMore(recordCount) {
        const {pageSize, pageNo} = this.state;
        return ((pageSize * pageNo) < recordCount)
    }


    render (){
        const {article_list, hasMore} = this.state
           return (
               <div className="find-courses">
            <div className="courses-wrapper">
            <main className="course-container">
            <InfiniteManuallyScroll
                    className={'courses-listing'}
                  dataLength={article_list.length}
                  next={this.fireNext.bind(this)}
                  hasMore={hasMore}
                >
                   {article_list.map(article => <AnderspinkArticleCard {...article} systemLanguage={this.props.language}/>)}
                </InfiniteManuallyScroll>
                <div className="show_more_button_container">
                    <h5 id="id_show_loading" style={{display: 'none'}}><i className={'far fa-spinner fa-spin'}></i><span> Loading...</span></h5>
                    <a id="id_show_more_btn" style={{display: hasMore ? 'block' : 'none'}} className="show_more_button" onClick={this.fireNext.bind(this)}>{gettext('Show more')}</a>
                </div>
            </main>
            </div></div>)}
}

export {AnderspinkBoardArticles}
