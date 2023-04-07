(function(define) {
    'use strict';

    define(['backbone'], function(Backbone) {
        return Backbone.View.extend({
            el: '.courseware-bookmarks-button',
            events: {
                'click .bookmarks-list-button': 'listBookmarks'
            },
            listBookmarks: function(query) {
                this.trigger('bookmarks');
            }
        });
    });
}(define || RequireJS.define));
