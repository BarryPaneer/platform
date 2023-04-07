(function(define) {
    'use strict';
    define([
        'jquery',
        'js/student_account/views/slowMovingPicture',
        'js/student_account/views/FormView'
    ],
        function($, SlowMovingPicture, FormView) {
            return FormView.extend({
                el: '#password-reset-form',

                tpl: '#password_reset-tpl',

                events: {
                    'click .js-reset': 'submitForm'
                },

                formType: 'password-reset',

                requiredStr: '',
                optionalStr: '',

                submitButton: '.js-reset',

                preRender: function(data) {
                    this.static_url = data.static_url;
                    this.element.show($(this.el));
                    this.element.show($(this.el).parent());
                    this.listenTo(this.model, 'sync', this.saveSuccess);

                    setTimeout($.proxy(function () {
                        var $bg = this.$el.find('.instruction-text'), $bgImg = $bg.find('img');
                        SlowMovingPicture($bgImg, $bg);
                    }, this), 200)

                },

                saveSuccess: function() {
                    this.trigger('password-email-sent');

                // Destroy the view (but not el) and unbind events
                    this.$el.empty().off();
                    this.stopListening();
                }
            });
        });
}).call(this, define || RequireJS.define);
