(function(define) {
    'use strict';
    define([
        'underscore',
        'backbone',
        'js/discovery/models/course_card',
        'js/discovery/models/facet_option'
    ], function(_, Backbone, CourseCard, FacetOption) {
        return Backbone.Model.extend({
            url: '/search/course_discovery/',
            jqhxr: null,

            defaults: {
                totalCount: 0,
                latestCount: 0
            },

            initialize: function() {
                this.courseCards = new Backbone.Collection([], {model: CourseCard});
                this.facetOptions = new Backbone.Collection([], {model: FacetOption});
                const self = this;
                $.ajax({
                    url: '/search/course_discovery/',
                    method: 'POST',
                    data: {search_string: '', page_index: '0', page_size: '300'},
                    async: false
                }).done(function(data) {
                    self.vendor_facets = data.facets.vendor;
                });
            },

            parse: function(response) {
                var courses = response.results || [];
                var facets = response.facets || {};
                if (this.vendor_facets) {
                    facets.vendor = this.vendor_facets
                }

                var options = this.facetOptions;
                this.courseCards.add(_.pluck(courses, 'data'));

                this.set({
                    totalCount: response.total,
                    latestCount: courses.length
                });

                _(facets).each(function(obj, key) {
                    _(obj.terms).each(function(count, term) {
                        options.add({
                            facet: key,
                            term: term,
                            count: count
                        }, {merge: true});
                    });
                });
            },

            reset: function() {
                this.set({
                    totalCount: 0,
                    latestCount: 0
                });
                this.courseCards.reset();
                this.facetOptions.reset();
            },

            latest: function() {
                return this.courseCards.last(this.get('latestCount'));
            }

        });
    });
}(define || RequireJS.define));
