(function(define) {
    'use strict';
    define(['jquery', 'underscore', 'backbone', 'gettext'], function($, _, Backbone, gettext) {
        return Backbone.View.extend({

            el: '#discovery-form',
            events: {
                'submit form': 'submitForm'
            },

            initialize: function() {
                this.$searchField = this.$el.find('input');
                this.$searchButton = this.$el.find('button');
                this.$message = $('#discovery-message');
                this.$loadingIndicator = this.$el.find('#loading-indicator');
            },

            submitForm: function(event) {
                event.preventDefault();
                this.doSearch();
            },

            doSearch: function(term, archived) {
                if (term !== undefined) {
                    this.$searchField.val(term);
                } else {
                    term = this.$searchField.val();
                }
                this.trigger('search', $.trim(term), archived);
            },

            clearSearch: function() {
                this.$searchField.val('');
            },

            showLoadingIndicator: function() {
                this.$loadingIndicator.removeClass('hidden');
            },

            hideLoadingIndicator: function() {
                this.$loadingIndicator.addClass('hidden');
            },

            showFoundMessage: function(count) {
                var msg = ngettext(
                '%s course found',
                '%s courses found',
                count
            );
                this.$message.html('(' + interpolate(msg, [count]) + ')');
            },

            showNotFoundMessage: function(term) {
                var msg = interpolate(
                gettext('We couldn\'t find any results for "%s".'),
                [_.escape(term)]
            );
                this.$message.html(msg);
                this.clearSearch();
            },

            showErrorMessage: function(error) {
                this.$message.text(gettext(error || 'There was an error, try searching again.'));
            }

        });
    });
}(define || RequireJS.define));
