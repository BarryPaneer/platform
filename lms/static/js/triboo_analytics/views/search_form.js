(function(define) {
    define(['jquery', 'backbone', 'gettext'], function($, Backbone, gettext) {
        'use strict';

        return Backbone.View.extend({

            el: '#filter-form',
            events: {
                'keydown #id_query_string': 'submitForm',
                'click #clear-all-filters': 'clearAll',
            },

            initialize: function() {
                this.$filterQuery = this.$el.find('input');
                this.$filterButton = this.$el.find('button');
                this.$filterField = this.$el.find('#id_queried_field')
                this.$message = $('#filter-message');
                this.$loadingIndicator = this.$el.find('#loading-indicator');
            },

            submitForm: function(event) {
                if (event.which === 13) {
                    event.preventDefault();
                    this.doFilter();
                }
            },

            doFilter: function(type, term) {
                if (term !== undefined) {
                    this.$filterQuery.val(term);
                } else {
                    term = this.$filterQuery.val();
                }
                if (type !== undefined) {
                    this.$filterField.val(type);
                } else {
                    type = this.$filterField.val();
                }
                var name = this.$filterField.find("option:selected").text()
                this.trigger('filter', type, term, name);
            },

            clearFilter: function() {
                this.$filterQuery.val('');
                this.$filterField.val('user__profile__name');
            },

            clearAll: function(event) {
                event.preventDefault();
                this.trigger('clearAll');
            },

        });
    });
}(define || RequireJS.define));
