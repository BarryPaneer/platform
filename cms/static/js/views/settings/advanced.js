define(['js/views/validation',
        'jquery',
        'underscore',
        'gettext',
        'codemirror',
        'js/views/modals/validation_error_modal',
        'edx-ui-toolkit/js/utils/html-utils'],
    function (ValidatingView, $, _, gettext, CodeMirror, ValidationErrorModal, HtmlUtils) {
        var AdvancedView = ValidatingView.extend({
            error_saving: 'error_saving',
            successful_changes: 'successful_changes',
            render_deprecated: false,

            // Model class is CMS.Models.Settings.Advanced
            events: {
                'focus :input': 'focusInput',
                'blur :input': 'blurInput'
                // TODO enable/disable save based on validation (currently enabled whenever there are changes)
            },
            initialize: function () {
                this.advancedGroup = arguments[0].advancedGroup;
                this.anderspinkBoardsList = arguments[0].anderspinkBoardsList;
                // console.log('this.advancedGroup', this.advancedGroup)
                this.template = HtmlUtils.template(
                    $('#advanced_entry-tpl').text()
                );
                this.listenTo(this.model, 'invalid', this.handleValidationError);
                this.render();

            },
            render: function () {
                // catch potential outside call before template loaded
                if (!this.template) return this;

                var listEle$ = this.$el.find('.course-advanced-policy-list');
                listEle$.empty();

                // b/c we've deleted all old fields, clear the map and repopulate
                this.fieldToSelectorMap = {};
                this.selectorToField = {};

                // iterate through model and produce key : value editors for each property in model.get
                var self = this;

                const defaultGroup = [
                    {
                        "name":"Basic Information",
                        "items":[ "display_coursenumber" ]
                    },
                    {
                        "name":"Schedule Your course",
                        "items":[ "advertised_start", "announcement", "days_early_for_beta", {key:"course_category", componentType:"dropdown"} ]
                    },
                    {
                        "name":"Target Your Learners",
                        "items":[{key:"invitation_only", componentType:"switcher"}, "max_student_enrollments_allowed", "enrollment_domain",
                        {key:"mobile_available", componentType:"switcher"} ]
                    },
                    {
                        "name":"Content",
                        "items":[{key:"enable_subsection_gating", componentType:"switcher"}, {key:"advanced_modules", componentType:"checkboxgroup"}, "static_asset_path",
                            {key:"video_auto_advance", componentType:"switcher"}, {key:"video_speed_optimizations", componentType:"switcher"},
                            {key:"show_calculator", componentType:"dropdown"}, "matlab_api_key", "lti_passporpxts", "annotation_token_secret",
                            "annotation_storage_url"]
                    },
                    {
                        "name":"Graded Activities",
                        "items":["max_attempts", {key:"showanswer", componentType:"dropdown"}, {key:"showanswer", componentType:"dropdown"},
                            {key:"show_reset_button", componentType:"switcher"}, {key:"enable_timed_exams", componentType:"switcher"},
                            {key:"rerandomize", componentType:"dropdown"}, {key:"enable_proctored_exams", componentType:"switcher"},
                            {key:"allow_proctoring_opt_out", componentType:"switcher"}, "due", "due_date_display_format", "teams_configuration",
                            {key:"create_zendesk_tickets", componentType:"switcher"},"remote_gradebook" ]
                    },
                    {
                        "name":"Certificates",
                        "items":[ {key:"certificates_display_behavior", componentType:"dropdown"} ]
                    },
                    {
                        "name":"Discussions",
                        "items":[ {key:"allow_anonymous", componentType:"switcher"}, {key:"allow_anonymous_to_peers", componentType:"switcher"}, {key:"discussion_blackouts", componentType:"dropdown"}, {key:"discussion_sort_alpha", componentType:"switcher"}, "discussion_topics" ]
                    },
                    {
                        "name":"Pages",
                        "items":["html_textbooks", {key:"anderspink_boards", componentType:"dropdown"}]
                    },
                    {
                        "name":"Wiki",
                        "items":[ {key:"allow_public_wiki_access", componentType:"switcher"} ]
                    }
                ];

                if(this.anderspinkBoardsList.length == 0 ){   
                    defaultGroup.find(f => f.name == "Pages").items.splice(1,1)
                }

                var TEAM_CONFIG = this.advancedGroup || defaultGroup

                _.each(TEAM_CONFIG, function(configItem){
                    var $teamFieldEl = $('<li class="team-field"><h4>'+ gettext(configItem.name) +'</h4><ul></ul></li>');
                    listEle$.append($teamFieldEl);
                    _.each(configItem.items, $.proxy(function(item){
                        var key = '', componentType = '';
                        if (typeof(item) == 'object'){
                            key = item.key;
                            componentType = item.componentType
                        }else{
                            key = item;
                        }
                        if (self.render_deprecated || !self.model.get(key).deprecated) {
                            /*if (key == 'advanced_modules') {
                                debugger
                            }*/
                            var $newEl = $(self.renderTemplate(key, self.model.get(key), componentType));
                            var $ul = HtmlUtils.append($teamFieldEl.find('>ul'), $newEl[0]);
                            if (componentType == 'checkboxgroup') {
                                var model = self.model.get(key);
                                self.initializeCheckboxGroup($ul.children().last(), model)
                            }
                        }
                    }, self))
                });

                var policyValues = listEle$.find('.json');
                _.each(policyValues, this.attachJSONEditor, this);
                _.each($(listEle$).find('select'), function (select) {
                    $(select).change(function (event) {
                        $select = $(event.target);

                        var obj = self.model.get($select.data('name'));
                        obj['value'] = $select.val();
                        self.model.set($select.data('name'), obj);

                        if ($select.val() !== $select.data('value')) {
                            var message = gettext("Your changes will not take effect until you save your progress. Take care with key and value formatting, as validation is not implemented.");
                            self.showNotificationBar(message,
                                _.bind(self.saveView, self),
                                _.bind(self.revertView, self));
                        }
                    });
                });

                this.applyElements();
                return this;
            },
            initializeCheckboxGroup:function($element, model){
                var $checkboxGroup = $element.find('.checkboxgroup');
                var $textarea = $checkboxGroup.next();
                var checkedList = eval($textarea.val());
                var data = _.map(model.values, function(p){return({value:p, text:p})});
                new LearningTribes.CheckboxGroup($checkboxGroup[0], {
                        data: data,
                        checkedList: checkedList,
                        prefire: false,
                        onChange: $.proxy(function(checkedItems){
                            var valArr = checkedItems.map(function(item){
                                return item.value;
                            });
                            var result = '["'+ valArr.join('","') +'"]';
                            var cm = $textarea.next('.CodeMirror')[0].CodeMirror;
                                cm.setValue(result);
                            this.setModelValue(cm, valArr)

                        }, this)
                    }
                )
            },
            setModelValue:function(cm, value){
                var key = $(cm.getWrapperElement()).closest('.field-group').children('.key').attr('id');
                var modelVal = this.model.get(key);
                modelVal.value = value;
                this.model.set(key, modelVal);
            },
            applyElements:function(){
                var $el = this.$el;
                var self = this;
                var setModelValue = function(cm, value){
                    var key = $(cm.getWrapperElement()).closest('.field-group').children('.key').attr('id');
                    var modelVal = self.model.get(key);
                    modelVal.value = value;
                    self.model.set(key, modelVal);
                };
                setTimeout(function () {
                    //be remember move these code to where after render.
                    var $marks = $el.find('.question-mark-wrapper');
                    _.each($marks, function(mark){
                        new LearningTribes.QuestionMark(mark)
                    });

                    var $switchers = $el.find('.switcher');
                    _.each($switchers, function(switcher){
                        var $switcher = $(switcher);
                        var $textarea = $switcher.next();
                        new LearningTribes.Switcher(switcher, $textarea.val(), (function(textarea){
                            return function(checked){
                                var cm = $(textarea).next('.CodeMirror')[0].CodeMirror;
                                cm.setValue(checked.toString());
                                setModelValue(cm, checked.toString())
                            }
                        })($textarea[0]))
                    });
                    var $dates = $el.find('input.date');
                    _.each($dates, function(date) {
                        var $date = $(date);
                        $date.datepicker();
                        $date.on('change', function(e){
                            var val = e.currentTarget.value;
                            var cm = $date.next('textarea').next('.CodeMirror')[0].CodeMirror;
                            cm.setValue(val);
                            setModelValue(cm, val)
                        })
                    })
                }, 400)
            },
            saveValueToModel:function(){
                var modelVal = self.model.get(key);
                modelVal.value = JSONValue;
                self.model.set(key, modelVal);
            },
            attachJSONEditor: function (textarea) {
                // Since we are allowing duplicate keys at the moment, it is possible that we will try to attach
                // JSON Editor to a value that already has one. Therefore only attach if no CodeMirror peer exists.
                if ($(textarea).siblings().hasClass('CodeMirror')) {
                    return;
                }

                var self = this;
                var oldValue = $(textarea).val();
                var cm = CodeMirror.fromTextArea(textarea, {
                    mode: 'application/json',
                    lineNumbers: false,
                    lineWrapping: false
                });
                cm.on('change', function (instance, changeobj) {
                    instance.save();
                    // this event's being called even when there's no change :-(
                    if (instance.getValue() !== oldValue) {
                        var message = gettext('Your changes will not take effect until you save your progress. Take care with key and value formatting, as validation is not implemented.');
                        self.showNotificationBar(message,
                            _.bind(self.saveView, self),
                            _.bind(self.revertView, self));
                    }
                });
                cm.on('focus', function (mirror) {
                    $(textarea).parent().children('label').addClass('is-focused');
                });
                cm.on('blur', function (mirror) {
                    $(textarea).parent().children('label').removeClass('is-focused');
                    var key = $(mirror.getWrapperElement()).closest('.field-group').children('.key').attr('id');
                    var stringValue = $.trim(mirror.getValue());
                    // update CodeMirror to show the trimmed value.
                    mirror.setValue(stringValue);
                    var JSONValue = undefined;
                    try {
                        JSONValue = JSON.parse(stringValue);
                    } catch (e) {
                        // If it didn't parse, try converting non-arrays/non-objects to a String.
                        // But don't convert single-quote strings, which are most likely errors.
                        var firstNonWhite = stringValue.substring(0, 1);
                        if (firstNonWhite !== '{' && firstNonWhite !== '[' && firstNonWhite !== "'") {
                            try {
                                stringValue = '"' + stringValue + '"';
                                JSONValue = JSON.parse(stringValue);
                                mirror.setValue(stringValue);
                            } catch (quotedE) {
                                // TODO: validation error
                                // console.log("Error with JSON, even after converting to String.");
                                // console.log(quotedE);
                                JSONValue = undefined;
                            }
                        }
                    }
                    if (JSONValue !== undefined) {
                        var modelVal = self.model.get(key);
                        modelVal.value = JSONValue;
                        self.model.set(key, modelVal);
                    }
                });
            },
            saveView: function () {
                // TODO one last verification scan:
                //    call validateKey on each to ensure proper format
                //    check for dupes
                var self = this;
                this.model.save({}, {
                    success: function () {
                        var title = gettext('Your policy changes have been saved.');
                        var message = gettext('No validation is performed on policy keys or value pairs. If you are having difficulties, check your formatting.');  // eslint-disable-line max-len
                        self.render();
                        self.showSavedBar(title, message);
                        analytics.track('Saved Advanced Settings', {
                            course: course_location_analytics
                        });
                    },
                    silent: true,
                    error: function (model, response, options) {
                        var json_response, reset_callback, err_modal;

                        /* Check that the server came back with a bad request error*/
                        if (response.status === 400) {
                            json_response = $.parseJSON(response.responseText);
                            reset_callback = function () {
                                self.revertView();
                            };

                            /* initialize and show validation error modal */
                            err_modal = new ValidationErrorModal();
                            err_modal.setContent(json_response);
                            err_modal.setResetCallback(reset_callback);
                            err_modal.show();
                        }
                    }
                });
            },
            revertView: function () {
                var self = this;
                this.model.fetch({
                    success: function () {
                        self.render();
                    },
                    reset: true
                });
            },
            renderTemplate: function (key, model, componentType) {
                let values;
                if(key == "anderspink_boards" && this.anderspinkBoardsList.length > 0){
                    values = this.anderspinkBoardsList
                }
                else values = model.values
                var newKeyId = _.uniqueId('policy_key_'),
                    newEle = this.template({
                        componentType: componentType,
                        key: key, display_name: model.display_name, help: model.help,
                        value: JSON.stringify(model.value, null, 4), deprecated: model.deprecated,
                        keyUniqueId: newKeyId, valueUniqueId: _.uniqueId('policy_value_'), options: values
                    });

                this.fieldToSelectorMap[key] = newKeyId;
                this.selectorToField[newKeyId] = key;
                return newEle;
            },
            focusInput: function (event) {
                $(event.target).prev().addClass('is-focused');
            },
            blurInput: function (event) {
                $(event.target).prev().removeClass('is-focused');
            }
        });

        return AdvancedView;
    });
