(function(define) {
    'use strict';
    define([
        'underscore',
        'backbone',
        'js/discovery/models/course_item',
        'js/discovery/models/facet_option'
    ], function(_, Backbone, CourseItem, FacetOption) {
        return Backbone.Model.extend({
            url: '/course_search/',
            jqhxr: null,

            defaults: {
                totalCount: 0,
                latestCount: 0
            },

            initialize: function() {
                this.courseItems = new Backbone.Collection([], {model: CourseItem});
                this.courseItems.comparator = function(item) {
                    return (item.get('content').display_name || '').toLowerCase();
                };
                this.facetOptions = new Backbone.Collection([], {model: FacetOption});
                const self = this;
                $.ajax({
                    url: '/course_search/',
                    method: 'POST',
                    data: {search_string: '', page_index: '0', page_size: '1500'},
                    async: false
                }).done(function(data) {
                    self.country_facets = data.facets.course_country;
                    self.vendor_facets = data.facets.vendor;
                    self.group_facets = data.facets.enrollment_learning_groups;
                });
            },

            parse: function(response) {
                var courses = response.results || [];
                var facets = response.facets || {};
                if (this.country_facets) {
                    facets.course_country = this.country_facets
                }
                if (this.vendor_facets) {
                    facets.vendor = this.vendor_facets
                }
                if (this.group_facets) {
                    facets.enrollment_learning_groups = this.group_facets
                }

                var options = this.facetOptions;
                this.courseItems.add(_.pluck(courses, 'data'));

                this.set({
                    totalCount: response.total,
                    latestCount: courses.length
                });

                _(facets).each(function(obj, key) {
                    _(obj.terms).each(function(count, term) {
                        if (count > 0) {
                            options.add({
                                facet: key,
                                term: term,
                                count: count
                            }, {merge: true});
                        }
                    });
                });
            },

            reset: function() {
                this.set({
                    totalCount: 0,
                    latestCount: 0
                });
                this.courseItems.reset();
                this.facetOptions.reset();
            },

            latest: function() {
                return this.courseItems.last(this.get('latestCount'));
            }

        });
    });
}(define || RequireJS.define));
