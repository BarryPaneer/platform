define([
    'jquery', 'js/views/settings/grading', 'js/models/settings/course_grading_policy'
], function($, GradingView, CourseGradingPolicyModel) {
    'use strict';
    return function(courseDetails, gradingUrl, asset_callback_url, assignment_threshold) {
        var model, editor;

        $('form :input')
            .focus(function() {
                $('label[for="' + this.id + '"]').addClass('is-focused');
            })
            .blur(function() {
                $('label').removeClass('is-focused');
            });

        model = new CourseGradingPolicyModel(courseDetails, {parse: true});
        model.urlRoot = gradingUrl;
        editor = new GradingView({
            asset_callback_url:asset_callback_url,
            assignment_threshold,
            el: $('.settings-grading'),
            model: model
        });
        editor.render();
    };
});
