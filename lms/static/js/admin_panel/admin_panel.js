
//share with other module through out admin panel feature
var NOTICE = {
    enrollConfirmation:{
        title:gettext("Enroll Confirmation Request"),
        message:gettext("Are you sure about enroll your user?")
    },
    unenrollConfirmation:{
        title:gettext("Unenroll Confirmation Request"),
        message:gettext("Are you sure you want to unenroll?")
    }
}

function user_create_edit(
    user_id,
    profile_fields,
    country_options,
    lang_options,
    date_format,
    platform_level_options,
    org_options,
    program_feature_enabled
) {

    Vue.component("switch-button", {
      template: '<div class="switch-button-control">\n' +
          '    <div class="switch-button" :class="{ enabled: isEnabled }" @click="toggle">\n' +
          '      <div class="toggle"></div>\n' +
          '    </div>\n' +
          '    <div class="switch-button-label">\n' +
          '      <slot></slot>\n' +
          '    </div>\n' +
          '  </div>',
      model: {
        prop: "isEnabled",
        event: "toggle"
      },
      props: {
        isEnabled: Boolean
      },
      methods: {
        toggle: function() {
          this.$emit("toggle", !this.isEnabled);
        }
      }
    });

    Vue.component("dropdown", {
        template: '<div class="select-wrapper"><div></div><input type="hidden" :value="$props.value"></div>',
        watch: {
          value: function(val) {
              if (this.component) {
                  this.component.setState({'selectedValue':val})
              }
          },
          data: {
              immediate: true,
              handler() {
                  if (!this.$props.data && !this.$props.data.length){
                      return false;
                  }
                  setTimeout($.proxy(function() {
                        var props = {
                            data: this.$props.data.map(function(item){
                                return {text:(item.text || item.name), value:item.value}
                            }),
                            value: this.$props.value,
                            onChange: this.handleChange,
                            searchable: true
                        }
                        this.component = ReactDOM.render(
                          React.createElement(Dropdown, props, null),
                          this.$el.firstElementChild
                        );
                  }, this), 500)

              }
          }
        },
        props: ['data', 'value', 'change'],
        methods:{
            handleChange:function(e) {
                this.$emit('change', e, e.value)
            }
        }
    });

    Vue.component('datepicker', {
        template: '<input v-bind:value="value">',
        props: ['value'],
        mounted: function () {
            const self = this;
            $(self.$el).datepicker({
                dateFormat: date_format,
                onSelect: function (date) {
                    self.$emit("input", date)
                }
            })
        }
    });

    Vue.http.interceptors.push(function (request, next) {
        if (request.method === 'POST') {
          request.headers.set('X-CSRFToken', $.cookie('csrftoken'));
        }

        next();
    })

    const creation_url = "/user_api/v1/account/admin_panel_registration/",
          user_data_url = "/user_api/v1/account/admin_panel/user/",
          search_api_url = "/user_api/v1/account/admin_panel/users/",
          delete_user_url = "/user_api/v1/account/admin_panel/delete_user/"
          update_enrollment_url = "/user_api/v1/account/admin_panel/update_enrollment/course_key/user_id/",
          year_of_birth_options = [],
          current_year = moment().year();

    for (var i = current_year; i >= 1901; i--) {
        var option = {
            name: String(i),
            value: i
        };
        year_of_birth_options.push(option)
    }

    function bleachHash (hash) {
        const validHashes = ['personal-info', 'permissions', 'bulk-registration']
        return validHashes.find(h => h === hash) || validHashes[0]
    }

    function selectedPlatformLevel () {
        // Populate list of analytics access in the second dropdown
        console.log('platform level: ' + this.platform_level)
        if (this.platform_level.length > 0) {
            if (['2', '3'].includes(this.platform_level)) {
                this.analytics_access_options = [{text:gettext('Full Access'), value:'2'}]
                this.analytics_access = '2'
            } else {
                this.analytics_access_options = [{text:gettext('None'), value:'0'},{text:gettext('Restricted'), value:'1'},{text:gettext('Full Access'), value:'2'}]
            }
        }
    }
    
    const UserData = new Vue({
        el: ".management-container",
        data: {
            activeSubTab:'enrolled',
            active_tab: 'course',
            country_options: country_options,
            lang_options: lang_options,
            genderData:[{ text:gettext('Male'), value:'m'}, { text:gettext('Female'), value:'f'}, { text:gettext('Other/Prefer Not to Say'), value:'o'}],
            analytics_access_options:[{text:gettext('None'), value:'0'},{text:gettext('Restricted'), value:'1'},{text:gettext('Full Access'), value:'2'}],
            platform_level_options: platform_level_options,
            query: "",
            search_result: [],
            show_more: false,
            origin_data: {},
            submit_data: {},
            current_user: user_id,
            profile_fields: profile_fields,
            username: "",
            email: "",
            password: "",
            password_confirm: "",
            update_password: true,
            first_name: "",
            last_name: "",
            name: "",
            gender: "",
            year_of_birth: "",
            year_of_birth_options: year_of_birth_options,
            language: "",
            country: "",
            lt_custom_country: "",
            lt_area: "",
            lt_sub_area: "",
            city: "",
            location: "",
            lt_address: "",
            lt_address_2: "",
            lt_phone_number: "",
            lt_gdpr: false,
            lt_company: "",
            lt_employee_id: "",
            lt_hire_date: "",
            lt_level: "",
            lt_job_code: "",
            lt_job_description: "",
            lt_department: "",
            lt_supervisor: "",
            lt_ilt_supervisor: "",
            mailing_address: "",
            lt_learning_group: "",
            lt_exempt_status: false,
            lt_comments: "",
            terms_of_service: "true",
            honor_code: "true",
            is_active: true,
            platform_level: "0",
            catalog_access: true,
            edflex_access: true,
            crehana_access: true,
            anderspink_access: true,
            learnlight_access: true,
            linkedin_access: true,
            udemy_access: true,
            founderz_access: true,
            siemens_access: true,
            triboo_centrical_access: true,
            analytics_access: "0",
            currently_enrolled: [],
            not_enrolled: [],
            enrollment_search: "",
            enrolled_search_result: [],
            not_enrolled_search_result: [],
            deleting_user: false,
            objects_to_delete: {},
            editting_info: false,
            editting_permissions: false,
            org: org_options[0].value,
            org_options: org_options,
            activePanel: bleachHash(window.location.hash.slice(1)),
        },
        methods: {
            selectedPlatformLevel : selectedPlatformLevel,
            ngettext: window.ngettext,
            toggleSubTab: function(e) {
                this.activeSubTab = e.target.className.includes('unenrolled') ? 'unenrolled' : 'enrolled'
            },
            save: function () {
                var submit_url = "",
                    submit_data = Object.assign({}, this.submit_data),
                    self = this,
                    action;

                if (this.username === '') {
                    $("#username").parent().addClass("required-field");
                }
                else {
                    $("#username").parent().removeClass("required-field");
                }

                if (submit_data.email === '' || this.email == "") {
                    $("#email").parent().addClass("required-field");
                }else {
                    $("#email").parent().removeClass("required-field");
                }

                if (submit_data.name === '' || this.name === '') {
                    $("#name").parent().addClass("required-field");
                } else {
                    $("#name").parent().removeClass("required-field");
                }

                if (this.current_user) {
                    submit_url = user_data_url + this.current_user + '/';
                    action = 'edit';
                    if (submit_data.password === '') {
                        delete submit_data.password
                    }
                } else {
                    submit_data.terms_of_service = this.terms_of_service;
                    submit_data.honor_code = this.honor_code;
                    submit_data.lt_gdpr = this.lt_gdpr;
                    submit_data.org = this.org;
                    submit_data.lt_exempt_status = this.lt_exempt_status;
                    submit_url = creation_url;
                    action = 'create'
                    if (submit_data.password === '' || submit_data.password === undefined) {
                        $("#password").parent().addClass("required-field");
                    }
                    else {
                        $("#password").parent().removeClass("required-field");
                    }
                }

                if (submit_data.first_name === '' || this.first_name === '') {
                    $("#first-name").parent().addClass("required-field");
                } else {
                    $("#first-name").parent().removeClass("required-field");
                }

                if (submit_data.last_name === '' || this.last_name === '') {
                    $("#last-name").parent().addClass("required-field");
                }else {
                    $("#last-name").parent().removeClass("required-field");
                }

                if(this.username === '' || submit_data.last_name === '' || this.last_name === '' ||submit_data.first_name === '' || this.first_name === '' || submit_data.email === '' || this.email == "" || this.username === '' || submit_data.password === '' || this.name === '' || submit_data.name == ""){
                    LearningTribes.Notification.Error({
                        title:gettext("Error while creating account"),
                        message:gettext("Please fill in the required fields"),
                    })
                    return ;
                }

                var pattern = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$/;
                if ('email' in submit_data && !pattern.test(submit_data.email)) {
                    $("#email").parent().addClass("required-field");
                    LearningTribes.Notification.Error({
                        title:gettext("Error while creating account"),
                        message:gettext("Invalid email format"),
                    })
                    return
                }
                if (this.password != this.password_confirm) {
                    LearningTribes.Notification.Error({
                        title:gettext("Error while creating account"),
                        message:gettext("The two password fields didn't match."),
                    })
                    return;
                }

                Vue.http.post(submit_url, submit_data).then(function (resp) {
                    resp.json().then(function (data) {
                        $("button.cancel-button").hide();
                        if (action == 'create') {
                            history.replaceState(null, null, '/admin_panel/users/'+data.user_id+'/');
                            self.not_enrolled = data.not_enrolled;
                            LearningTribes.confirmation.show({
                               message: gettext("Add permissions to the user created"),
                               confirmationText: gettext('Go to permissions'),
                               cancelationText: gettext('Not now'),
                               confirmationCallback: function() {
                                   self.switch_tab('permissions')
                               },
                               cancelationCallback: function () {
                                   return false
                               }
                           });
                        }
                        else {
                            if (self.editting_info) {
                                LearningTribes.Notification.Info({
                                    title:"Modification of user personal data",
                                    message:'The user personal data has been modified.',
                                })
                            } else {
                                LearningTribes.Notification.Info({
                                    title:"User permissions saved",
                                    message:'We have saved the user permissions.',
                                })
                            }

                        }
                        self.load_from_data(data);
                        window.location = '#info-tabs'
                    })
                }, function (resp) {
                    var error_body = resp.body,
                        message = gettext("An error was encountered while saving your changes.");
                    if (typeof error_body === 'object' && 'error' in error_body) {
                        message = error_body.error.join('<br>')
                    }
                    if (typeof error_body === 'object' && 'user_programs_team_count' in error_body) {
                        message = gettext('The role of this user cannot be changed. `{email}` is still in the learning path team of {count} learning path(s). Remove the user from the team and come back here.').replace('{email}', self.email).replace('{count}', error_body.user_programs_team_count);
                    }
                    if (self.editting_info) {
                        LearningTribes.Notification.Error({
                            title:gettext("Error while saving user personal data"),
                            message: message,
                        })
                    }
                    else {
                        LearningTribes.Notification.Error({
                            title:gettext("Error while saving user permissions"),
                            message: message,
                        })
                    }

                })
            },
            initProgramRergistration: function(data) {
                var bulkRegistration = ReactDOM.render(
                    React.createElement(Registration, {
                        enrolledListAPI: '/api/program_enrollments/v1/users/${userName}/programs/?exclude_enrolled_flag=0&lp_loading_policy=1',
                        allListAPI: '/api/program_enrollments/v1/users/${userName}/programs/?exclude_enrolled_flag=1&lp_loading_policy=1',
                        enrollmentAPI: '/api/program_enrollments/v1/users/${userName}/programs/',
                        isDebug: false,
                    }, null),
                    document.querySelector('.program-tab')
                )

                bulkRegistration.startFetch({userName: data.username || ''})
            },
            revert_changes: function () {
                for (let i in this.origin_data) {
                    this[i] = this.origin_data[i]
                }
                this.editting_info = false;
                this.editting_permissions = false;
                $(".cancel-button").hide()
            },

            cancel: function () {
                if (this.current_user) {
                    this.revert_changes()
                } else {
                    window.location = '/admin_panel/users/'
                }
            },

            delete_user: function () {
                var self = this;
                LearningTribes.Notification.Warning({
                    title:gettext("Delete User Request"),
                    message:gettext("Are you sure about delete your user?"),
                    cancelText:gettext("Cancel"),
                    confirmText:gettext("Confirm"),
                    onCancel:function(){
                        self.deleting_user = false;
                    },
                    onConfirm:function(){
                        var url = delete_user_url + self.current_user + '/';
                        Vue.http.get(url).then(function (resp) {
                            resp.json().then(function (data) {
                                self.deleting_user = true;
                                self.objects_to_delete = data;
                                $(".delete-user-page").show();
                            })
                        })
                    }
                })
            },

            cancel_delete: function () {
                this.deleting_user = false;
                $(".delete-user-page").hide();
            },

            confirm_delete: function () {
                var url = delete_user_url + this.current_user + '/';
                Vue.http.post(url).then(function (resp) {
                    resp.json().then(function (data) {
                        LearningTribes.Notification.Info({
                            title:gettext("User deleted"),
                            message:gettext("The user has been successfully deleted."),
                            onCancel:function(){
                                window.location = '/admin_panel/users/'
                            }
                        })
                    }, function (data) {
                        LearningTribes.Notification.Error({
                            title:gettext("Error while user deletion"),
                            message:gettext("An error was encountered while deleting the user.")
                        })
                    })
                })
            },

            registration_data: function () {
                var context = {
                    search_result: this.search_result,
                    username: this.username,
                    email: this.email,
                    password: this.password,
                    first_name: this.first_name,
                    last_name: this.last_name,
                    name: this.name,
                    gender: this.gender,
                    year_of_birth: this.year_of_birth,
                    language: this.language,
                    country: this.country,
                    lt_custom_country: this.lt_custom_country,
                    lt_area: this.lt_area,
                    lt_sub_area: this.lt_sub_area,
                    city: this.city,
                    location: this.location,
                    lt_address: this.lt_address,
                    lt_address_2: this.lt_address_2,
                    lt_phone_number: this.lt_phone_number,
                    lt_gdpr: this.lt_gdpr,
                    lt_company: this.lt_company,
                    lt_employee_id: this.lt_employee_id,
                    lt_hire_date: this.lt_hire_date,
                    lt_level: this.lt_level,
                    lt_job_code: this.lt_job_code,
                    lt_job_description: this.lt_job_description,
                    lt_department: this.lt_department,
                    lt_supervisor: this.lt_supervisor,
                    lt_ilt_supervisor: this.lt_ilt_supervisor,
                    mailing_address: this.mailing_address,
                    lt_learning_group: this.lt_learning_group,
                    lt_exempt_status: this.lt_exempt_status,
                    lt_comments: this.lt_comments,
                    terms_of_service: this.terms_of_service
                };
                if (this.current_user) {
                    this.submit_data.action = "edit"
                } else {
                    this.submit_data.action = "create"
                }
                return context
            },

            load_from_data: function (data) {
                var self = this,
                    require_fields = ["#username", "#email", "#name", "#password", "#first-name", "#last-name"];
                self.current_user = data.user_id;
                self.username = data.username || '';
                self.email = data.email;
                self.first_name = data.first_name;
                self.last_name = data.last_name;
                self.name = data.name;
                self.gender = data.gender;
                self.year_of_birth = data.year_of_birth;
                self.language = data.language;
                self.country = data.country;
                self.lt_custom_country = data.lt_custom_country;
                self.lt_area = data.lt_area;
                self.lt_sub_area = data.lt_sub_area;
                self.city = data.city;
                self.location = data.location;
                self.lt_address = data.lt_address;
                self.lt_address_2 = data.lt_address_2;
                self.lt_phone_number = data.lt_phone_number;
                self.lt_gdpr = data.lt_gdpr;
                self.lt_company = data.lt_company;
                self.lt_employee_id = data.lt_employee_id;
                self.lt_hire_date = data.lt_hire_date;
                self.lt_level = data.lt_level;
                self.lt_job_code = data.lt_job_code;
                self.lt_job_description = data.lt_job_description;
                self.lt_department = data.lt_department;
                self.lt_supervisor = data.lt_supervisor;
                self.lt_ilt_supervisor = data.lt_ilt_supervisor;
                self.mailing_address = data.mailing_address;
                self.lt_learning_group = data.lt_learning_group;
                self.lt_exempt_status = data.lt_exempt_status;
                self.lt_comments = data.lt_comments;
                self.is_active = data.is_active;
                self.platform_level = data.platform_level;
                self.catalog_access = data.catalog_access;
                self.edflex_access = data.edflex_access;
                self.crehana_access = data.crehana_access;
                self.anderspink_access = data.anderspink_access;
                self.learnlight_access = data.learnlight_access;
                self.linkedin_access = data.linkedin_access;
                self.udemy_access = data.udemy_access;
                self.founderz_access = data.founderz_access;
                self.siemens_access = data.siemens_access;
                self.triboo_centrical_access = data.triboo_centrical_access;
                self.analytics_access = data.analytics_access;
                self.currently_enrolled = data.currently_enrolled;
                self.not_enrolled = data.not_enrolled;
                self.org = data.org;
                self.update_password = false;
                self.editting_info = false;
                self.editting_permissions = false;
                self.origin_data = Object.assign({}, data);
                self.origin_data.password = '';
                self.origin_data.password_confirm = '';
                self.origin_data.update_password = false;
                self.submit_data = {};
                if (self.lt_gdpr === 'False') {
                    self.lt_gdpr = false
                }
                if (self.lt_exempt_status === 'False') {
                    self.lt_exempt_status = false
                }
                sessionStorage.setItem('unsaved', '0');

                for (let i in require_fields) {
                    $(require_fields[i]).parent().removeClass("required-field");
                }
            },

            fetch_user_data: function () {
                if (!this.current_user) {
                    return
                } else {
                    var self = this;
                    this.update_password = false;
                    Vue.http.get(user_data_url+this.current_user).then(function (resp) {
                        resp.json().then(function (data) {
                            self.load_from_data(data)
                            // update analytic permission dropdown list based on user platform level:
                            self.selectedPlatformLevel()
                            if (program_feature_enabled) self.initProgramRergistration(data)
                        })
                    })
                }
            },

            click_user: function (data) {
                if (sessionStorage.unsaved === '1') {
                    var self = this;
                    LearningTribes.confirmation.show({
                       message: gettext("There are unsaved changes"),
                       confirmationText: gettext('Continue'),
                       cancelationText: gettext('Go back'),
                       confirmationCallback: function() {
                            self.load_from_data(data);
                            history.replaceState(null, null, '/admin_panel/users/'+data.user_id+'/')
                       },
                       cancelationCallback: function () {

                       }
                    });
                } else {
                    this.load_from_data(data);
                    history.replaceState(null, null, '/admin_panel/users/'+data.user_id+'/');
                    if (program_feature_enabled) this.initProgramRergistration(data);
                }
            },

            activate_tab: function (field) {
                this.active_tab=field
            },
            detect_change: function (field) {
                if (field in this.origin_data) {
                    if (this.$data[field] != this.origin_data[field]) {
                        this.submit_data[field] = this.$data[field]
                    } else {
                        delete this.submit_data[field]
                    }
                } else {
                    this.submit_data[field] = this.$data[field]
                }
                if ($.isEmptyObject(this.submit_data)) {
                    $("button.cancel-button").hide();
                    sessionStorage.setItem('unsaved', '0');
                } else {
                    $("button.cancel-button").show();
                    var permission_fields = ["is_active", "platform_level", "catalog_access",
                        "edflex_access", "crehana_access", "anderspink_access", "learnlight_access",
                        "linkedin_access", "udemy_access", "founderz_access", "siemens_access", "analytics_access",
                        "triboo_centrical_access"]
                    if (permission_fields.includes(field)) {
                        this.editting_permissions = true;
                        this.editting_info = false;
                    } else {
                        this.editting_permissions = false;
                        this.editting_info = true;
                    }
                    sessionStorage.setItem('unsaved', '1');
                }
            },

            _real_switch_tab: function (tab) {
                const hash = bleachHash(tab)

                this.activePanel = hash
                var url = new URL(window.location)
                url.hash = hash
                history.pushState({}, '', url)
            },

            switch_tab: function (tab) {
                var self = this;
                if (this.editting_info && tab != "personal-info") {
                    LearningTribes.confirmation.show({
                       message: gettext("There is unsaved user personal data"),
                       confirmationText: gettext('Continue without saving'),
                       cancelationText: gettext('Go back'),
                       confirmationCallback: function() {
                           self.revert_changes();
                           self._real_switch_tab(tab)
                       },
                       cancelationCallback: function () {
                           return false
                       }
                   });
                } else if (this.editting_permissions && tab != "permissions") {
                    LearningTribes.confirmation.show({
                       message: gettext("There is unsaved user permission data"),
                       confirmationText: gettext('Continue without saving'),
                       cancelationText: gettext('Go back'),
                       confirmationCallback: function() {
                           self.revert_changes();
                           self._real_switch_tab(tab)
                       },
                       cancelationCallback: function () {
                           return false
                       }
                   });
                } else {
                    self._real_switch_tab(tab)
                }
            },

            registration_tab: function (tab) {
                $(".registration-tabs span").removeClass("active")
                $("span."+tab).addClass("active")
            },

            search: function (e) {
                e.preventDefault();
                if (this.query === "") {
                    return true
                } else {
                    var self = this;
                    var url = search_api_url + '?name='+self.query+'&page=1&page_size=10'
                    Vue.http.post(search_api_url, {query: self.query}).then(function (resp) {
                        resp.json().then(function (data) {
                            self.search_result = data.search_result;
                            self.show_more = data.show_more;
                        })
                    })
                }
            },

            toggle_enrollment: function (action, course_id, idx) {
                var url = update_enrollment_url.replace("course_key", course_id).replace("user_id", this.current_user),
                    self = this,
                    notice_title, notice_message;
                var noticeObj = NOTICE[action+'Confirmation']
                LearningTribes.Notification.Warning({
                    title: noticeObj.title,
                    message:noticeObj.message,
                    cancelText:gettext('Cancel'),
                    confirmText:gettext('Confirm'),
                    onCancel:function(){

                    },
                    onConfirm:function(){
                        Vue.http.post(url, {action: action}).then(function (resp) {
                            resp.json().then(function (data) {
                                if (action == "enroll") {
                                    var info = data.info;
                                    if (self.enrollment_search !== "") {
                                        for (var i in self.not_enrolled) {
                                            if (self.not_enrolled[i].course_id == course_id) {
                                                idx = i;
                                                break;
                                            }
                                        }
                                    }
                                    info.name = self.not_enrolled[idx].name;
                                    self.not_enrolled.splice(idx, 1);
                                    self.currently_enrolled.push(info);
                                    LearningTribes.Notification.Info({
                                        title:gettext("Successfully enrolled"),
                                        message:gettext('The user have been successfully enrolled.'),
                                    })
                                }
                                else {
                                    if (data.user_enrolled_programs_count != undefined && data.user_enrolled_programs_count > 0) {
                                        const message = gettext('The course of this user cannot be unenrolled. This course of `{email}` is still in `{count}` learning path(s). Remove the user from them and come back here.').replace('{email}', self.email).replace('{count}', data.user_enrolled_programs_count);
                                        LearningTribes.Notification.Error(
                                            {
                                                title: gettext("Error while unenrolling user course"),
                                                message: message,
                                            }
                                        )
                                    } else {
                                        if (self.enrollment_search !== "") {
                                            for (var i in self.currently_enrolled) {
                                                if (self.currently_enrolled[i].course_id == course_id) {
                                                    idx = i;
                                                    break;
                                                }
                                            }
                                        }
                                        var info = self.currently_enrolled.splice(idx, 1)[0];
                                        self.not_enrolled.push(info);
                                        LearningTribes.Notification.Info({
                                            title:gettext("Successfully unenrolled"),
                                            message:gettext("The user is no longer enrolled in the course(s)."),
                                        })
                                    }
                                }
                            })
                        })
                    }
                })

            },

            trans: function (text) {
                return gettext(text)
            },

            onHashChange: function () {
                this._real_switch_tab(window.location.hash.slice(1))
            }
        },
        computed: {
            enrolled_by_search: function () {
                if (this.enrollment_search === "") {
                    this.enrolled_search_result = this.currently_enrolled;
                    return this.enrolled_search_result
                } else {
                    this.enrolled_search_result = [];
                    for (i in this.currently_enrolled) {
                        var course_name = this.currently_enrolled[i].name.toLowerCase();
                        if (course_name.includes(this.enrollment_search.toLowerCase())) {
                            this.enrolled_search_result.push(this.currently_enrolled[i])
                        }
                    }
                    return this.enrolled_search_result
                }
            },

            not_enrolled_by_search: function () {
                if (this.enrollment_search === "") {
                    this.not_enrolled_search_result = this.not_enrolled;
                    return this.not_enrolled_search_result
                } else {
                    this.not_enrolled_search_result = [];
                    for (i in this.not_enrolled) {
                        var course_name = this.not_enrolled[i].name.toLowerCase();
                        if (course_name.includes(this.enrollment_search.toLowerCase())) {
                            this.not_enrolled_search_result.push(this.not_enrolled[i])
                        }
                    }
                    return this.not_enrolled_search_result
                }
            }
        },

        created () {
            window.addEventListener("hashchange", this.onHashChange, false)
        },

        destroyed () {
            window.removeEventListener('hashchange', this.onHashChange)
        }
    });

    function init() {
        UserData.fetch_user_data()
    }

    init();
}
