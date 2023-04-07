import React from "react";
import InfiniteScroll from "react-infinite-scroll-component";

import ProgramCard from "./ProgramCard"
import {CourseCard} from "../programs/CourseCard"
import {ExploreBlock} from "../my_training/explore-block";

class CoursesProgramsContainer extends React.Component {
    constructor(props) {
        super(props)
    }

    fireIndentClick() {
        const {onIndentClick} = this.props;
        onIndentClick && onIndentClick();
    }

    fireNext(){
        const {onNext}=this.props;
        onNext && onNext();
    }

    render() {
        try {
            const {programs, courses, programs_title, courses_title} = this.props;
            const programs_list = [];
            const courses_list = [];
            (typeof(programs) == 'string' ? JSON.parse(programs) : programs).forEach((program, index) => {
                (programs_list || []).push(
                    <ProgramCard key={`id-${index}`}
                        systemLanguage={this.props.language}
                                {...program}
                    />
                )
            });

            (typeof(courses) == 'string' ? JSON.parse(courses) : courses).forEach((course, index) => {
                (courses_list || []).push(
                    <CourseCard key={`id-${index}`}
                                {...course} systemLanguage={this.props.language}
                    />
                )
            });

            return (
                <main className="course-container">
                    <div className="program-list-wrapper">
                        <div className='catalog_name-wrapper'>
                            <span className={'category_name'}>{programs_title}</span>
                            <span className={'view_all_button'}>
                                <a className={'button_underline'} href="/programs/">{gettext("View all")}</a> &gt;
                            </span>
                        </div>
                        {programs_list.length <=0 && <ExploreBlock explore={false} subTitle={false} title='There are no Trainings to register for right now.' />}
                        {programs_list.length >0 && <InfiniteScroll
                            className={'container-for-program-cards'}
                            dataLength={programs_list.length}
                        >
                            {programs_list}
                        </InfiniteScroll>}
                    </div>
                    <div className="course-list-wrapper">
                        <div className='catalog_name-wrapper'>
                            <span className={'category_name'}>{courses_title}</span>
                            <span className={'view_all_button'}>
                                <a className={'button_underline'} href="/courses/">{gettext("View all")}</a> &gt;
                            </span>
                        </div>
                        {courses_list.length <=0 && <ExploreBlock explore={false} subTitle={false} title='There are no course to self registration right now' />}
                        {courses_list.length > 0 && <InfiniteScroll
                            className={'courses-listing'}
                            dataLength={courses_list.length}
                        >
                            {courses_list}
                        </InfiniteScroll>}
                    </div>
                </main>
            )
        } catch(e) {
            console.error('Error  :  ', e);
        }
    }
}

export {CoursesProgramsContainer}
