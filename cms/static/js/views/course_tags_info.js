// Backbone Application View: Course Tags Information
define([
    'jquery',
    'underscore',
    'backbone',
    'js/utils/templates'
], function($, _, Backbone, TemplateUtils) {
    'use strict';
    var CourseTagsInfo = Backbone.View.extend({
        events: {
            'click .tag-item': 'removeTagItem'
        },

        initialize: function() {
            _.bindAll(this, 'render');
            this.template = TemplateUtils.loadTemplate('course-settings-tags-fields');
        },

        render: function() {
            var courseTags = this.model.get('vendor');
            $(this.el).empty();
            $(this.el).append(this.template({courseTags: courseTags}));
            $('#course-vendor').val('');
        },

        removeTagItem: function(event) {
            event.preventDefault();
            var courseTags = _.clone(this.model.get('vendor'));
            var pos = $(event.currentTarget).data('index');
            courseTags.splice(pos, 1);
            this.model.set('vendor', courseTags);
            this.render();
        }
    });
    return CourseTagsInfo;
});
