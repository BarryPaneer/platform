(function(define) {
    'use strict';

    define(['backbone', 'js/triboo_analytics/collections/filters',
        'js/triboo_analytics/views/search_form', 'js/triboo_analytics/views/filter_bar'],
        function(Backbone, Filters, SearchForm, FilterBar) {
            return function(searchQuery) {
                var dispatcher = _.extend({}, Backbone.Events);
                var filters = new Filters();
                var form = new SearchForm();
                var filterBar = new FilterBar({collection: filters});

                dispatcher.listenTo(form, 'filter', function(type, query, name) {
                    var targetQuery = {
                        type: type,
                        query: query,
                        name: name + ': ' + query
                    }
                    if (query) {
                        filters.remove(targetQuery);
                        filters.add(targetQuery);
                        form.clearFilter();
                    } else {
                        filters.remove(targetQuery);
                        form.clearFilter();
                    }

                });

                dispatcher.listenTo(filterBar, 'clearFilter', function(type) {
                    filters.remove(type);
                });

                dispatcher.listenTo(form, 'clearAll', function() {
                    filterBar.resetFilters();
                    form.clearFilter();
                });
            };
        });
}(define || RequireJS.define));
