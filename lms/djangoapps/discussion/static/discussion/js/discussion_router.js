(function(define) {
    'use strict';

    define(
        [
            'underscore',
            'backbone',
            'common/js/discussion/utils',
            'common/js/discussion/views/discussion_thread_view'
        ],
        function(_, Backbone, DiscussionUtil, DiscussionThreadView) {
            var DiscussionRouter = Backbone.Router.extend({
                routes: {
                    '': 'allThreads',
                    ':forum_name/threads/:thread_id': 'showThread'
                },

                initialize: function(options) {
                    Backbone.Router.prototype.initialize.call(this);
                    _.bindAll(this, 'allThreads', 'showThread');
                    this.rootUrl = options.rootUrl;
                    this.discussion = options.discussion;
                    this.courseSettings = options.courseSettings;
                    this.discussionBoardView = options.discussionBoardView;
                    if (options.startHeader !== undefined) {
                        this.startHeader = options.startHeader;
                    } else {
                        this.startHeader = 2; // Start the header levels at H<startHeader>
                    }
                },

                start: function() {

                    // Automatically navigate when the user selects threads
                    this.discussionBoardView.discussionThreadListView.on(
                        'thread:selected', _.bind(this.navigateToThread, this)
                    );
                    this.discussionBoardView.discussionThreadListView.on(
                        'thread:removed', _.bind(this.navigateToAllThreads, this)
                    );
                    this.discussionBoardView.discussionThreadListView.on(
                        'thread:created', _.bind(this.navigateToThread, this)
                    );

                    Backbone.history.start({
                        pushState: true,
                        root: this.rootUrl
                    });
                },

                stop: function() {
                    Backbone.history.stop();
                },

                allThreads: function() {
                    $('.new-post-btn').show().siblings().hide();
                    this.discussionBoardView.discussionThreadListView.$el.show();
                    $('.forum-content').show();

                    if (this.main) {
                        this.main.cleanup();
                        this.main.undelegateEvents();
                        this.main.$el.remove();
                        this.main = null;
                    }
                    return this.discussionBoardView.goHome();
                },

                showThread: function(forumName, threadId) {
                    $('.back-thread-list').show().siblings().hide();
                    this.discussionBoardView.discussionThreadListView.$el.hide();
                    $('.forum-content').hide();
                    $('.forum-search').hide();

                    this.thread = this.discussion.get(threadId);
                    this.thread.set('unread_comments_count', 0);
                    this.thread.set('read', true);
                    return this.showMain();
                },

                showMain: function() {
                    var self = this;
                    if (this.main) {
                        this.main.cleanup();
                        this.main.undelegateEvents();
                        $('.discussion-body').remove(this.main.$el)
                    }
                    this.main = new DiscussionThreadView({
                        model: this.thread,
                        mode: 'tab',
                        startHeader: this.startHeader,
                        courseSettings: this.courseSettings,
                        is_commentable_divided: this.discussion.is_commentable_divided
                    });
                    $('.discussion-body').append(this.main.$el)
                    this.main.render();
                    return this.thread.on('thread:thread_type_updated', this.showMain);
                },

                navigateToThread: function(threadId) {
                    var thread = this.discussion.get(threadId);
                    return this.navigate('' + (thread.get('commentable_id')) + '/threads/' + threadId, {
                        trigger: true
                    });
                },

                navigateToAllThreads: function() {
                    return this.navigate('', {
                        trigger: true
                    });
                }

            });

            return DiscussionRouter;
        });
}).call(this, define || RequireJS.define);
