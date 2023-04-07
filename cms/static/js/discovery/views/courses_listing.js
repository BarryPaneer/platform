(function(define) {
    'use strict';
    define([
        'jquery',
        'underscore',
        'backbone',
        'gettext',
        'js/discovery/views/course_item'
    ], function($, _, Backbone, gettext, CourseItemView) {
        return Backbone.View.extend({

            el: 'div.courses',
            $window: $(window),
            $document: $(document),

            initialize: function() {
                this.$list = this.$el.find('.course-listing');
                this.attachScrollHandler();
            },

            render: function() {
                this.$list.empty();
                this.renderItems();
                return this;
            },

            renderNext: function() {
                this.renderItems();
                this.isLoading = false;
            },

            renderItems: function() {
                /* eslint no-param-reassign: [2, { "props": true }] */
                var latest = this.model.latest();
                var items = latest.map(function(result) {
                    result.userPreferences = this.model.userPreferences;
                    var item = new CourseItemView({model: result});
                    return item.render().el;
                }, this);
                this.$list.append(items);
                /* eslint no-param-reassign: [2, { "props": false }] */
            },

            attachScrollHandler: function() {
                this.$window.on('scroll', _.throttle(this.scrollHandler.bind(this), 400));
            },

            scrollHandler: function() {
                if (this.isNearBottom() && !this.isLoading) {
                    this.trigger('next');
                    this.isLoading = true;
                }
            },

            isNearBottom: function() {
                var scrollBottom = this.$window.scrollTop() + this.$window.height();
                var threshold = this.$document.height() - 200;
                return scrollBottom >= threshold;
            }
        });
    });
}(define || RequireJS.define));
