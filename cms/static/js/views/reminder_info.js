// Backbone Application View: Course Reminder Information

define([ // jshint ignore:line
    'jquery',
    'underscore',
    'backbone',
    'gettext',
    'js/utils/templates'
],
function ($, _, Backbone, gettext, TemplateUtils) {
    'use strict';
    var ReminderInfoView = Backbone.View.extend({

        events: {
            'click .delete-course-reminder-info': "removeReminderInfo"
        },

        initialize: function() {
            // Set up the initial state of the attributes set for this model instance
            _.bindAll(this, 'render');
            this.template = this.loadTemplate('course-reminder-details-fields');
            this.listenTo(this.model, 'change:reminder_info', this.render);
        },

        loadTemplate: function(name) {
            // Retrieve the corresponding template for this model
            return TemplateUtils.loadTemplate(name);
        },

        render: function() {
             // rendering for this model
            $("li.course-reminder-details-fields").empty();
            var self = this;
            var reminder_information = this.model.get('reminder_info');
            $.each(reminder_information, function( index, info ) {
                $(self.el).append(self.template({index: index, info: info, info_count: reminder_information.length }));
            });
        },

        removeReminderInfo: function(event) {
            /*
            * Remove course Reminder fields.
            * */
            event.preventDefault();
            var index = event.currentTarget.getAttribute('data-index'),
                existing_info = _.clone(this.model.get('reminder_info'));
            existing_info.splice(index, 1);
            this.model.set('reminder_info', existing_info);
        }

    });
    return ReminderInfoView;
});
