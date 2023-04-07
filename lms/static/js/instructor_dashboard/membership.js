/* globals _, AutoEnrollmentViaCsv, NotificationModel, NotificationView */

/*
Membership Section

imports from other modules.
wrap in (-> ... apply) to defer evaluation
such that the value can be defined later than this assignment (file load order).
*/

(function() {
    'use strict';
    var AuthListWidget,
        Membership,
        BatchEnrollment,
        SendWelcomingEmail,
        BetaTesterBulkAddition,
        MemberListWidget,
        emailStudents, plantTimeout, statusAjaxError, enableAddButton,
        /* eslint-disable */
        __hasProp = {}.hasOwnProperty,
        __extends = function(child, parent) { for (var key in parent) { if (__hasProp.call(parent, key)) child[key] = parent[key]; } function ctor() { this.constructor = child; } ctor.prototype = parent.prototype; child.prototype = new ctor(); child.__super__ = parent.prototype; return child; };
        /* eslint-enable */

    var removeLoading = function ($target) {
        return function() {
            $target.parent().removeClass('loading-wrapper');
        }
    }

    var startLoading = function(e) {
        var $target = $(e.currentTarget);
        $target.parent().addClass('loading-wrapper');
        return $target;
    }

    plantTimeout = function() {
        return window.InstructorDashboard.util.plantTimeout.apply(this, arguments);
    };

    statusAjaxError = function() {
        return window.InstructorDashboard.util.statusAjaxError.apply(this, arguments);
    };

    enableAddButton = function(enable, parent) {
        var $addButton = parent.$('input[type="button"].add');
        var $addField = parent.$('input[type="text"].add-field');
        if (enable) {
            $addButton.removeAttr('disabled');
            $addField.removeAttr('disabled');
        } else {
            $addButton.attr('disabled', true);
            $addField.attr('disabled', true);
        }
    };

    emailStudents = false;

    MemberListWidget = (function() {
        function memberListWidget($container, params) {
            var templateHtml, condition,
                memberListParams = params || {},
                memberlistwidget = this;
            this.$container = $container;
            memberListParams = _.defaults(memberListParams, {
                title: 'Member List',
                info: 'Use this list to manage members.',
                labels: ['field1', 'field2', 'field3'],
                add_placeholder: 'Enter name',
                add_btn_label: 'Add Member',
                add_handler: function() {}
            });
            templateHtml = edx.HtmlUtils.template($('#membership-list-widget-tpl').text())(memberListParams);
            edx.HtmlUtils.setHtml(this.$container, templateHtml);
            this.$('input[type="button"].add').click(function() {
                condition = typeof memberListParams.add_handler === 'function';
                return condition ? memberListParams.add_handler(memberlistwidget.$('.add-field').val()) : undefined;
            });
        }

        memberListWidget.prototype.clear_input = function() {
            return this.$('.add-field').val('');
        };

        memberListWidget.prototype.clear_rows = function() {
            return this.$('table tbody').empty();
        };

        memberListWidget.prototype.add_row = function(rowArray) {
            var $tbody, $td, $tr, item, i, len;
            $tbody = this.$('table tbody');
            $tr = $('<tr>');
            for (i = 0, len = rowArray.length; i < len; i++) {
                item = rowArray[i];
                $td = $('<td>');
                if (item instanceof jQuery) {
                    edx.HtmlUtils.append($td, edx.HtmlUtils.HTML(item));
                } else {
                    $td.text(item);
                }
                $tr.append($td);
            }
            return $tbody.append($tr);
        };

        memberListWidget.prototype.$ = function(selector) {
            var s;
            if (this.debug != null) {
                s = this.$container.find(selector);
                return s;
            } else {
                return this.$container.find(selector);
            }
        };

        return memberListWidget;
    }());

    AuthListWidget = (function(_super) {
        __extends(AuthListWidget, _super);  // eslint-disable-line no-use-before-define
        function AuthListWidget($container, rolename, $errorSection) {  // eslint-disable-line no-shadow
            var msg,
                authListWidget = this,
                labelsList = ['', gettext('Username'), gettext('Email'), gettext('Revoke access')];
            this.rolename = rolename;
            this.$errorSection = $errorSection;
            this.list_enabled = true;
            if (this.rolename === 'Group Moderator') {
                labelsList = [gettext('Username'), gettext('Email'), gettext('Group'), gettext('Revoke access')];
            }
            AuthListWidget.__super__.constructor.call(this, $container, {  // eslint-disable-line no-underscore-dangle
                title: $container.data('display-name'),
                info: $container.data('info-text'),
                labels: labelsList,
                add_title:gettext('Add new team member'),
                add_placeholder: gettext('Enter username or email'),
                add_btn_label: $container.data('add-button-label'),
                add_handler: function(input) {
                    return authListWidget.add_handler(input);
                }
            });
            this.debug = true;
            this.list_endpoint = $container.data('list-endpoint');
            this.modify_endpoint = $container.data('modify-endpoint');
            if (this.rolename == null) {
                msg = 'AuthListWidget missing @rolename';
                throw msg;
            }
            this.reload_list();
        }

        AuthListWidget.prototype.re_view = function() {
            this.clear_errors();
            this.clear_input();
            return this.reload_list();
        };

        AuthListWidget.prototype.add_handler = function(input) {
            var authListWidgetAddHandler = this;
            if ((input != null) && input !== '') {
                return this.modify_member_access(input, 'allow', function(error) {
                    if (error !== null) {
                        return authListWidgetAddHandler.show_errors(error);
                    }
                    authListWidgetAddHandler.clear_errors();
                    authListWidgetAddHandler.clear_input();
                    return authListWidgetAddHandler.reload_list();
                });
            } else {
                return this.show_errors(gettext('Please enter a username or email.'));
            }
        };

        AuthListWidget.prototype.reload_list = function() {
            var authListWidgetReloadList = this,
                $selectedOption;
            return this.get_member_list(function(error, memberList, divisionScheme) {
                if (error !== null) {
                    authListWidgetReloadList.show_errors(error);
                    return;
                }
                authListWidgetReloadList.clear_rows();

                _.each(memberList, function(member) {
                    var $revokeBtn, labelTrans;
                    labelTrans = gettext('Revoke access');

                    $revokeBtn = $(_.template('<div class="revoke"><span class="icon far fa-times-circle" aria-hidden="true"></span> <%- label %></div>')({  // eslint-disable-line max-len
                        label: labelTrans
                    }), {
                        class: 'revoke'
                    });
                    $revokeBtn.click(function() {
                        authListWidgetReloadList.modify_member_access(member.email, 'revoke', function(err) {
                            if (err !== null) {
                                authListWidgetReloadList.show_errors(err);
                                return;
                            }
                            authListWidgetReloadList.clear_errors();
                            authListWidgetReloadList.reload_list();
                        });
                    });
                    const $img = $('<img class="portrait"/>');
                    $img.attr('src', member.profile_image_url);
                    if (authListWidgetReloadList.rolename === 'Group Moderator') {
                        if (divisionScheme !== undefined && divisionScheme === 'none') {
                            // There is No discussion division scheme selected so the Group Moderator role
                            // should be disabled
                            authListWidgetReloadList.list_enabled = false;
                            $selectedOption = $('select#member-lists-selector').children('option:selected');
                            if ($selectedOption[0].value === authListWidgetReloadList.rolename) {
                                authListWidgetReloadList.show_errors(
                                    gettext('This role requires a divided discussions scheme.')
                                );
                                enableAddButton(false, authListWidgetReloadList);
                            }
                        } else {
                            authListWidgetReloadList.list_enabled = true;
                            enableAddButton(true, authListWidgetReloadList);
                            authListWidgetReloadList.add_row([member.username, member.email,
                                member.group_name, $revokeBtn]
                            );
                        }
                    } else {
                        authListWidgetReloadList.add_row([$img, member.username, member.email, $revokeBtn]);
                    }
                });
            });
        };

        AuthListWidget.prototype.clear_errors = function() {
            if (this.$errorSection !== undefined) {
                this.$errorSection.text('');
                return this.$errorSection.css({display: 'none'});
            }
            return undefined;
        };

        AuthListWidget.prototype.show_errors = function(msg) {
            if (this.$errorSection !== undefined) {
                this.$errorSection.text(msg);
                return this.$errorSection.css({display: 'block'});
            }
            return undefined;
        };

        AuthListWidget.prototype.get_member_list = function(cb) {
            var authlistwidgetgetmemberlist = this;
            $.ajax({
                type: 'POST',
                dataType: 'json',
                url: this.list_endpoint,
                data: {
                    rolename: this.rolename
                },
                success: function(data) {
                    return typeof cb === 'function' ? cb(
                        null,
                        data[authlistwidgetgetmemberlist.rolename],
                        data.division_scheme
                    ) : undefined;
                }
            });
        };

        AuthListWidget.prototype.modify_member_access = function(uniqueStudentIdentifier, action, cb) {
            var authlistwidgetmemberaccess = this;
            return $.ajax({
                type: 'POST',
                dataType: 'json',
                url: this.modify_endpoint,
                data: {
                    unique_student_identifier: uniqueStudentIdentifier,
                    rolename: this.rolename,
                    action: action
                },
                success: function(data) {
                    return authlistwidgetmemberaccess.member_response(data);
                },
                error: statusAjaxError(function() {
                    return typeof cb === 'function' ? cb(gettext("Error changing user's permissions.")) : undefined;
                })
            });
        };

        AuthListWidget.prototype.member_response = function(data) {
            var msg;
            this.clear_errors();
            this.clear_input();
            if (data.userDoesNotExist) {
                msg = gettext("Could not find a user with username or email address '<%- identifier %>'.");
                return this.show_errors(_.template(msg, {
                    identifier: data.unique_student_identifier
                }));
            } else if (data.inactiveUser) {
                msg = gettext("Error: User '<%- username %>' has not yet activated their account. Users must create and activate their accounts before they can be assigned a role.");  // eslint-disable-line max-len
                return this.show_errors(_.template(msg, {
                    username: data.unique_student_identifier
                }));
            } else if (data.removingSelfAsInstructor) {
                return this.show_errors(
                    gettext('Error: You cannot remove yourself from the Instructor group!')
                );
            } else {
                return this.reload_list();
            }
        };

        return AuthListWidget;
    }(MemberListWidget));

    this.AutoEnrollmentViaCsv = (function() {
        function AutoEnrollmentViaCsv($container) {
            var autoenrollviacsv = this;
            this.$container = $container;
            this.$enrollment_signup_button = this.$container.find("input[name='enrollment-signup-button']");
            this.$students_list_file = this.$container.find("input[name='auto_enroll_students_list']")[0];
            this.$csrf_token = this.$container.find("input[name='csrfmiddlewaretoken']");
            this.$results = this.$container.find('#register-enroll-results');
            this.$browse_button = this.$container.find('#browseBtn-auto-enroll');
            this.$browse_file = this.$container.find('#browseFile');
            this.$progress_bar = this.$container.find('.progress-bar');
            this.$file_size = this.$container.find('.file-size');
            this.$file_name = this.$container.find('.file-name');
            this.processing = false;
            this.$browse_button.on('change', function(event) {
                if (event.currentTarget.files.length === 1) {
                    autoenrollviacsv.activeFiles = autoenrollviacsv.$browse_button[0].files;
                    autoenrollviacsv.refreshFileInfo();
                    return autoenrollviacsv.$browse_file.val(
                        event.currentTarget.value.substring(event.currentTarget.value.lastIndexOf('\\') + 1)
                    );
                }
                return false;
            });
            this.$enrollment_signup_button.click(function(event) {
                var data;
                if (autoenrollviacsv.processing) {
                    return false;
                }
                autoenrollviacsv.processing = true;
                event.preventDefault();
                data = new FormData();
                if (autoenrollviacsv.activeFiles && autoenrollviacsv.activeFiles.length>0) {
                    data.append('students_list', autoenrollviacsv.activeFiles[0]);
                }
                var $target = startLoading(event);
                return $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: $(event.target).data('endpoint'),
                    data: data,
                    processData: false,
                    contentType: false,
                    success: function(responsedata) {
                        removeLoading($target)();
                        autoenrollviacsv.processing = false;
                        return autoenrollviacsv.display_response(responsedata, $(event.target).data('action'));
                    },
                    xhr: function() {
                        var xhr = new window.XMLHttpRequest();

                        xhr.upload.addEventListener("progress", function(evt) {
                          if (evt.lengthComputable) {
                            var percentComplete = evt.loaded / evt.total;
                            percentComplete = parseInt(percentComplete * 100);
                            autoenrollviacsv.$progress_bar.find('i').width(percentComplete+'%');
                          }
                        }, false);

                        return xhr;
                    },
                    error: function(responsedata) {
                        removeLoading($target)();
                        autoenrollviacsv.processing = false;
                        return autoenrollviacsv.display_response(responsedata, $(event.target).data('action'));
                    }
                });
            });

            this.initAdditionalFileUploader();

        }

        AutoEnrollmentViaCsv.prototype.refreshFileInfo = function() {
            var fileSize = (this.activeFiles[0].size/1000).toFixed(3);
            this.$file_size.text(fileSize+'KB');
            var fileName = this.activeFiles[0] ? this.activeFiles[0].name : '';
            this.$file_name.text(fileName)

            this.$progress_bar.find('i').width(0+'%');
        }

        AutoEnrollmentViaCsv.prototype.initAdditionalFileUploader = function() {
            var $form = this.$container;
            var form = $form[0];
            const stopEvent = function (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            'drag dragstart dragend dragover dragenter dragleave drop'.split(' ').forEach(function(eventName) {
                form.addEventListener(eventName, stopEvent, false)
            })

            form.addEventListener('drop', function(e) {
                var droppedFiles = e.dataTransfer.files;
                autoenrollviacsv.activeFiles = droppedFiles;
                autoenrollviacsv.refreshFileInfo();
            });

            'dragover dragenter'.split(' ').forEach(function(eventName) {
                form.addEventListener(eventName, function() {
                    $form.addClass('draghovering')
                });
            })
            'dragleave dragend drop'.split(' ').forEach(function(eventName) {
                form.addEventListener(eventName, function() {
                    $form.removeClass('draghovering')
                });
            })

        }


        AutoEnrollmentViaCsv.prototype.display_response = function(dataFromServer, action) {
            var renderResponse,
                displayResponse = this;
            this.$results.empty();

            renderResponse = function(title, message, type, studentResults) {
                var details, responseMessage, studentResult, l, len3;
                details = [];
                for (l = 0, len3 = studentResults.length; l < len3; l++) {
                    studentResult = studentResults[l];
                    details.push(studentResult.response);
                }
                return edx.HtmlUtils.append(displayResponse.$results,
                    edx.HtmlUtils.HTML(displayResponse.render_notification_view(type, title, message, details))
                );
            };

            if (dataFromServer.general_errors.length) {
                renderResponse(gettext('Errors'), "", 'error', dataFromServer.general_errors);
            }

            if (dataFromServer.row_errors.length) {
                renderResponse(gettext('Errors'), "", 'error', dataFromServer.row_errors);
            }

            if (action == 'precheck') {
                if (dataFromServer.general_errors.length == 0 && dataFromServer.row_errors.length == 0) {
                    renderResponse(gettext('CSV file ready for upload'), "", 'confirmation', []);
                }
            }
            if (action == "register-enroll") {
                if (dataFromServer.created_and_enrolled.length) {
                    renderResponse(gettext('Users successfully created and enrolled:'),
                        "", 'confirmation', dataFromServer.created_and_enrolled);
                }

                if (dataFromServer.only_enrolled.length) {
                    renderResponse(gettext('Registered users now enrolled in this course:',
                        "", 'confirmation', dataFromServer.only_enrolled));
                }

                if (dataFromServer.untouched.length) {
                    renderResponse(gettext('Registered users who were already enrolled (no changes):'),
                        "", 'confirmation', dataFromServer.untouched);
                }
            }

            return false;
        };

        AutoEnrollmentViaCsv.prototype.render_notification_view = function(type, title, message, details) {
            var notificationModel, view;
            notificationModel = new NotificationModel();
            notificationModel.set({
                type: type,
                title: title,
                message: message,
                details: details
            });
            view = new NotificationView({
                model: notificationModel
            });
            view.render();
            return view.$el.html();
        };

        return AutoEnrollmentViaCsv;
    }());

    this.AutoUpdateViaCsv = (function() {
        function AutoUpdateViaCsv($container) {
            var autoupdateviacsv = this;
            this.$container = $container;
            this.$update_button = this.$container.find("input[name='update_button']");
            this.$students_list_file = this.$container.find("input[name='auto_update_students_list']")[0];
            this.$csrf_token = this.$container.find("input[name='csrfmiddlewaretoken']");
            this.$results = this.$container.find('#update-results');
            this.$browse_button = this.$container.find('#browseBtn-auto-update');
            this.$browse_file = this.$container.find('#browseFileUpdate');
            this.$progress_bar = this.$container.find('.progress-bar');
            this.$file_size = this.$container.find('.file-size');
            this.$file_name = this.$container.find('.file-name');
            this.processing = false;
            this.$browse_button.on('change', function(event)  {
                if (event.currentTarget.files.length === 1) {
                    autoupdateviacsv.activeFiles = autoupdateviacsv.$browse_button[0].files;
                    autoupdateviacsv.refreshFileInfo();
                    return autoupdateviacsv.$browse_file.val(
                        event.currentTarget.value.substring(event.currentTarget.value.lastIndexOf('\\') + 1)
                    );
                }
                return false;
            });
            this.$update_button.click(function(event) {
                var data;
                if (autoupdateviacsv.processing) {
                    return false;
                }
                autoupdateviacsv.processing = true;
                event.preventDefault();
                data = new FormData();
                if (autoupdateviacsv.activeFiles && autoupdateviacsv.activeFiles.length>0) {
                    data.append('students_list', autoupdateviacsv.activeFiles[0]);
                }
                var $target = startLoading(event);
                return $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: $(event.target).data('endpoint'),
                    data: data,
                    processData: false,
                    contentType: false,
                    success: function(responsedata) {
                        autoupdateviacsv.processing = false;
                        removeLoading($target)();
                        return autoupdateviacsv.display_response(responsedata, $(event.target).data('action'));
                    },
                    xhr: function() {
                        var xhr = new window.XMLHttpRequest();

                        xhr.upload.addEventListener("progress", function(evt) {
                          if (evt.lengthComputable) {
                            var percentComplete = evt.loaded / evt.total;
                            percentComplete = parseInt(percentComplete * 100);
                            autoupdateviacsv.$progress_bar.find('i').width(percentComplete+'%');
                          }
                        }, false);

                        return xhr;
                    },
                    error: function(responsedata) {
                        autoupdateviacsv.processing = false;
                        removeLoading($target)();
                        return autoupdateviacsv.display_response(responsedata, $(event.target).data('action'));
                    }
                });
            });
            this.initAdditionalFileUploader();
        }

        AutoUpdateViaCsv.prototype.refreshFileInfo = function() {
            var fileSize = (this.activeFiles[0].size/1000).toFixed(3);
            this.$file_size.text(fileSize+'KB');
            var fileName = this.activeFiles[0] ? this.activeFiles[0].name : '';
            this.$file_name.text(fileName)

            this.$progress_bar.find('i').width(0+'%');
        }

        AutoUpdateViaCsv.prototype.initAdditionalFileUploader = function() {
            var $form = this.$container;
            var form = $form[0];
            const stopEvent = function (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            'drag dragstart dragend dragover dragenter dragleave drop'.split(' ').forEach(function(eventName) {
                form.addEventListener(eventName, stopEvent, false)
            })

            form.addEventListener('drop', function(e) {
                var droppedFiles = e.dataTransfer.files;
                autoupdateviacsv.activeFiles = droppedFiles;
                autoupdateviacsv.refreshFileInfo();
            });

            'dragover dragenter'.split(' ').forEach(function(eventName) {
                form.addEventListener(eventName, function() {
                    $form.addClass('draghovering')
                });
            })
            'dragleave dragend drop'.split(' ').forEach(function(eventName) {
                form.addEventListener(eventName, function() {
                    $form.removeClass('draghovering')
                });
            })

        }

        AutoUpdateViaCsv.prototype.display_response = function(dataFromServer, action) {
            var renderResponse,
                displayResponse = this;
            this.$results.empty();

            renderResponse = function(title, message, type, studentResults) {
                var details, responseMessage, studentResult, l, len3;
                details = [];
                for (l = 0, len3 = studentResults.length; l < len3; l++) {
                    studentResult = studentResults[l];
                    details.push(studentResult.response);
                }
                return edx.HtmlUtils.append(displayResponse.$results,
                    edx.HtmlUtils.HTML(displayResponse.render_notification_view(type, title, message, details))
                );
            };

            if (dataFromServer.general_errors.length) {
                renderResponse(gettext('Errors'), "", 'error', dataFromServer.general_errors);
            }

            if (dataFromServer.row_errors.length) {
                renderResponse(gettext('Errors'), "", 'error', dataFromServer.row_errors);
            }

            if (dataFromServer.updated.length) {
                renderResponse(gettext('User accounts successfully updated:'),
                    "", 'confirmation', dataFromServer.updated);
            }

            return false;
        };

        AutoUpdateViaCsv.prototype.render_notification_view = function(type, title, message, details) {
            var notificationModel, view;
            notificationModel = new NotificationModel();
            notificationModel.set({
                type: type,
                title: title,
                message: message,
                details: details
            });
            view = new NotificationView({
                model: notificationModel
            });
            view.render();
            return view.$el.html();
        };

        return AutoUpdateViaCsv;

    }());

    BetaTesterBulkAddition = (function() {
        function betaTesterBulkAddition($container) {
            var betatest = this;
            this.$container = $container;
            this.$identifier_input = this.$container.find("textarea[name='student-ids-for-beta']");
            this.$btn_beta_testers = this.$container.find("input[name='beta-testers']");
            this.$checkbox_autoenroll = this.$container.find("input[name='auto-enroll-beta']");
            this.$checkbox_emailstudents = this.$container.find("input[name='email-students-beta']");
            this.$task_response = this.$container.find('.request-response');
            this.$request_response_error = this.$container.find('.request-response-error');
            this.clear_responses();

            this.$btn_beta_testers.click(function(event) {
                var autoEnroll, sendData;
                emailStudents = betatest.$checkbox_emailstudents.is(':checked');
                autoEnroll = betatest.$checkbox_autoenroll.is(':checked');
                sendData = {
                    action: $(event.target).data('action'),
                    identifiers: betatest.$identifier_input.val(),
                    email_students: emailStudents,
                    auto_enroll: autoEnroll
                };
                var $target = startLoading(event);
                return $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: betatest.$btn_beta_testers.data('endpoint'),
                    data: sendData,
                    success: function(data) {
                        removeLoading($target)();
                        return betatest.display_response(data);
                    },
                    error: statusAjaxError(function() {
                        removeLoading($target)();
                        return betatest.fail_with_error(gettext('Error adding/removing users as beta testers.'));
                    })
                });
            });
        }

        betaTesterBulkAddition.prototype.clear_input = function() {
            this.$identifier_input.val('');
            this.$checkbox_emailstudents.attr('checked', true);
            return this.$checkbox_autoenroll.attr('checked', true);
        };

        betaTesterBulkAddition.prototype.clear_responses = function() {
            this.$task_response.empty();
            this.$request_response_error.empty();
            return this.$request_response_error.css({display: 'none'});
        }

        betaTesterBulkAddition.prototype.fail_with_error = function(msg) {
            this.clear_input();
            this.$task_response.empty();
            this.$request_response_error.empty();
            this.$request_response_error.text(msg);
            return this.$request_response_error.css({display: 'block'});
        };

        betaTesterBulkAddition.prototype.display_response = function(dataFromServer) {
            var errors, noUsers, renderList, sr, studentResults, successes, i, len, ref,
                displayResponse = this;
            this.clear_input();
            this.clear_responses();
            errors = [];
            successes = [];
            noUsers = [];
            ref = dataFromServer.results;
            for (i = 0, len = ref.length; i < len; i++) {
                studentResults = ref[i];
                if (studentResults.userDoesNotExist) {
                    noUsers.push(studentResults);
                } else if (studentResults.error) {
                    errors.push(studentResults);
                } else {
                    successes.push(studentResults);
                }
            }
            renderList = function(label, ids) {
                var identifier, $idsList, $taskResSection, j, len1;
                $taskResSection = $('<div/>', {
                    class: 'request-res-section'
                });
                $taskResSection.append($('<h3/>', {
                    text: label
                }));
                $idsList = $('<ul/>');
                $taskResSection.append($idsList);
                for (j = 0, len1 = ids.length; j < len1; j++) {
                    identifier = ids[j];
                    $idsList.append($('<li/>', {
                        text: identifier
                    }));
                }
                return displayResponse.$task_response.append($taskResSection);
            };
            if (successes.length && dataFromServer.action === 'add') {
                var j, len1, inActiveUsers, activeUsers; // eslint-disable-line vars-on-top
                activeUsers = [];
                inActiveUsers = [];
                for (j = 0, len1 = successes.length; j < len1; j++) {
                    sr = successes[j];
                    if (sr.is_active) {
                        activeUsers.push(sr.identifier);
                    } else {
                        inActiveUsers.push(sr.identifier);
                    }
                }
                if (activeUsers.length) {
                    // Translators: A list of users appears after this sentence;
                    renderList(gettext('These users were successfully added as beta testers:'), activeUsers);
                }
                if (inActiveUsers.length) {
                    // Translators: A list of users appears after this sentence;
                    renderList(gettext(
                        'These users could not be added as beta testers because their accounts are not yet activated:'),
                        inActiveUsers);
                }
            }
            if (successes.length && dataFromServer.action === 'remove') {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('These users were successfully removed as beta testers:'), (function() {
                    var j, len1, results;
                    results = [];
                    for (j = 0, len1 = successes.length; j < len1; j++) {
                        sr = successes[j];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (errors.length && dataFromServer.action === 'add') {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('These users were not added as beta testers:'), (function() {
                    var j, len1, results;
                    results = [];
                    for (j = 0, len1 = errors.length; j < len1; j++) {
                        sr = errors[j];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (errors.length && dataFromServer.action === 'remove') {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('These users were not removed as beta testers:'), (function() {
                    var j, len1, results;
                    results = [];
                    for (j = 0, len1 = errors.length; j < len1; j++) {
                        sr = errors[j];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (noUsers.length) {
                noUsers.push($(
                    gettext('Users must create and activate their account before they can be promoted to beta tester.'))
                );
                return renderList(gettext('Could not find users associated with the following identifiers:'), (function() { // eslint-disable-line max-len
                    var j, len1, results;
                    results = [];
                    for (j = 0, len1 = noUsers.length; j < len1; j++) {
                        sr = noUsers[j];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            return renderList();
        };
        return betaTesterBulkAddition;
    }());

    BatchEnrollment = (function() {
        function batchEnrollment($container) {
            var batchEnroll = this;
            this.$container = $container;
            this.$identifier_input = this.$container.find("textarea[name='student-ids']");
            this.$role = this.$container.find("select[name='role']");
            this.$enrollment_button = this.$container.find('.enrollment-button');
            this.$reason_field = this.$container.find("textarea[name='reason-field']");
            this.$checkbox_autoenroll = this.$container.find("input[name='auto-enroll']");
            this.$checkbox_emailstudents = this.$container.find("input[name='email-students']");
            this.checkbox_emailstudents_initialstate = this.$checkbox_emailstudents.is(':checked');
            this.$task_response = this.$container.find('.request-response');
            this.$request_response_error = this.$container.find('.request-response-error');
            this.clear_responses();

            this.$enrollment_button.click(function(event) {
                var sendData;
                if (!batchEnroll.$reason_field.val()) {
                    batchEnroll.$reason_field.val('');
                }
                if (!batchEnroll.$role.val()) {
                    batchEnroll.fail_with_error(gettext('Role field should not be left unselected.'));
                    return false;
                }

                emailStudents = batchEnroll.$checkbox_emailstudents.is(':checked');
                sendData = {
                    action: $(event.target).data('action'),
                    identifiers: batchEnroll.$identifier_input.val(),
                    role: batchEnroll.$role.val(),
                    auto_enroll: batchEnroll.$checkbox_autoenroll.is(':checked'),
                    email_students: emailStudents,
                    reason: batchEnroll.$reason_field.val()
                };
                var $target = startLoading(event);
                return $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: $(event.target).data('endpoint'),
                    data: sendData,
                    success: function(data) {
                        removeLoading($target)();
                        return batchEnroll.display_response(data);
                    },
                    error: statusAjaxError(function() {
                        removeLoading($target)();
                        return batchEnroll.fail_with_error(gettext('Error enrolling/unenrolling users.'));
                    })
                });
            });
        }

        batchEnrollment.prototype.clear_input = function() {
            this.$identifier_input.val('');
            this.$reason_field.val('');
            this.$checkbox_emailstudents.attr('checked', this.checkbox_emailstudents_initialstate);
            return this.$checkbox_autoenroll.attr('checked', true);
        };

        batchEnrollment.prototype.clear_responses = function() {
            this.$task_response.empty();
            this.$request_response_error.empty();
            return this.$request_response_error.css({display: 'none'});
        }

        batchEnrollment.prototype.fail_with_error = function(msg) {
            this.clear_input();
            this.$task_response.empty();
            this.$request_response_error.empty();
            this.$request_response_error.text(msg)
            return this.$request_response_error.css({display: 'block'});
        };

        batchEnrollment.prototype.display_response = function(dataFromServer) {
            var allowed, autoenrolled, enrolled, errors, errorsLabel,
                invalidIdentifier, partialUnenrollIdentifier, notenrolled, notunenrolled, renderList, sr, studentResults,
                i, j, len, len1, ref, renderIdsLists,
                displayResponse = this;
            this.clear_input();
            this.clear_responses();
            invalidIdentifier = [];
            partialUnenrollIdentifier = [];
            errors = [];
            enrolled = [];
            allowed = [];
            autoenrolled = [];
            notenrolled = [];
            notunenrolled = [];
            ref = dataFromServer.results;
            for (i = 0, len = ref.length; i < len; i++) {
                studentResults = ref[i];
                if (studentResults.invalidIdentifier) {
                    invalidIdentifier.push(studentResults);
                } else if (studentResults.partialUnenrollIdentifier) {
                    partialUnenrollIdentifier.push(studentResults);
                } else if (studentResults.error) {
                    errors.push(studentResults);
                } else if (studentResults.after.enrollment) {
                    enrolled.push(studentResults);
                } else if (studentResults.after.allowed) {
                    if (studentResults.after.auto_enroll) {
                        autoenrolled.push(studentResults);
                    } else {
                        allowed.push(studentResults);
                    }
                } else if (dataFromServer.action === 'unenroll' &&
                      !studentResults.before.enrollment &&
                      !studentResults.before.allowed) {
                    notunenrolled.push(studentResults);
                } else if (!studentResults.after.enrollment) {
                    notenrolled.push(studentResults);
                } else {
                    console.warn('learner results not reported to user');  // eslint-disable-line no-console
                }
            }
            renderList = function(label, ids) {
                var identifier, $idsList, $taskResSection, h, len3;
                $taskResSection = $('<div/>', {
                    class: 'request-res-section'
                });
                $taskResSection.append($('<h3/>', {
                    text: label
                }));
                $idsList = $('<ul/>');
                $taskResSection.append($idsList);
                for (h = 0, len3 = ids.length; h < len3; h++) {
                    identifier = ids[h];
                    $idsList.append($('<li/>', {
                        text: identifier
                    }));
                }
                return displayResponse.$task_response.append($taskResSection);
            };
            if (invalidIdentifier.length) {
                renderList(gettext('The following email addresses and/or usernames are invalid:'), (function() {
                    var m, len4, results;
                    results = [];
                    for (m = 0, len4 = invalidIdentifier.length; m < len4; m++) {
                        sr = invalidIdentifier[m];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (partialUnenrollIdentifier.length) {
                renderList(gettext('The following email addresses and/or usernames are needed to unenroll from learning path(s) first:'), (function() {
                    var m, len4, results;
                    results = [];
                    for (m = 0, len4 = partialUnenrollIdentifier.length; m < len4; m++) {
                        sr = partialUnenrollIdentifier[m];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (errors.length) {
                errorsLabel = (function() {
                    if (dataFromServer.action === 'enroll') {
                        return 'There was an error enrolling:';
                    } else if (dataFromServer.action === 'unenroll') {
                        return 'There was an error unenrolling:';
                    } else {
                        console.warn("unknown action from server '" + dataFromServer.action + "'");  // eslint-disable-line no-console, max-len
                        return 'There was an error processing:';
                    }
                }());
                renderIdsLists = function(errs) {
                    var srItem,
                        k = 0,
                        results = [];
                    for (k = 0, len = errs.length; k < len; k++) {
                        srItem = errs[k];
                        results.push(srItem.identifier);
                    }
                    return results;
                };
                for (j = 0, len1 = errors.length; j < len1; j++) {
                    studentResults = errors[j];
                    renderList(errorsLabel, renderIdsLists(errors));
                }
            }
            if (enrolled.length && emailStudents) {
                renderList(gettext('Successfully enrolled and sent email to the following users:'), (function() {
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = enrolled.length; k < len2; k++) {
                        sr = enrolled[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (enrolled.length && !emailStudents) {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('Successfully enrolled the following users:'), (function() {
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = enrolled.length; k < len2; k++) {
                        sr = enrolled[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (allowed.length && emailStudents) {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('Successfully sent enrollment emails to the following users. They will be allowed to enroll once they register:'), (function() {  // eslint-disable-line max-len
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = allowed.length; k < len2; k++) {
                        sr = allowed[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (allowed.length && !emailStudents) {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('These users will be allowed to enroll once they register:'), (function() {
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = allowed.length; k < len2; k++) {
                        sr = allowed[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (autoenrolled.length && emailStudents) {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('Successfully sent enrollment emails to the following users. They will be enrolled once they register:'), (function() {  // eslint-disable-line max-len
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = autoenrolled.length; k < len2; k++) {
                        sr = autoenrolled[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (autoenrolled.length && !emailStudents) {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('These users will be enrolled once they register:'), (function() {
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = autoenrolled.length; k < len2; k++) {
                        sr = autoenrolled[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (notenrolled.length && emailStudents) {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('Emails successfully sent. The following users are no longer enrolled in the course:'), (function() {  // eslint-disable-line max-len
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = notenrolled.length; k < len2; k++) {
                        sr = notenrolled[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (notenrolled.length && !emailStudents) {
                // Translators: A list of users appears after this sentence;
                renderList(gettext('The following users are no longer enrolled in the course:'), (function() {
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = notenrolled.length; k < len2; k++) {
                        sr = notenrolled[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            if (notunenrolled.length) {
                return renderList(gettext('These users were not affiliated with the course so could not be unenrolled:'), (function() {  // eslint-disable-line max-len
                    var k, len2, results;
                    results = [];
                    for (k = 0, len2 = notunenrolled.length; k < len2; k++) {
                        sr = notunenrolled[k];
                        results.push(sr.identifier);
                    }
                    return results;
                }()));
            }
            return renderList();
        };

        return batchEnrollment;
    }());

    SendWelcomingEmail = (function() {
        function sendWelcomingEmail($container) {
            var sendEmail = this;
            this.$container = $container;
            this.$emails_textarea = this.$container.find("textarea[name='student-emails-for-welcoming']");
            this.$submit_button = this.$container.find("input[name='send-welcoming-email_button']");
            this.$results = this.$container.find("div.results");

            this.$submit_button.click(function(event) {
                var sendData = {
                    emails: sendEmail.$emails_textarea.val(),
                };
                var $target = startLoading(event);
                return $.ajax({
                    dataType: 'json',
                    type: 'POST',
                    url: sendEmail.$submit_button.data('endpoint'),
                    data: sendData,
                    success: function(data) {
                        removeLoading($target)();
                        return sendEmail.display_response(data);
                    },
                });
            });
        }

        sendWelcomingEmail.prototype.clear_input = function() {
            return this.$emails_textarea.val('');
        };

        sendWelcomingEmail.prototype.display_response = function(dataFromServer) {
            this.clear_input();
            this.$results.empty();
            var title;

            if (dataFromServer.row_errors.length) {
                title = gettext('The following email addresses are invalid:')
                this.$results.append(this.render_notification_view('error', title, dataFromServer.row_errors))
            }

            if (dataFromServer.row_successes.length) {
                title = gettext("Successfully sent welcoming emails to the following addresses:")
                this.$results.append(this.render_notification_view('confirmation', title, dataFromServer.row_successes))
            }
        };

        sendWelcomingEmail.prototype.render_notification_view = function(type, title, email_addresses) {
            var notification_model, view;
            notification_model = new NotificationModel();
            notification_model.set({
                type: type,
                title: title,
                details: email_addresses,
            });
            view = new NotificationView({
                model: notification_model
            });
            view.render();
            return view.$el.html();
        };

        return sendWelcomingEmail;
    }());

    this.AuthList = (function() {
        function authList($container, rolename) {
            var authlist = this;
            this.$container = $container;
            this.rolename = rolename;
            this.$display_table = this.$container.find('.auth-list-table');
            this.$request_response_error = this.$container.find('.request-response-error');
            this.$request_response_error.css({display: 'none'});
            this.$add_section = this.$container.find('.auth-list-add');
            this.$allow_field = this.$add_section.find("input[name='email']");
            this.$allow_button = this.$add_section.find("input[name='allow']");
            this.$allow_button.click(function() {
                authlist.access_change(authlist.$allow_field.val(), 'allow', function() {
                    return authlist.reload_auth_list();
                });
                return authlist.$allow_field.val('');
            });
            this.reload_auth_list();
        }

        authList.prototype.reload_auth_list = function() {
            var loadAuthList,
                ths = this;
            loadAuthList = function(data) {
                var $tablePlaceholder, WHICH_CELL_IS_REVOKE, columns, grid, options, tableData;
                ths.$request_response_error.empty();
                ths.$request_response_error.css({display: 'none'});
                ths.$display_table.empty();
                options = {
                    enableCellNavigation: true,
                    enableColumnReorder: false,
                    forceFitColumns: true
                };
                WHICH_CELL_IS_REVOKE = 3;
                columns = [
                    {
                        id: 'username',
                        field: 'username',
                        name: 'Username'
                    }, {
                        id: 'email',
                        field: 'email',
                        name: 'Email'
                    }, {
                        id: 'first_name',
                        field: 'first_name',
                        name: 'First Name'
                    }, {
                        id: 'revoke',
                        field: 'revoke',
                        name: 'Revoke',
                        formatter: function() {
                            return "<span class='revoke-link'>Revoke Access</span>";
                        }
                    }
                ];
                tableData = data[ths.rolename];
                $tablePlaceholder = $('<div/>', {
                    class: 'slickgrid'
                });
                ths.$display_table.append($tablePlaceholder);
                grid = new window.Slick.Grid($tablePlaceholder, tableData, columns, options);
                return grid.onClick.subscribe(function(e, args) {
                    var item;
                    item = args.grid.getDataItem(args.row);
                    if (args.cell === WHICH_CELL_IS_REVOKE) {
                        return ths.access_change(item.email, 'revoke', function() {
                            return ths.reload_auth_list();
                        });
                    }
                    return false;
                });
            };
            return $.ajax({
                dataType: 'json',
                type: 'POST',
                url: this.$display_table.data('endpoint'),
                data: {
                    rolename: this.rolename
                },
                success: loadAuthList,
                error: statusAjaxError(function() {
                    ths.$request_response_error.text("Error fetching list for '" + ths.rolename + "'");
                    return ths.$request_response_error.css({display: 'block'});
                })
            });
        };

        authList.prototype.refresh = function() {
            this.$display_table.empty();
            return this.reload_auth_list();
        };

        authList.prototype.access_change = function(email, action, cb) {
            var ths = this;
            return $.ajax({
                dataType: 'json',
                type: 'POST',
                url: this.$add_section.data('endpoint'),
                data: {
                    email: email,
                    rolename: this.rolename,
                    action: action
                },
                success: function(data) {
                    return typeof cb === 'function' ? cb(data) : undefined;
                },
                error: statusAjaxError(function() {
                    ths.$request_response_error.text(gettext("Error changing user's permissions."));
                    return ths.$request_response_error.css({display: 'block'});
                })
            });
        };

        return authList;
    }());

    Membership = (function() {
        function membership($section) {
            var authList, i, len, ref,
                thismembership = this;
            this.$section = $section;
            this.$section.data('wrapper', this);
            plantTimeout(0, function() {
                return new BatchEnrollment(thismembership.$section.find('.batch-enrollment'));
            });
            plantTimeout(0, function() {
                return new SendWelcomingEmail(thismembership.$section.find('.auto_send_welcoming_email'));
            });
            plantTimeout(0, function() {
                return new AutoEnrollmentViaCsv(thismembership.$section.find('.auto_enroll_csv'));
            });
            plantTimeout(0, function() {
                return new AutoUpdateViaCsv(thismembership.$section.find('.auto_update_csv'));
            });
            plantTimeout(0, function() {
                return new BetaTesterBulkAddition(thismembership.$section.find('.batch-beta-testers'));
            });
            this.$list_selector = this.$section.find('select#member-lists-selector');
            this.$auth_list_containers = this.$section.find('.auth-list-container');
            this.$auth_list_errors = this.$section.find('.member-lists-management .request-response-error');

            this.auth_lists = _.map(this.$auth_list_containers, function(authListContainer) {
                var rolename;
                rolename = $(authListContainer).data('rolename');
                return new AuthListWidget($(authListContainer), rolename, thismembership.$auth_list_errors);
            });
            this.$list_selector.empty();
            ref = this.auth_lists;
            for (i = 0, len = ref.length; i < len; i++) {
                authList = ref[i];
                this.$list_selector.append($('<option/>', {
                    text: authList.$container.data('display-name'),
                    value: authList.rolename,
                    data: {
                        auth_list: authList
                    }
                }));
            }
            if (this.auth_lists.length === 0) {
                this.$list_selector.hide();
            }
            this.$list_selector.change(function() {
                var $opt, j, len1, ref1;
                $opt = thismembership.$list_selector.children('option:selected');
                if (!($opt.length > 0)) {
                    return;
                }
                ref1 = thismembership.auth_lists;
                for (j = 0, len1 = ref1.length; j < len1; j++) {
                    authList = ref1[j];
                    authList.$container.removeClass('active');
                }
                authList = $opt.data('auth_list');
                authList.$container.addClass('active');
                authList.re_view();

                // On Change update the Group Moderation list
                if ($opt[0].value === 'Group Moderator') {
                    if (!authList.list_enabled) {
                        authList.show_errors(gettext('This role requires a divided discussions scheme.'));
                        enableAddButton(false, authList);
                    } else {
                        enableAddButton(true, authList);
                    }
                }
            });
            this.$list_selector.change();
        }

        membership.prototype.onClickTitle = function() {
            var list;
            // When the title is clicked refresh all the authorization lists as the member list
            // may have changed since render.
            for (list = 0; list < this.auth_lists.length; list++) {
                this.auth_lists[list].re_view();
            }
        };

        return membership;
    }());

    _.defaults(window, {
        InstructorDashboard: {}
    });

    _.defaults(window.InstructorDashboard, {
        sections: {}
    });

    _.defaults(window.InstructorDashboard.sections, {
        Membership: Membership
    });
}).call(this);
