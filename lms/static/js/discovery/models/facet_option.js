(function(define) {
    'use strict';
    define(['backbone'], function(Backbone) {
        return Backbone.Model.extend({
            idAttribute: 'term',
            defaults: {
                facet: '',
                term: '',
                count: 0,
                selected: false
            }
        });
    });
}(define || RequireJS.define));
