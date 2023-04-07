define(['js/views/baseview', 'jquery', 'underscore', 'js/views/edit_textbook', 'js/views/show_textbook', 'common/js/components/utils/view_utils'],
        function(BaseView, $, _, EditTextbookView, ShowTextbookView, ViewUtils) {
            var ListTextbooks = BaseView.extend({
                initialize: function() {
                    this.emptyTemplate = this.loadTemplate('no-textbooks');
                    this.listenTo(this.collection, 'all', this.render);
                    this.listenTo(this.collection, 'destroy', this.handleDestroy);
                    this.template = _.template($('#list-textbook-tpl').text());
                },
                tagName: 'div',
                className: 'textbooks-list',
                render: function() {
                    this.$el.html(this.template());
                    this.$body = this.$el.find('.body')

                    var textbooks = this.collection;
                    if (textbooks.length === 0) {
                        this.$el.html(this.emptyTemplate());
                    } else {
                        this.$body.empty();
                        var that = this;
                        textbooks.each(function(textbook) {
                            var view;
                            if (textbook.get('editing')) {
                                view = new EditTextbookView({model: textbook, ..._.pick(that.options, ['QuestionMarkWrapper'])});
                            } else {
                                view = new ShowTextbookView({model: textbook});
                            }
                            that.$body.append(view.render().el);
                        });
                    }
                    if (textbooks.find(p=>p.attributes.editing)) {
                        this.$el.addClass('editing-view')
                    } else {
                        this.$el.removeClass('editing-view')
                    }
                    return this;
                },
                events: {
                    'click .new-button': 'addOne'
                },
                addOne: function(e) {
                    var $sectionEl, $inputEl;
                    if (e && e.preventDefault) { e.preventDefault(); }
                    this.collection.add([{editing: true}]); // (render() call triggered here)
            // find the outer 'section' tag for the newly added textbook
                    $sectionEl = this.$body.find('section:last');
            // find the first input element in this section
                    $inputEl = $sectionEl.find('input:first');
            // activate the text box (so user can go ahead and start typing straight away)
                    $inputEl.focus().select();
                },
                handleDestroy: function(model, collection, options) {
                    collection.remove(model);
                }
            });
            return ListTextbooks;
        });
