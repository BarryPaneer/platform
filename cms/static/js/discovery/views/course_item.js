(function(define) {
    'use strict';
    define([
        'jquery',
        'underscore',
        'backbone',
        'gettext'
    ], function($, _, Backbone, gettext) {
        return Backbone.View.extend({

            tagName: 'li',
            templateId: '#course_item-tpl',
            className: 'course-item',

            initialize: function() {
                this.tpl = _.template($(this.templateId).html());
            },

            render: function() {
                var data = _.clone(this.model.attributes);
                if (data.archived) {
                    data.idBase = 'archived';
                } else {
                    data.idBase = 'course';
                }
                this.$el.html(this.tpl(data));
                return this;
            }
        });
    });
}(define || RequireJS.define));
