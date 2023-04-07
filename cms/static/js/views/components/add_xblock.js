/**
 * This is a simple component that renders add buttons for all available XBlock template types.
 */
define(['jquery', 'underscore', 'gettext', 'js/views/baseview', 'common/js/components/utils/view_utils',
    'js/views/components/add_xblock_button', 'js/views/components/add_xblock_menu', 'text!js/views/components/components.json'],
    function($, _, gettext, BaseView, ViewUtils, AddXBlockButton, AddXBlockMenu, componentsText) {
        var EFFECTION_PEROID = 250;
        var AddXBlockComponent = BaseView.extend({
            events: {
                'click .new-component-templates': 'stopEvents',
                'click .new-component .new-component-type .multiple-templates': 'showComponentTemplates',
                'click .new-component .new-component-type .single-template': 'createNewComponent',
                'click .new-component .cancel-button': 'closeNewComponent',
                'click .new-component-templates .new-component-template .button-component': 'createNewComponent',
                'click .new-component-templates .cancel-button': 'closeNewComponent'
            },

            stopEvents: function() {
                event.preventDefault();
                event.stopPropagation();
                return false;
            },
            hideAllTemplates: function() {
                this.$el.find('.new-component-templates').hide();
            },
            initialize: function(options) {
                BaseView.prototype.initialize.call(this, options);
                this.template = this.loadTemplate('add-xblock-component');
                $(document.body).on('click', $.proxy(this.hideAllTemplates, this))
            },

            render: function() {
                if (!this.$el.html()) {
                    var that = this;
                    this.$el.html(this.template({}));
                    this.collection.each(
                        function(componentModel) {
                            var view, menu;
                            var GroupsConfig = JSON.parse(componentsText);
                            view = new AddXBlockButton({model: componentModel, help: GroupsConfig[componentModel.type].help});
                            that.$el.find('.new-component-type').append(view.render().el);

                            menu = new AddXBlockMenu({model: componentModel, GroupsConfig});
                            that.$el.append(menu.render().el);
                        }
                    );
                }
            },

            showComponentTemplates: function(event) {
                setTimeout($.proxy(function(){
                    var type;
                    event.preventDefault();
                    event.stopPropagation();
                    type = $(event.currentTarget).data('type');
                    var offset = $(event.currentTarget).position();
                    var targetComputedStyle = getComputedStyle(event.currentTarget)
                    var direction = targetComputedStyle.getPropertyValue('direction') || 'ltr'
                    var style = direction === 'ltr'
                        ? {
                            left: offset.left,
                            top: offset.top
                        }
                        : {
                            left: offset.left + event.currentTarget.clientWidth + 2 + (parseInt(targetComputedStyle.getPropertyValue('margin-left')) || 0),
                            top: offset.top,
                            transform: 'translateX(-100%)',
                        }
                    this.$('.new-component-' + type).fadeIn(EFFECTION_PEROID).css(style)
                    this.$('.new-component-' + type + ' div').focus();
                }, this), 200)
            },

            closeNewComponent: function(event) {
                event.preventDefault();
                event.stopPropagation();
                type = $(event.currentTarget).data('type');
                //this.$('.new-component').fadeIn(EFFECTION_PEROID);
                this.$('.new-component-templates').fadeOut(EFFECTION_PEROID);
                this.$('ul.new-component-type li button[data-type=' + type + ']').focus();
            },

            createNewComponent: function(event) {
                var self = this,
                    $element = $(event.currentTarget),
                    saveData = $element.data(),
                    oldOffset = ViewUtils.getScrollOffset(this.$el);
                event.preventDefault();
                this.closeNewComponent(event);
                ViewUtils.runOperationShowingMessage(
                    gettext('Adding'),
                    _.bind(this.options.createComponent, this, saveData, $element)
                ).always(function() {
                    // Restore the scroll position of the buttons so that the new
                    // component appears above them.
                    ViewUtils.setScrollOffset(self.$el, oldOffset);
                });
            }
        });

        return AddXBlockComponent;
    }); // end define();
