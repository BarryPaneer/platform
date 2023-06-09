(function(define, undefined) {
    'use strict';
    define([
        'gettext', 'jquery', 'underscore', 'backbone', 'logger',
        'js/student_account/models/user_account_model',
        'js/student_account/models/user_preferences_model',
        'js/student_account/views/account_settings_fields',
        'js/student_account/views/account_settings_view',
        'edx-ui-toolkit/js/utils/string-utils',
        'edx-ui-toolkit/js/utils/html-utils',
        'js/views/message_banner',
    ], function(gettext, $, _, Backbone, Logger, UserAccountModel, UserPreferencesModel,
                 AccountSettingsFieldViews, AccountSettingsView, StringUtils, HtmlUtils,
                MessageBannerView) {
        return function(
            imageInfo,
            accountSettingsData,
            fieldsData,
            ordersHistoryData,
            authData,
            passwordResetSupportUrl,
            userAccountsApiUrl,
            userPreferencesApiUrl,
            accountUserId,
            platformName,
            contactEmail,
            ltPhoneNumber,
            ltGDPR,
            gdprMessage,
            allowEmailChange,
            allowNameChange,
            socialPlatforms,
            syncLearnerProfileData,
            enterpriseName,
            enterpriseReadonlyAccountFields,
            edxSupportUrl,
            extendedProfileFields,
            displaySocialMedia,
            displayAccountDeletion
        ) {
            var $accountSettingsElement, userAccountModel, userPreferencesModel, aboutSectionsData,
                accountsSectionData, ordersSectionData, accountSettingsView, showAccountSettingsPage,
                showLoadingError, orderNumber, getUserField, userFields, timeZoneDropdownField, countryDropdownField,
                emailFieldView, socialFields, accountDeletionFields, platformData,
                aboutSectionMessageType, aboutSectionMessage, fullnameFieldView, countryFieldView,
                fullNameFieldData, emailFieldData, countryFieldData, additionalFields, fieldItem, accountFields,
                profileImageFieldData, profileImageFieldView;

            $accountSettingsElement = $('.wrapper-account-settings');

            userAccountModel = new UserAccountModel(
                _.extend(
                    accountSettingsData
                ));
            userAccountModel.url = userAccountsApiUrl;

            userPreferencesModel = new UserPreferencesModel();
            userPreferencesModel.url = userPreferencesApiUrl;

            if (syncLearnerProfileData && enterpriseName) {
                aboutSectionMessageType = 'info';
                aboutSectionMessage = HtmlUtils.interpolateHtml(
                    gettext('Your profile settings are managed by {enterprise_name}. Contact your administrator or {link_start}edX Support{link_end} for help.'),  // eslint-disable-line max-len
                    {
                        enterprise_name: enterpriseName,
                        link_start: HtmlUtils.HTML(
                            StringUtils.interpolate(
                                '<a href="{edx_support_url}">', {
                                    edx_support_url: edxSupportUrl
                                }
                            )
                        ),
                        link_end: HtmlUtils.HTML('</a>')
                    }
                );
            }

            emailFieldData = {
                model: userAccountModel,
                title: gettext('Email Address (Sign In)'),
                valueAttribute: 'email',
                helpMessage: StringUtils.interpolate(
                    gettext('You receive messages from {platform_name} and course teams at this address.'),  // eslint-disable-line max-len
                    {platform_name: platformName}
                ),
                persistChanges: true
            };
            if (!allowEmailChange || (syncLearnerProfileData && enterpriseReadonlyAccountFields.fields.indexOf('email') !== -1)) {  // eslint-disable-line max-len
                emailFieldView = {
                    view: new AccountSettingsFieldViews.ReadonlyFieldView(emailFieldData)
                };
            } else {
                emailFieldView = {
                    view: new AccountSettingsFieldViews.EmailFieldView(emailFieldData)
                };
            }

            fullNameFieldData = {
                model: userAccountModel,
                title: gettext('Full Name'),
                valueAttribute: 'name',
                helpMessage: gettext('The name that is used for ID verification and that appears on your certificates.'),  // eslint-disable-line max-len,
                persistChanges: true
            };
            if (!allowNameChange || (syncLearnerProfileData && enterpriseReadonlyAccountFields.fields.indexOf('name') !== -1)) {
                fullnameFieldView = {
                    view: new AccountSettingsFieldViews.ReadonlyFieldView(fullNameFieldData)
                };
            } else {
                fullnameFieldView = {
                    view: new AccountSettingsFieldViews.TextFieldView(fullNameFieldData)
                };
            }

            countryFieldData = {
                model: userAccountModel,
                required: true,
                title: gettext('Country or Region of Residence'),
                valueAttribute: 'country',
                options: fieldsData.country.options,
                persistChanges: true,
                helpMessage: gettext('The country or region where you live.')
            };
            if (syncLearnerProfileData && enterpriseReadonlyAccountFields.fields.indexOf('country') !== -1) {
                countryFieldData.editable = 'never';
                countryFieldView = {
                    view: new AccountSettingsFieldViews.DropdownFieldView(
                        countryFieldData
                    )
                };
            } else {
                countryFieldView = {
                    view: new AccountSettingsFieldViews.DropdownFieldView(countryFieldData)
                };
            }

            profileImageFieldData = {
                model: userAccountModel,
                valueAttribute: 'profile_image',
                messageView: new MessageBannerView({ el: $('.message-banner') }),
                title: gettext('Username'),
                imageMaxBytes: imageInfo.profile_image_max_bytes,
                imageMinBytes: imageInfo.profile_image_min_bytes,
                imageUploadUrl: imageInfo.profile_image_upload_url,
                imageRemoveUrl: imageInfo.profile_image_remove_url,
                helpMessage: gettext('You can upload an image that you want to associate with your username. Your image must be a .gif, .jpg or .png file. We recommend to use the format 200x200 pixels. The size of the image must be below 1Mb.')
            };
            if (syncLearnerProfileData && enterpriseReadonlyAccountFields.fields.indexOf('profile_image') !== -1) {
                profileImageFieldData.editable = 'never';
                profileImageFieldView = {
                    view: new AccountSettingsFieldViews.ProfileImageFieldView(profileImageFieldData)
                };
            } else {
                profileImageFieldData.editable = 'toggle';
                profileImageFieldView = {
                    view: new AccountSettingsFieldViews.ProfileImageFieldView(profileImageFieldData)
                };
            }

            aboutSectionsData = [
                {
                    title: gettext('Basic Account Information'),
                    subtitle: gettext('These settings include basic information about your account.'),

                    messageType: aboutSectionMessageType,
                    message: aboutSectionMessage,

                    fields: [
                        profileImageFieldView,
                        {
                            view: new AccountSettingsFieldViews.ReadonlyFieldView({
                                model: userAccountModel,
                                title: gettext('Username'),
                                valueAttribute: 'username',
                                helpMessage: StringUtils.interpolate(
                                    gettext('The name that identifies you on {platform_name}. You cannot change your username.'),  // eslint-disable-line max-len
                                    {platform_name: platformName}
                                )
                            })
                        },
                        fullnameFieldView,
                        emailFieldView,
                        {
                            view: new AccountSettingsFieldViews.PhoneNumberFieldView({
                                model: userAccountModel,
                                title: gettext('Phone Number'),
                                valueAttribute: 'lt_phone_number',
                                persistChanges: true
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.CheckboxFieldView({
                                model: userAccountModel,
                                title: gettext(gdprMessage),
                                valueAttribute: 'lt_gdpr',
                                persistChanges: true
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.PasswordFieldView({
                                model: userAccountModel,
                                title: gettext('Password'),
                                screenReaderTitle: gettext('Reset Your Password'),
                                valueAttribute: 'password',
                                emailAttribute: 'email',
                                passwordResetSupportUrl: passwordResetSupportUrl,
                                linkTitle: gettext('Reset Your Password'),
                                linkHref: fieldsData.password.url,
                                helpMessage: gettext('Check your email account for instructions to reset your password.')  // eslint-disable-line max-len
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.LanguagePreferenceFieldView({
                                model: userPreferencesModel,
                                title: gettext('Language'),
                                valueAttribute: 'pref-lang',
                                required: true,
                                refreshPageOnSave: true,
                                helpMessage: StringUtils.interpolate(
                                    gettext('The language used throughout this site. This site is currently available in a limited number of languages. Changing the value of this field will cause the page to refresh.'),  // eslint-disable-line max-len
                                    {platform_name: platformName}
                                ),
                                options: fieldsData.language.options,
                                persistChanges: true
                            })
                        },
                        countryFieldView,
                        {
                            view: new AccountSettingsFieldViews.TimeZoneFieldView({
                                model: userPreferencesModel,
                                required: true,
                                title: gettext('Time Zone'),
                                valueAttribute: 'time_zone',
                                helpMessage: gettext('Select the time zone for displaying course dates. If you do not specify a time zone, course dates, including assignment deadlines, will be displayed in your browser\'s local time zone.'), // eslint-disable-line max-len
                                groupOptions: [{
                                    groupTitle: gettext('All Time Zones'),
                                    selectOptions: fieldsData.time_zone.options,
                                    nullValueOptionLabel: gettext('Default (Local Time Zone)')
                                }],
                                persistChanges: true
                            })
                        }
                    ]
                },
                {
                    title: gettext('Additional Information'),
                    fields: [
                        {
                            view: new AccountSettingsFieldViews.DropdownFieldView({
                                model: userAccountModel,
                                title: gettext('Education Completed'),
                                valueAttribute: 'level_of_education',
                                options: fieldsData.level_of_education.options,
                                persistChanges: true
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.DropdownFieldView({
                                model: userAccountModel,
                                title: gettext('Gender'),
                                valueAttribute: 'gender',
                                options: fieldsData.gender.options,
                                persistChanges: true
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.DropdownFieldView({
                                model: userAccountModel,
                                title: gettext('Year of Birth'),
                                valueAttribute: 'year_of_birth',
                                options: fieldsData.year_of_birth.options,
                                persistChanges: true
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.LanguageProficienciesFieldView({
                                model: userAccountModel,
                                title: gettext('Preferred Language'),
                                valueAttribute: 'language_proficiencies',
                                options: fieldsData.preferred_language.options,
                                persistChanges: true
                            })
                        }
                    ]
                }
            ];

            accountFields = aboutSectionsData[0].fields;
            for (var i = 0; i < accountFields.length; i++) {
                if (accountFields[i].view.fieldType === 'phone_number' && ltPhoneNumber === 'hidden') {
                    accountFields.splice(i, 1);
                }
                if (accountFields[i].view.fieldType === 'gdpr' && ltGDPR === 'hidden') {
                    accountFields.splice(i, 1);
                    i--; // avoid to skip matched items. make sure this's the last statement in current loop.
                }
            }
            // Add the extended profile fields
            additionalFields = aboutSectionsData[1];
            for (var field in extendedProfileFields) {  // eslint-disable-line guard-for-in, no-restricted-syntax, vars-on-top, max-len
                fieldItem = extendedProfileFields[field];
                if (fieldItem.field_type === 'TextField') {
                    additionalFields.fields.push({
                        view: new AccountSettingsFieldViews.ExtendedFieldTextFieldView({
                            model: userAccountModel,
                            title: fieldItem.field_label,
                            fieldName: fieldItem.field_name,
                            valueAttribute: 'extended_profile',
                            persistChanges: true
                        })
                    });
                } else {
                    if (fieldItem.field_type === 'ListField') {
                        additionalFields.fields.push({
                            view: new AccountSettingsFieldViews.ExtendedFieldListFieldView({
                                model: userAccountModel,
                                title: fieldItem.field_label,
                                fieldName: fieldItem.field_name,
                                options: fieldItem.field_options,
                                valueAttribute: 'extended_profile',
                                persistChanges: true
                            })
                        });
                    }
                }
            }


            // Add the social link fields
            socialFields = {
                title: gettext('Social Media Links'),
                subtitle: StringUtils.interpolate(gettext('Optionally, link your personal accounts to the social media icons on your {platform_name} profile.'), { // eslint-disable-line max-len
                    platform_name: platformName
                }),
                fields: []
            };

            for (var socialPlatform in socialPlatforms) {  // eslint-disable-line guard-for-in, no-restricted-syntax, vars-on-top, max-len
                platformData = socialPlatforms[socialPlatform];
                socialFields.fields.push(
                    {
                        view: new AccountSettingsFieldViews.SocialLinkTextFieldView({
                            model: userAccountModel,
                            title: StringUtils.interpolate(
                                gettext('{platform_name} Link'), {platform_name: platformData.display_name}
                            ),
                            valueAttribute: 'social_links',
                            helpMessage: StringUtils.interpolate(
                                gettext(
                                'Enter your {platform_name} username or the URL to your {platform_name} page. Delete the URL to remove the link.'), // eslint-disable-line max-len
                                {platform_name: platformData.display_name}
                            ),
                            platform: socialPlatform,
                            persistChanges: true,
                            placeholder: platformData.example
                        })
                    }
                );
            }
            //display social media or not base on site configuration
            if (displaySocialMedia) {
                aboutSectionsData.push(socialFields);
            }
            // Add account deletion fields
            if (displayAccountDeletion) {
                accountDeletionFields = {
                    title: gettext('Delete My Account'),
                    fields: [],
                    // Used so content can be rendered external to Backbone
                    domHookId: 'account-deletion-container'
                };
                aboutSectionsData.push(accountDeletionFields);
            }

            // set TimeZoneField to listen to CountryField

            getUserField = function(list, search) {
                return _.find(list, function(field) {
                    return field.view.options.valueAttribute === search;
                }).view;
            };
            userFields = _.find(aboutSectionsData, function(section) {
                return section.title === gettext('Basic Account Information');
            }).fields;
            timeZoneDropdownField = getUserField(userFields, 'time_zone');
            countryDropdownField = getUserField(userFields, 'country');
            timeZoneDropdownField.listenToCountryView(countryDropdownField);

            accountsSectionData = [
                {
                    title: gettext('Linked Accounts'),
                    subtitle: StringUtils.interpolate(
                        gettext('You can link your social media accounts to simplify signing in to {platform_name}.'),
                        {platform_name: platformName}
                    ),
                    fields: _.map(authData.providers, function(provider) {
                        return {
                            view: new AccountSettingsFieldViews.AuthFieldView({
                                title: provider.name,
                                valueAttribute: 'auth-' + provider.id,
                                helpMessage: '',
                                connected: provider.connected,
                                connectUrl: provider.connect_url,
                                acceptsLogins: provider.accepts_logins,
                                disconnectUrl: provider.disconnect_url,
                                platformName: platformName
                            })
                        };
                    })
                }
            ];

            ordersHistoryData.unshift(
                {
                    title: gettext('ORDER NAME'),
                    order_date: gettext('ORDER PLACED'),
                    price: gettext('TOTAL'),
                    number: gettext('ORDER NUMBER')
                }
            );

            ordersSectionData = [
                {
                    title: gettext('My Orders'),
                    subtitle: StringUtils.interpolate(
                        gettext('This page contains information about orders that you have placed with {platform_name}.'),  // eslint-disable-line max-len
                        {platform_name: platformName}
                    ),
                    fields: _.map(ordersHistoryData, function(order) {
                        orderNumber = order.number;
                        if (orderNumber === 'ORDER NUMBER') {
                            orderNumber = 'orderId';
                        }
                        return {
                            view: new AccountSettingsFieldViews.OrderHistoryFieldView({
                                totalPrice: order.price,
                                orderId: order.number,
                                orderDate: order.order_date,
                                receiptUrl: order.receipt_url,
                                valueAttribute: 'order-' + orderNumber,
                                lines: order.lines
                            })
                        };
                    })
                }
            ];

            accountSettingsView = new AccountSettingsView({
                model: userAccountModel,
                accountUserId: accountUserId,
                el: $accountSettingsElement,
                tabSections: {
                    aboutTabSections: aboutSectionsData,
                    accountsTabSections: accountsSectionData,
                    ordersTabSections: ordersSectionData
                },
                userPreferencesModel: userPreferencesModel
            });

            accountSettingsView.render();

            showAccountSettingsPage = function() {
                // Record that the account settings page was viewed.
                Logger.log('edx.user.settings.viewed', {
                    page: 'account',
                    visibility: null,
                    user_id: accountUserId
                });
            };

            showLoadingError = function() {
                accountSettingsView.showLoadingError();
            };

            userAccountModel.fetch({
                success: function() {
                    // Fetch the user preferences model
                    userPreferencesModel.fetch({
                        success: showAccountSettingsPage,
                        error: showLoadingError
                    });
                },
                error: showLoadingError
            });

            return {
                userAccountModel: userAccountModel,
                userPreferencesModel: userPreferencesModel,
                accountSettingsView: accountSettingsView
            };
        };
    });
}).call(this, define || RequireJS.define);
