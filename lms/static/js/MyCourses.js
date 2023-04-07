import ReactDOM from "react-dom";
import React from "react";
import {Banner} from './com/banner'
import {ExploreBlock} from './my_training/explore-block'


const MyCourses = function (options) {
    const {tab, is_program_enabled}=options
    function updateCourseList(activeTab) {
        const $listing = $('.listing-courses')
        var $courses = $(".listing-courses li.course-item");
        var activeStatus = activeTab;
        if (activeTab == 'not-started') {
            activeStatus = 'Not_started';
        } else if (activeTab == 'started') {
            activeStatus = 'Started';
        } else if (activeTab == 'finished') {
            activeStatus = 'Finished';
        }
        $courses.each(function () {
            if (activeStatus == 'all-courses' || $(this).data('status') == activeStatus) {
                $(this).show();
            } else {
                $(this).hide();
            }
        })

        if (Array.from($courses).every(p=>$(p).css('display')=='none')) {
            $('.empty-tab-message').removeClass('hidden')
            $listing.addClass('hidden')
        }else {
            $('.empty-tab-message').addClass('hidden')
            $listing.removeClass('hidden')
        }
    }


    $(".my-courses-nav li").click(function () {
        $(this).find('.btn-link').addClass('active-section');
        $(this).siblings().find('.btn-link').removeClass('active-section');
        updateCourseList($(this).attr('id'));
        const $courses = $('.my-courses article.course')
        $courses.addClass('skeleton')
        setTimeout(()=>{
            $courses.removeClass('skeleton')
        },500)
    });

    $('document').ready(function () {
        ReactDOM.render(
            React.createElement(Banner, { module:'myTraining', showTabs: is_program_enabled }),
            document.querySelector('.banner-wrapper')
        );

        const {COURSES_ARE_BROWSABLE, CATALOG_DENIED_GROUP_not_in_all}=options
        const explore = !!(COURSES_ARE_BROWSABLE && CATALOG_DENIED_GROUP_not_in_all)

        if (document.querySelector('.empty-message-wrapper') != null) {
            ReactDOM.render(React.createElement(ExploreBlock, {
                explore,
                url: '/courses/',
                subTitle: explore && gettext('No Courses'),
                title: gettext('You are not enrolled in any courses yet.')
            }), document.querySelector('.empty-message-wrapper'));
        }

        ReactDOM.render(React.createElement(ExploreBlock, {
            explore: false,
            subTitle: false,
            title: gettext('There are no courses to display yet.')
        }), document.querySelector('.empty-tab-message'));

        updateCourseList(tab);
        setTimeout(()=>{
            $('.my-courses article.skeleton').removeClass('skeleton')
        }, 500)

    });
}

export {MyCourses};
