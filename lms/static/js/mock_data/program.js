const MockedProgramResult = {
    facets: {
        "language":
            {
                "total": 0,
                "terms": {},
                "other": 0
            }
    },
    total: 4,
    max_score: 1.0,
    took: 106,
    results:[
        {
            uuid: 'a01', title: 'Supply Chain',
            language: 'French', courses_count: 3, duration: 9,
            card_image_url: '/static/js/mock_data/images/program_cards/a1.png', systemLanguage: '',
            finishedCourseNum:3, allCourseNum:15,
            // for program about page
            // duration|program_duration, uuid|program_uuid,
            enrollment_status:'unenrolled', // enrolled|unenrolled
            language_code:'en',program_duration:1770,
            enrollment_start:'2020-8-3', enrollment_end:'2020-11-20',
            description:'<p>test.............3dafasdfasfaf</p> <p><audio style="display: none;" controls="controls"></audio></p>' +
                '<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Elementum nisi aliquet volutpat pellentesque volutpat est. Sapien in etiam vitae nibh nunc mattis imperdiet sed nullam.</p> ' +
                '<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Elementum nisi aliquet volutpat pellentesque volutpat est. Sapien in etiam vitae nibh nunc mattis imperdiet sed nullam.</p> ' +
                '<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Elementum nisi aliquet volutpat pellentesque volutpat est. Sapien in etiam vitae nibh nunc mattis imperdiet sed nullam.</p> ',
            //description:'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Elementum nisi aliquet volutpat pellentesque volutpat est. Sapien in etiam vitae nibh nunc mattis imperdiet sed nullam. ',
            program_courses_completed:1, program_courses_total:3,
            courses:[{
                course_id:'a1', badges:8, duration:undefined, start:'2021-11-27 17:53:11',
                status:'enrolled', // not_start|enrolled|completed  !
                is_course_ended:false,
                course_img:'/static/triboo-theme/images/programs/course0.jpg',
                course_about_url:'ttt.html',
                course_subtitle:'What level of hiker are you? A very long extend test with comma, A very long extend test with peroid. A very long extend test with comma, A very long extend test with comma, end',
                /*course_detail_description:'<p>test.............3dafasdfasfaf</p> <p><audio style="display: none;" controls="controls"></audio></p>'*/
                course_detail_description:'<p>test.............3dafasdfasfaf</p> CADM CV203: Produce dimensioned introductory level drawings using a computer assisted drafting program (AutoCAD).\n' +
                    '\n' +
                    'ACCT CB340: Prepare and analyze financial information of a business to develop sound managerial decisions relating to Corporate Finance, including the valuation of securities, working capital management, and short term financing\n' +
                    '\n' +
                    'SSCI SS299: Examine a wide variety of technologies that have influenced our society significantly. Analyze the contribution these technologies make to society, associated ethical dilemmas, and critique their value to the individual and society.\n' +
                    '\n' +
                    'Initially, course descriptions are written when a new program is being developed  or when developing a new course.\n' +
                    '\n' +
                    'Course descriptions can also be changed during the POS Renewal Cycle, which is managed by the Academic Data Office. For questions about this process, please contact'
            },{
                course_id:'a2', badges:8, duration:3500, start:'2021-11-27 17:53:11',
                status:'not_start', // not_start|enrolled|completed  !
                is_course_ended:false,
                course_img:'/static/triboo-theme/images/programs/course1.jpg',
                course_about_url:'',
                course_subtitle:'Picking the right Hiking Gear! Title_wiout_breakdown_Title_wiout_breakdown_Title_wiout_breakdown_Title_wiout_breakdown_Title_wiout_breakdown_Title_wiout_breakdown_Title_wiout_breakdown_Title_wiout_breakdown_',
                course_detail_description:'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Elementum nisi aliquet volutpat pellentesque volutpat est. Sapien in etiam vitae nibh nunc mattis imperdiet sed nullam. Vitae et, tortor pulvinar risus pulvinar sit amet.'
            },{
                course_id:'a3', badges:8, duration:2200, start:'2021-11-27 17:53:11',
                status:'not_start', // not_start|enrolled|completed  !
                is_course_ended:false,
                course_img:'/static/triboo-theme/images/programs/course2.jpg',
                course_about_url:'',
                course_subtitle:'Understand Your Map & Timing',
                course_detail_description:'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Elementum nisi aliquet volutpat pellentesque volutpat est. Sapien in etiam vitae nibh nunc mattis imperdiet sed nullam. Vitae et, tortor pulvinar risus pulvinar sit amet.'
            }]
        },
        {
            uuid: 'a02',
            title: 'The basics of customer relationship management2 plus a very long long and longer title, to see what it looks',
            language: 'English',
            courses_count: 3,
            duration: 190,
            card_image_url: '/static/js/mock_data/images/program_cards/a2.png',
            systemLanguage: '', finishedCourseNum:8, allCourseNum:12
        },
        {
            uuid: 'a03', title: 'The_basics_of_customer_relationship_management3_this_title_has_underscore_with_it',
            language: 'English', courses_count: 3, duration: 9,
            card_image_url: '/static/js/mock_data/images/program_cards/a3.png', systemLanguage: ''
        },
        {
            uuid: 'a04', title: 'The basics of customer relationship management4',
            language: 'English', courses_count: 3, duration: 14750,
            card_image_url: '/static/js/mock_data/images/program_cards/a4.png', systemLanguage: ''
        }
    ]
}

const MockedCourseResult = {
    results:[
        {
            course_id: 'a1', title: 'Global Security Awareness',
            image_url: '/static/js/mock_data/images/course_card/course.jpeg',
            progress: 7, //how many percent of this course has finished, e.g 98, nearly finished
            start: 'Started', end: new Date('2021/12/3'),
            language: 'en', badge: 8, duration: 10,
            tags: [ // tag_id: added at Aug 2, 2021 11:30
                {tag_id:1, text: 'Online'},
                {tag_id:2, text: 'mooc'}]
        },
        {
            course_id: 'a2', title: 'Coach_Development_Maximising_Potential_title_with_under_score_and_very_long',
            image_url: '/static/js/mock_data/images/course_card/meeting.jpeg', progress: 15,
            start: new Date('2012/12/28'), end: new Date('2021/12/3'),
            language: 'fr', badge: 12, duration: 30, tags: [{text: 'Online'}, {text: 'mook'}]
        },
        {
            course_id: 'a3', title: 'The key stages of the sales process',
            image_url: '/static/js/mock_data/images/course_card/welcome.png', progress: 21,
            start: new Date('2020/6/29'), end: new Date('2021/11/28'),
            language: 'en', badge: 18, duration: 188, tags: [{text: 'ILT'}]
        },
        {
            course_id: 'a4', title: 'The key stages of the sales process1',
            image_url: '/static/js/mock_data/images/course_card/welcome.png', progress: 21,
            start: new Date('2020/6/29'), end: new Date('2021/11/28'),
            language: 'en', badge: 18, duration: 188, tags: [{text: 'ILT'}]
        },
        {
            course_id: 'a5', title: 'The key stages of the sales process2',
            image_url: '/static/js/mock_data/images/course_card/welcome.png', progress: 21,
            start: new Date('2020/6/29'), end: new Date('2021/11/28'),
            language: 'en', badge: 18, duration: 188, tags: [{text: 'ILT'}]
        },

    ]
}

export {MockedProgramResult, MockedCourseResult}
