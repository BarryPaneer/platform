(function() {
    'use strict';

    var __hasProp = {}.hasOwnProperty,
        __extends = function(child, parent) {
            var key;
            for (key in parent) {
                if (__hasProp.call(parent, key)) {
                    child[key] = parent[key];
                }
            }
            function Ctor() {
                this.constructor = child;
            }
            Ctor.prototype = parent.prototype;
            child.prototype = new Ctor();
            child.__super__ = parent.prototype;
            return child;
        };

    define(['jquery', 'underscore', 'gettext', 'xblock/runtime.v1', 'js/views/xblock', 'js/views/modals/edit_xblock'],
        function($, _, gettext, XBlock, XBlockView, EditXBlockModal) {
            var ModuleEdit = (function(_super) {
                __extends(ModuleEdit, _super);

                function ModuleEdit() {
                    return ModuleEdit.__super__.constructor.apply(this, arguments);
                }

                ModuleEdit.prototype.tagName = 'li';

                ModuleEdit.prototype.className = 'component';

                ModuleEdit.prototype.editorMode = 'editor-mode';

                ModuleEdit.prototype.events = {
                    'click .edit-button': 'clickEditButton',
                    //'click .show-or-hide-button': 'switchStatus',
                    //'click .icon-show-hide': 'triggerToggle',
                    'click .show-or-hide-button': 'triggerToggle',
                    'click .delete-button': 'onDelete'
                };

                ModuleEdit.prototype.triggerToggle = function(e) {
                    this.options.onToggle && this.options.onToggle(e);
                }

                ModuleEdit.prototype.initialize = function() {
                    this.onDelete = this.options.onDelete;
                    //this.$el.addClass('status-invisible')
                    return this.render(this.options.afterCreate);
                };

                /*ModuleEdit.prototype.switchStatus = function(e) {
                    alert('test')
                }*/

                ModuleEdit.prototype.loadDisplay = function() {
                    var xblockElement;
                    xblockElement = this.$el.find('.xblock-student_view');
                    if (xblockElement.length > 0) {
                        return XBlock.initializeBlock(xblockElement);
                    }
                };

                ModuleEdit.prototype.createItem = function(parent, payload, callback, afterCreate) {
                    var _this = this;
                    this.options.afterCreate = afterCreate
                    if (_.isNull(callback)) {
                        callback = function() {};
                    }
                    payload.parent_locator = parent;
                    return $.postJSON(this.model.urlRoot + '/', payload, function(data) {
                        _this.model.set({
                            id: data.locator
                        });
                        _this.$el.data('locator', data.locator);
                        _this.$el.data('courseKey', data.courseKey);
                        return _this.render(afterCreate);
                    }).success(callback);
                };

                ModuleEdit.prototype.loadView = function(viewName, target, callback) {
                    var _this = this;
                    if (this.model.id) {
                        return $.ajax({
                            url: '' + (decodeURIComponent(this.model.url())) + '/' + viewName,
                            type: 'GET',
                            cache: false,
                            headers: {
                                Accept: 'application/json'
                            },
                            success: function(fragment) {
                                return _this.renderXBlockFragment(fragment, target).done(callback);
                            }
                        });
                    }
                };

                ModuleEdit.prototype.render = function(afterCreate) {
                    var _this = this;
                    return this.loadView('student_view', this.$el, function() {
                        _this.loadDisplay();
                        if(afterCreate){
                            afterCreate()
                        }
                     
                        return _this.delegateEvents();
                    });
                };

                ModuleEdit.prototype.clickEditButton = function(event) {
                    var modal;
                    event.preventDefault();
                    modal = new EditXBlockModal();
                    return modal.edit(this.$el, this.model, {
                        title: gettext('Page'),
                        refresh: _.bind(() => this.render(this.options.afterCreate), this),
                    });
                };

                return ModuleEdit;
            }(XBlockView));
            return ModuleEdit;
        });
}).call(this);
