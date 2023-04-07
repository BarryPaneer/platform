(function(define) {
    'use strict';
    define([
        'jquery',
        'underscore',
        'backbone',
        'gettext',
        'js/discovery/views/course_card'
    ], function($, _, Backbone, gettext, CourseCardView) {
        return Backbone.View.extend({

            el: 'div.courses',
            events: {
                //'click #filter-bar-show-button': 'toggleFilterBar',
                'click .discovery-message-wrapper i': 'forwardFilterIconStatus',
            },

            $window: $(window),
            $document: $(document),

            initialize: function() {
                this.$list = this.$el.find('.courses-listing');
                this.attachScrollHandler();
                this.loadSkeletons()
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

            loadSkeletons: function() {
                var items = [0, 1,2,3,4,5,6].map(function(index) {
                    var m0 = {attributes:{duration:'', badges:'', org:'', course_category:'', non_started: '', non_started_string: '', course_mandatory_enabled:'', language:'', image_url:'', course:'',content:{}}}
                    var item = new CourseCardView({model: m0})
                    var el = item.render().el;
                    $(el).find('.course').addClass('skeleton')
                    return el;
                }, this);
                this.$list.append(items);
            },

            renderItems: function() {
                /* eslint no-param-reassign: [2, { "props": true }] */
                var latest = this.model.latest();
                var items = latest.map(function(result) {
                    result.userPreferences = this.model.userPreferences;
                    var item = new CourseCardView({model: result});
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
            },

            switchStatus: function (e, status) {
                if (e.hasClass(status)) {
                    e.removeClass(status)
                } else {
                    e.addClass(status)
                }
            },

            toggleFilterBar: function (e) {
                var self = this;
                setTimeout(function () {
                    const $wrapper = $('.search-form');
                    const $hideButton = $('#filter-bar-hide-button');
                    const $showButton = $('#filter-bar-show-button');
                    self.switchStatus($wrapper, 'hidden');
                    self.switchStatus($hideButton, 'hidden');
                    self.switchStatus($showButton, 'hidden');
                }, 50)
            },
            setSearchFormStatus:function(visible){
                this.$el.toggleClass('search-form-hidden');
            },
            forwardFilterIconStatus: function(){
                this.trigger('filterIconClick')
            }


        });
    });
}(define || RequireJS.define));
