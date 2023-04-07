(function(define) {
    'use strict';
    define([
        'jquery',
        'underscore',
        'gettext',
        'edx-ui-toolkit/js/utils/html-utils',
        'edx-ui-toolkit/js/utils/string-utils',
        'js/student_account/views/slowMovingPicture',
        'js/student_account/views/FormView',
        'text!templates/student_account/form_success.underscore',
        'text!templates/student_account/form_status.underscore'
    ], function(
            $, _, gettext,
            HtmlUtils,
            StringUtils,
            SlowMovingPicture,
            FormView,
            formSuccessTpl,
            formStatusTpl
    ) {
        return FormView.extend({
            el: '#login-form',
            tpl: '#login-tpl',
            events: {
                'click .js-login': 'submitForm',
                'click .forgot-password': 'forgotPassword',
                'click .login-provider': 'thirdPartyAuth',
                'click .sso-login': 'switchSSOLogin',
                'click .email-login': 'switchEmailLogin'
            },
            formType: 'login',
            requiredStr: '',
            optionalStr: '',
            submitButton: '.js-login',
            formSuccessTpl: formSuccessTpl,
            formStatusTpl: formStatusTpl,
            authWarningJsHook: 'js-auth-warning',
            passwordResetSuccessJsHook: 'js-password-reset-success',
            defaultFormErrorsTitle: gettext('We couldn\'t sign you in.'),

            preRender: function(data) {
                this.providers = data.thirdPartyAuth.providers || [];
                this.hasSecondaryProviders = (
                    data.thirdPartyAuth.secondaryProviders && data.thirdPartyAuth.secondaryProviders.length
                );
                this.currentProvider = data.thirdPartyAuth.currentProvider || '';
                this.syncLearnerProfileData = data.thirdPartyAuth.syncLearnerProfileData || false;
                this.errorMessage = data.thirdPartyAuth.errorMessage || '';
                this.platformName = data.platformName;
                this.resetModel = data.resetModel;
                this.supportURL = data.supportURL;
                this.passwordResetSupportUrl = data.passwordResetSupportUrl;
                this.createAccountOption = data.createAccountOption;
                this.allowRegistrationForm = data.allowRegistrationForm;
                this.accountActivationMessages = data.accountActivationMessages;
                this.hideAuthWarnings = data.hideAuthWarnings;
                this.pipelineUserDetails = data.pipelineUserDetails;
                this.enterpriseName = data.enterpriseName;
                this.static_url = data.static_url;
                this.register_user_url = data.register_user_url;
                this.prioritizeEmailLogin = data.prioritize_email_login;

                this.listenTo(this.model, 'sync', this.saveSuccess);
                this.listenTo(this.resetModel, 'sync', this.resetEmail);
            },

            render: function(html) {
                var fields = html || '';

                $(this.el).html(_.template(this.tpl)({
                // We pass the context object to the template so that
                // we can perform variable interpolation using sprintf
                    context: {
                        fields: fields,
                        currentProvider: this.currentProvider,
                        syncLearnerProfileData: this.syncLearnerProfileData,
                        providers: this.providers,
                        hasSecondaryProviders: this.hasSecondaryProviders,
                        platformName: this.platformName,
                        createAccountOption: this.createAccountOption,
                        allowRegistrationForm: this.allowRegistrationForm,
                        pipelineUserDetails: this.pipelineUserDetails,
                        enterpriseName: this.enterpriseName,
                        static_url: this.static_url
                    }
                }));

                this.postRender();

                var $bg = this.$el.find('.instruction-text'), $bgImg = $bg.find('img');
                SlowMovingPicture($bgImg, $bg);
                return this;
            },

            postRender: function() {
                var formErrorsTitle;
                this.$container = $(this.el);
                this.$form = this.$container.find('form');
                this.$formFeedback = this.$container.find('.js-form-feedback');
                this.$submitButton = this.$container.find(this.submitButton);

                if (this.errorMessage) {
                    formErrorsTitle = _.sprintf(
                        gettext('An error occurred when signing you in to %s.'),
                        this.platformName
                    );
                    this.renderErrors(formErrorsTitle, [this.errorMessage]);
                } else if (this.currentProvider) {
                    /* If we're already authenticated with a third-party
                     * provider, try logging in. The easiest way to do this
                     * is to simply submit the form.
                     */
                    this.model.save();
                }

                // Display account activation success or error messages.
                this.renderAccountActivationMessages();
                // Display normal form or third-party auth link according to if we have providers.
                this.displayLoginSection();
            },

            renderAccountActivationMessages: function() {
                _.each(this.accountActivationMessages, this.renderAccountActivationMessage, this);
            },

            renderAccountActivationMessage: function(message) {
                this.renderFormFeedback(this.formStatusTpl, {
                    jsHook: message.tags,
                    message: HtmlUtils.HTML(message.message)
                });
            },

            displayLoginSection: function() {
                var hasSSOProviders = this.providers.length > 0 && !this.currentProvider || this.hasSecondaryProviders
                if (!hasSSOProviders || this.prioritizeEmailLogin) {
                    this.$form.removeClass('hidden');
                    $('.login-providers').addClass('hidden');
                    $('.email-login-link').addClass('hidden');
                    if (hasSSOProviders) {
                        $('.sso-link').removeClass('hidden');
                    } else {
                        $('.sso-link').addClass('hidden');
                    }
                } else {
                    this.$form.addClass('hidden');
                    $('.login-providers').removeClass('hidden');
                    $('.email-login-link').removeClass('hidden');
                    $('.sso-link').addClass('hidden');
                }
            },

            forgotPassword: function(event) {
                event.preventDefault();

                this.trigger('password-help');
                this.clearPasswordResetSuccess();
            },

            postFormSubmission: function() {
                this.clearPasswordResetSuccess();
            },

            resetEmail: function() {
                var email = $('#password-reset-email').val(),
                    successTitle = gettext('Password Reset Email Sent'),
                    successMessageHtml = HtmlUtils.interpolateHtml(
                        gettext("We've sent instructions to the email address you provided."), { // eslint-disable-line max-len
                            boldStart: HtmlUtils.HTML('<b>'),
                            boldEnd: HtmlUtils.HTML('</b>'),
                            paragraphStart: HtmlUtils.HTML('<p>'),
                            paragraphEnd: HtmlUtils.HTML('</p>'),
                            email: email,
                            platform_name: this.platformName,
                            anchorStart: HtmlUtils.HTML(
                                StringUtils.interpolate(
                                    '<a href="{passwordResetSupportUrl}">', {
                                        passwordResetSupportUrl: this.passwordResetSupportUrl
                                    }
                                )
                            ),
                            anchorEnd: HtmlUtils.HTML('</a>')
                        }
                    );

                this.clearFormErrors();
                this.clearPasswordResetSuccess();

                this.renderFormFeedback(this.formSuccessTpl, {
                    jsHook: this.passwordResetSuccessJsHook,
                    title: successTitle,
                    messageHtml: successMessageHtml
                });
            },

            thirdPartyAuth: function(event) {
                var providerUrl = $(event.currentTarget).data('provider-url') || '';

                if (providerUrl) {
                    window.location.href = providerUrl;
                }
            },

            switchSSOLogin: function(event) {
                event.preventDefault();
                this.clearFormErrors();
                if (!this.$form.hasClass('hidden')) {
                    this.$form.addClass('hidden');
                }
                if ($('.login-providers').hasClass('hidden')) {
                    $('.login-providers').removeClass('hidden');
                }
                if (!$('.sso-link').hasClass('hidden')) {
                    $('.sso-link').addClass('hidden');
                }
                if ($('.email-login-link').hasClass('hidden')) {
                    $('.email-login-link').removeClass('hidden');
                }
            },

            switchEmailLogin: function(event) {
                event.preventDefault();
                this.clearFormErrors();
                if (this.$form.hasClass('hidden')) {
                    this.$form.removeClass('hidden');
                }
                if (!$('.login-providers').hasClass('hidden')) {
                    $('.login-providers').addClass('hidden');
                }
                if ($('.sso-link').hasClass('hidden')) {
                    $('.sso-link').removeClass('hidden');
                }
                if (!$('.email-login-link').hasClass('hidden')) {
                    $('.email-login-link').addClass('hidden');
                }
            },

            saveSuccess: function() {
                this.trigger('auth-complete');
                this.clearPasswordResetSuccess();
            },

            saveError: function(error) {
                var msg = error.responseText;
                if (error.status === 0) {
                    msg = gettext('An error has occurred. Check your Internet connection and try again.');
                } else if (error.status === 500) {
                    msg = gettext('An error has occurred. Try refreshing the page, or check your Internet connection.'); // eslint-disable-line max-len
                }
                this.errors = [
                    StringUtils.interpolate(
                        '<li>{msg}</li>', {
                            msg: msg
                        }
                    )
                ];
                this.clearPasswordResetSuccess();

            /* If we've gotten a 403 error, it means that we've successfully
             * authenticated with a third-party provider, but we haven't
             * linked the account to an EdX account.  In this case,
             * we need to prompt the user to enter a little more information
             * to complete the registration process.
             */
                if (error.status === 403 &&
                 error.responseText === 'third-party-auth' &&
                 this.currentProvider) {
                    if (!this.hideAuthWarnings) {
                        this.clearFormErrors();
                        this.renderAuthWarning();
                    }
                } else {
                    this.renderErrors(this.defaultFormErrorsTitle, this.errors);
                }
                this.toggleDisableButton(false);
            },

            renderAuthWarning: function() {
                var message = _.sprintf(
                    gettext('You have successfully signed into %(currentProvider)s, but your %(currentProvider)s' +
                            ' account is not linked to your %(platformName)s account yet. To permanently link your accounts,' +
                            ' sign in now using your %(platformName)s password.'),
                    {currentProvider: this.currentProvider, platformName: this.platformName}
                );

                var step_1_text = _.sprintf(
                    gettext('Step 1: Sign into %(currentProvider)s'),
                    {currentProvider: this.currentProvider}
                );
                var step_2_text = _.sprintf(
                    gettext('Step 2: Permanently link your %(currentProvider)s account to your %(platformName)s account'),
                    {currentProvider: this.currentProvider, platformName: this.platformName}
                );

                this.hideWelcomeText();
                this.clearAuthWarning();
                this.renderFormFeedback(this.formStatusTpl, {
                    jsHook: this.authWarningJsHook,
                    message: message,
                    step_1_text: step_1_text,
                    step_2_text: step_2_text,
                    register_url_enable_flag: true,
                    question_text: gettext('First time here?'),
                    register_user_url: this.register_user_url,
                    register_text: gettext('Create an Account.')
                });
            },

            clearPasswordResetSuccess: function() {
                var query = '.' + this.passwordResetSuccessJsHook;
                this.clearFormFeedbackItems(query);
            },

            clearAuthWarning: function() {
                var query = '.' + this.authWarningJsHook;
                this.clearFormFeedbackItems(query);
            },

            hideWelcomeText: function() {
                document.querySelectorAll('.welcome-text figcaption').forEach($el => {
                    $el.style.display = 'none'
                })
            },
        });
    });
}).call(this, define || RequireJS.define);
