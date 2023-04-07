(function(define) {
    define([
        'jquery',
        'underscore',
        'backbone',
        'gettext',
        'js/triboo_analytics/models/filter',
        'js/triboo_analytics/views/filter_label'
    ], function($, _, Backbone, gettext, Filter, FilterLabel) {
        'use strict';

        return Backbone.View.extend({

            el: '#filter-bar',
            templateId: '#filter_bar-tpl',

            events: {
                'click #clear-all-filters': 'clearAll',
                'click li .filter-button': 'clearFilter'
            },

            initialize: function() {
                this.tpl = _.template($(this.templateId).html());
                this.render();
                this.listenTo(this.collection, 'remove', this.hideIfEmpty);
                this.listenTo(this.collection, 'add', this.addFilter);
                this.listenTo(this.collection, 'reset', this.resetFilters);
            },

            render: function() {
                this.$el.html(this.tpl());
                this.$ul = this.$el.find('ul');
                this.$el.addClass('is-animated');
                return this;
            },

            addFilter: function(filter) {
                var label = new FilterLabel({model: filter});
                this.$ul.append(label.render().el);
            },

            resetFilters: function() {
                this.$ul.empty();
            },

            clearFilter: function(event) {
                event.preventDefault();
                var $target = $(event.currentTarget);
                var filter = this.collection.get($target.data('type'));
                this.trigger('clearFilter', filter.id);
            },

            clearAll: function(event) {
                this.trigger('clearAll');
            },

        });
    });
}(define || RequireJS.define));
