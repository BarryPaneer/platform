define([
    'jquery', 'js/models/settings/course_details', 'js/views/settings/main'
], function($, CourseDetailsModel, MainView) {
    'use strict';
    return function(usedByPrivate, usedByNonPrivate, detailsUrl, showMinGradeWarning, showCertificateAvailableDate, langCode, exportUrl, homepageUrl) {
        var model;
        // highlighting labels when fields are focused in
        $('form :input')
            .focus(function() {
                $('label[for="' + this.id + '"]').addClass('is-focused');
            })
            .blur(function() {
                $('label').removeClass('is-focused');
            });

        model = new CourseDetailsModel();
        model.urlRoot = detailsUrl;
        model.showCertificateAvailableDate = showCertificateAvailableDate;
        model.fetch({
            success: function(model) {
                var editor = new MainView({
                    el: $('.settings-details'),
                    model: model,
                    showMinGradeWarning: showMinGradeWarning,
                    langCode: langCode,
                    exportUrl: exportUrl,
                    homepageUrl: homepageUrl,
                    usedByPrivate: usedByPrivate,
                    usedByNonPrivate: usedByNonPrivate
                });
                editor.render();
            },
            reset: true
        });
    };
});
