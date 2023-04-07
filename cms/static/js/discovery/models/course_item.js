(function(define) {
    'use strict';
    define(['backbone'], function(Backbone) {
        return Backbone.Model.extend({
            defaults: {
                modes: [],
                course: '',
                enrollment_start: '',
                content: {
                    overview: '',
                    display_name: '',
                    number: ''
                },
                start: '',
                end: '',
                org: '',
                id: '',
                run: '',
                url: '',
                rerun_link: '',
                allowReruns: '',
                lms_link: '',
                archived: false
            }
        });
    });
}(define || RequireJS.define));
