(function(define) {
    'use strict';

    define(
        [
            'jquery',
            'underscore',
            'backbone',
            'js/views/message_banner',
            'course_bookmarks/js/collections/bookmarks',
            'course_bookmarks/js/views/bookmarks_list',
            'course_bookmarks/js/views/bookmarks_list_button'
        ],
        function($, _, Backbone, MessageBannerView, BookmarksCollection, BookmarksListView, BookmarksListButton) {
            return function(options) {
                var courseId = options.courseId,
                    bookmarksApiUrl = options.bookmarksApiUrl,
                    bookmarksCollection = new BookmarksCollection([],
                        {
                            course_id: courseId,
                            url: bookmarksApiUrl
                        }
                    ),
                    bookmarksListButton = new BookmarksListButton();                    ;
                var bookmarksView = new BookmarksListView(
                    {
                        $el: options.$el,
                        collection: bookmarksCollection,
                        loadingMessageView: new MessageBannerView({el: $('#loading-message')}),
                        errorMessageView: new MessageBannerView({el: $('#error-message')})
                    }
                );

                var dispatcher = _.clone(Backbone.Events);

                dispatcher.listenTo(bookmarksListButton, 'bookmarks', function() {
                    bookmarksView.render();
                    bookmarksView.showBookmarks();
                });
            };
        }
    );
}).call(this, define || RequireJS.define);
