
var edx = edx || {};

(function($, _, Backbone, gettext) {
    'use strict';

    edx.dialog = edx.dialog || {};
    edx.confirmation= edx.confirmation || {};

    window.LearningTribes = window.LearningTribes || {};
    window.LearningTribes.dialog = edx.dialog;
    window.LearningTribes.confirmation = edx.confirmation;

    var $dialogContainer = $('#dialog-container');

    var initialize = function () {
        this.$bg = $('<div class="message-dialog-transparent-background"></div>').addClass('hide');
        this.$el = $('<div></div>').addClass('message-dialog hide').html($('#dialog-template').html());
        $dialogContainer.append(this.$el);
        $dialogContainer.append(this.$bg);
        this.$el.find('i').on('click', $.proxy(function () {
            this.hide();
        }, this))
    }

    initialize.prototype.show = function (content, delay) {
        this.$el.find('.dialog-content').html(content);
        this.$bg.removeClass('hide')
        this.$el.removeClass('hide');
        if (delay) {
            setTimeout(()=>{
                this.hide()
            }, delay)
        }
    }

    initialize.prototype.hide = function() {
        this.$bg.addClass('hide');
        this.$el.addClass('hide');
    }

    // confirmation dialog
    var Confirmation = function (message, confirmationCallback, cancelCallback, commonCallback2) {
        const messageIsObject = typeof(message) == 'object'

        this.$bg = $('<div class="confirmation-dialog-transparent-background"></div>').addClass('hide');
        this.$el = $('<div></div>').addClass('confirmation-dialog hide').html($('#confirmation-template').html());
        $dialogContainer.append(this.$el);
        $dialogContainer.append(this.$bg);

        var cancel = $.proxy(function () {
            this.destroy();
            cancelCallback && cancelCallback();
            commonCallback2 && commonCallback2();
            if (messageIsObject) {
                const { cancelationCallback, commonCallback}=message;
                cancelationCallback && cancelationCallback();
                commonCallback && commonCallback();
            }
        }, this)
        var confirm = $.proxy(function () {
            this.destroy();
            confirmationCallback && confirmationCallback();
            commonCallback2 && commonCallback2();
            if (messageIsObject) {
                const {confirmationCallback, commonCallback}=message;
                confirmationCallback && confirmationCallback();
                commonCallback && commonCallback();
            }
        }, this)
        if (messageIsObject) {
            const $closingMarkButton = this.$el.find('i');
            const { hideClosingButton } = message;
            hideClosingButton && $closingMarkButton.hide();
        }
        this.$el.find('i').on('click', cancel)
        const $primary = this.$el.find('.btn-primary'),
            $secondary = this.$el.find('.btn-secondary')
        $primary.on('click', confirm)
        $secondary.on('click', cancel)
        if (messageIsObject) {
            if (message.confirmationText) {
                $primary.val(message.confirmationText)
            }
            if (message.cancelationText) {
                $secondary.val(message.cancelationText)
            }
        }

        const $dialogContent = this.$el.find('.dialog-content')
        if (messageIsObject) {
            if (typeof(message.message) == 'object') {
                $dialogContent.append(message.message)
            }else{
                $dialogContent.html(message.message)
            }
        }else{
            $dialogContent.html(message);
        }
    }

    Confirmation.prototype.destroy = function() {
        this.$el.remove();
        this.$bg.remove();
    }

    edx.dialog = LearningTribes.dialog = new initialize();
    edx.confirmation = LearningTribes.confirmation = {
        _confirmation:null,
        show: function (message, confirmationCallback, cancelCallback) {
            if (this._confirmation == null) {
                this._confirmation = new Confirmation (message, confirmationCallback, cancelCallback, $.proxy(function () {
                    this._confirmation = null;
                }, this))
            }
        }
    }

}(jQuery, _, Backbone, gettext));


