(function(define) {
    'use strict';
    define(['backbone', 'underscore', 'js/discovery/models/search_state', 'js/discovery/collections/filters',
        'js/discovery/views/search_form', 'js/discovery/views/courses_listing',
        'js/discovery/views/filter_bar', 'js/discovery/views/refine_sidebar', 'js/discovery/views/sort_button'],
        function(Backbone, _, SearchState, Filters, SearchForm, CoursesListing, FilterBar, RefineSidebar, SortButton) {
            return function(meanings, titleMeanings, transForTags, searchQuery, userLanguage, userTimezone, showTabs=false, external_button_url="", student_enrollments_dict) {

                ReactDOM.render(
                    React.createElement(Banner, { module:'explore', switcher:!!external_button_url, showTabs:showTabs }, null),
                    document.querySelector('.banner-wrapper')
                );

                var dispatcher = _.extend({}, Backbone.Events);
                var sortButton = new SortButton();
                var search = new SearchState(sortButton);
                var filters = new Filters();
                var form = new SearchForm();
                var filterBar = new FilterBar({collection: filters});
                var refineSidebar = new RefineSidebar({
                    collection: search.discovery.facetOptions,
                    meanings: meanings,
                    titleMeanings: titleMeanings,
                    transForTags: transForTags,
                    userLanguage: userLanguage
                });
                var listing;
                var courseListingModel = search.discovery;
                courseListingModel.userPreferences = {
                    userLanguage: userLanguage,
                    userTimezone: userTimezone,
                    student_enrollments_dict: student_enrollments_dict,
                };
                listing = new CoursesListing({model: courseListingModel});
                form.on('displayStatusChange', function(){
                    listing.setSearchFormStatus()
                })
                listing.on('filterIconClick', function () {
                    form.toggleFilterBar(null);
                })

                function removeFilter(filter) {
                    form.showLoadingIndicator();
                    filters.remove(filter);
                    if (filter.startsWith('search_query')) {
                        form.doSearch('');
                    } else {
                        search.refineSearch(filters.getTerms());
                    }
                }

                function quote(string) {
                    return '"' + string + '"';
                }

                dispatcher.listenTo(sortButton, 'search', function(query) {
                    form.showLoadingIndicator();
                    search.performSearch(query, filters.getTerms());
                });

                dispatcher.listenTo(form, 'search', function(query) {
                    filters.reset();
                    form.showLoadingIndicator();
                    search.performSearch(query, filters.getTerms());
                });

                dispatcher.listenTo(refineSidebar, 'selectOption', function(type, query, name) {
                    form.showLoadingIndicator();
                    if (filters.get(type + '-' + query)) {
                        removeFilter(type + '-' + query);
                    } else {
                        filters.add({id: type + '-' + query, type: type, query: query, name: name});
                        search.refineSearch(filters.getTerms());
                    }
                });

                dispatcher.listenTo(filterBar, 'clearFilter', removeFilter);

                dispatcher.listenTo(refineSidebar, 'clearAll', function() {
                    form.doSearch('');
                });

                dispatcher.listenTo(listing, 'next', function() {
                    search.loadNextPage();
                });

                dispatcher.listenTo(search, 'next', function() {
                    listing.renderNext();
                });

                dispatcher.listenTo(search, 'search', function(query, total) {
                    if (total > 0) {
                        form.showFoundMessage(total);
                        if (query) {
                            filters.add(
                                {id: 'search_query-' + query, type: 'search_query', query: query, name: quote(query)},
                                {merge: true}
                            );
                        }
                    } else {
                        form.showNotFoundMessage(query);
                        filters.reset();
                    }
                    form.hideLoadingIndicator();
                    listing.render();
                    refineSidebar.render();
                });

                dispatcher.listenTo(search, 'error', function() {
                    form.showErrorMessage(search.errorMessage);
                    form.hideLoadingIndicator();
                });

                // kick off search on page refresh
                form.doSearch(searchQuery);
            };
        });
}(define || RequireJS.define));
