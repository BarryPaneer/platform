(function(define) {
    'use strict';
    define(['jquery', 'underscore', 'backbone', 'gettext'], function($, _, Backbone, gettext) {
        return Backbone.View.extend({
            template_id: '#sort_button-tpl',
            el: '#discovery-courses-sort-options',
            selected_option: '-start_date',
            selected_name: gettext('Most Recent').trim(),
            all_options: [
                ['-start_date', gettext('Most Recent').trim()],
                ['+start_date', gettext('Oldest').trim()],
                ['+display_name', gettext('Title A-Z').trim()],
                ['-display_name', gettext('Title Z-A').trim()],
            ],
            events: {
                'click .discovery-sort-item': 'sortCourses',
            },

            initialize: function() {
                this.tpl = _.template($(this.template_id).html());
                this.render();
            },

            sortCourses: function(event) {
                let el = $(event.currentTarget);
                this.selected_name = el.text();
                this.selected_option = el.attr("sort_type");
                this.trigger('search', '');
                this.render();
            },

            getSortType: function() {
                return {sort_type: this.selected_option};
            },

            getOptionsMenu: function() {
                let other_options = [];

                for(var i = 0, len = this.all_options.length; i < len; i++){
                    if (this.all_options[i][0] != this.selected_option) {
                        other_options.push(this.all_options[i]);
                    }
                }

                return {
                    'title': gettext('Sort by'),
                    'selected_item': this.selected_name,
                    'other_options': other_options,
                };
            },

            render: function() {
                this.$el.html(this.tpl(this.getOptionsMenu()));
            },

        });
    });
}(define || RequireJS.define));
