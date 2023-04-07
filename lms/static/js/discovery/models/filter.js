(function(define) {
    'use strict';
    define(['backbone'], function(Backbone) {
        return Backbone.Model.extend({
            idAttribute: 'id',
            defaults: {
                id: 'search_query-',
                type: 'search_query',
                query: '',
                name: ''
            }
        });
    });
}(define || RequireJS.define));
