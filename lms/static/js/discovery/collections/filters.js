(function(define) {
    'use strict';
    define(['backbone', 'js/discovery/models/filter'], function(Backbone, Filter) {
        return Backbone.Collection.extend({
            model: Filter,
            getTerms: function() {
                return this.reduce(function(terms, filter) {
                    var filterType = filter.get('type');
                    var filterQuery = filter.get('query');
                    if (!terms.hasOwnProperty(filterType)) {
                        terms[filterType] = [];
                    }
                    terms[filterType].push(filterQuery);
                    return terms;
                }, {});
            }
        });
    });
}(define || RequireJS.define));
