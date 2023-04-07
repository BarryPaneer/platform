(function(define) {
    define(['backbone'], function(Backbone) {
        'use strict';

        return Backbone.Model.extend({
            idAttribute: 'type',
            defaults: {
                type: 'user__profile__name',
                query: '',
                name: ''
            }
        });
    });
}(define || RequireJS.define));
