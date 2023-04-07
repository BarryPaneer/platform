function iltValidation() {

    Vue.component('select2', {
        props: ['options', 'value', 'placeholder'],
        template: '<select><slot></slot></select>',
        mounted: function () {
            var vm = this;
            $(this.$el)
            // init select2
                .select2({
                    data: this.options,
                    placeholder: this.placeholder
                })
                .val(this.value)
                .trigger('change')
                // emit event on change.
                .on('change', function () {
                    vm.$emit('input', this.value)
                })
        },
        destroyed: function () {
            $(this.$el).off().select2('destroy')
        }
    });

    const data_url = "/ilt-validation-request-data/",
          batch_enroll_url = "/ilt-batch-enroll/";

    const ILTValidationList = new Vue({
        el: "#ilt-validation-page",
        data: {
            pending_all: [],
            approved_all: [],
            declined_all: [],
            to_validate: {},
            to_unsubscribe: {},
            session_info: {},
            accommodation: false,
            date_format: "YYYY-MM-DD HH:mm",
            cached_request: {},
            input_name: '',
            selected_module: '',
            selected_start: '',
            current_approved_results: [],
            start_format: "YYYY-MM-DD",
            last_module_value: '',
            last_start_value: '',
            course_module_dict: null,
            module_course_dict: null,
            enrollment_selected_course: '',
            enrollment_selected_module: ''
        },
        computed: {
            current_pending_sessions: function () {
                var result = [];
                for (var i in this.pending_all) {
                    var r_info = this.pending_all[i],
                        usage_key = r_info.usage_key,
                        course_key = r_info.course_key,
                        sess_key = r_info.session_id;
                    result.push(this.session_info[course_key][usage_key][sess_key])
                }
                return result
            },

            current_approved_sessions: function () {
                var result = [];
                for (var i in this.approved_all) {
                    var r_info = this.approved_all[i],
                        usage_key = r_info.usage_key,
                        course_key = r_info.course_key,
                        sess_key = r_info.session_id;
                    result.push(this.session_info[course_key][usage_key][sess_key])
                }
                return result
            },

            current_declined_sessions: function () {
                var result = [];
                for (var i in this.declined_all) {
                    var r_info = this.declined_all[i],
                        usage_key = r_info.usage_key,
                        course_key = r_info.course_key,
                        sess_key = r_info.session_id;
                    result.push(this.session_info[course_key][usage_key][sess_key])
                }
                return result
            },

            current_approved_return: function () {
                var result = [],
                    res_name = [],
                    res_module = [],
                    res_start = []
                for (var i in this.approved_all) {
                    var r = this.approved_all[i];
                    if (!this.input_name || r.learner_name.indexOf(this.input_name) !== -1 || r.user_name.indexOf(this.input_name) !== -1) {
                        res_name.push(r);
                    }
                    if (!this.selected_module || r.module === this.selected_module) {
                        res_module.push(r);
                    }
                    if (!this.selected_start || moment(r.start).format(this.start_format) === this.selected_start) {
                        res_start.push(r);
                    }
                }
                result = res_name.filter(function (val) { return res_module.indexOf(val) > -1 })
                result = result.filter(function (val) { return res_start.indexOf(val) > -1 })
                this.current_approved_results = result
                return result;
            },

            current_approved_sessions_return: function () {
                var result = [],
                    approved = this.current_approved_results;
                for (var i in approved) {
                    var r_info = approved[i],
                        usage_key = r_info.usage_key,
                        course_key = r_info.course_key,
                        sess_key = r_info.session_id;
                    result.push(this.session_info[course_key][usage_key][sess_key])
                }
                // console.log('current_approved_sessions_return', result)
                return result
            },

            current_modules: function () {
                var result = [],
                    approved = this.current_approved_results;
                for (var i in approved) {
                    var module = approved[i].module;
                    if (result.indexOf(module) === -1) {
                        result.push(module);
                    }
                }
                this.current_modules_list = result
                var module = $('select#id_select_module.select2-hidden-accessible')
                var module_value = module.val()
                if (module[0] && (!module_value || this.last_module_value === module_value)) {
                    module.empty()
                        .select2({
                            data: this.current_modules_list,
                            placeholder: module[0].dataset.ph
                        }).val(module_value).change()
                    // console.log('this.current_modules_list', this.current_modules_list)
                }
                this.last_module_value = module_value
                return result;
            },

            current_starts: function () {
                var result = [],
                    approved = this.current_approved_results;
                for (var i in approved) {
                    var start = moment(approved[i].start).format(this.start_format);
                    if (result.indexOf(start) === -1) {
                        result.push(start);
                    }
                }
                this.current_starts_list = result
                var start = $('select#id_select_start.select2-hidden-accessible')
                var start_value = start.val()
                if (start[0] && (!start_value || this.last_start_value === start_value)) {
                    start.empty()
                        .select2({
                            data: this.current_starts_list,
                            placeholder: start[0].dataset.ph
                        }).val(start_value).change()
                    // console.log('this.current_starts_list', this.current_starts_list)
                }
                this.last_start_value = start_value
                return result;
            },

            current_enrollment_courses: function () {
                var result = [];
                for (var key in this.course_module_dict) {
                    result.push({
                        id: key,
                        text: this.course_module_dict[key]['course_name']
                    })
                }
                return result
            },

            current_enrollment_modules: function () {
                if (this.enrollment_selected_course == '') {
                    return []
                }
                var current_module = $('select#id_enrollment_select_module.select2-hidden-accessible');
                var modules = this.course_module_dict[this.enrollment_selected_course].modules,
                    result = [];
                for (var i in modules) {
                    result.push({
                        id: modules[i][1],
                        text: modules[i][0]
                    })
                }
                var tmp_value = current_module.val();
                current_module.empty().select2({
                    data: result,
                    placeholder: current_module[0].dataset.ph
                }).val(tmp_value).change();
                return result
            },

            current_enrollment_sessions: function () {
                if (this.enrollment_selected_course != '' && this.enrollment_selected_module != '') {
                    var modules = this.course_module_dict[this.enrollment_selected_course].modules;
                    for (var i in modules) {
                        if (modules[i][1] === this.enrollment_selected_module) {
                            var sessions = modules[i][2];
                            return sessions
                        }
                    }
                }

                return []
            },

            current_enrollment_users: function () {
                if (this.enrollment_selected_course != '' && this.enrollment_selected_module != '') {
                    var modules = this.course_module_dict[this.enrollment_selected_course].modules;
                    for (var i in modules) {
                        if (modules[i][1] === this.enrollment_selected_module) {
                            var users = modules[i][3];
                            return users
                        }
                    }
                }

                return {}
            },

            has_learner_selected: function () {
                var learners = this.current_enrollment_users;
                for (var key in learners) {
                    if (learners[key].checked) {
                        return true
                    }
                }
                return false
            }
        },
        methods: {
            showSaveButton: function () {

            },

            validate: function (action, index) {
                var request = this.pending_all[index],
                    data = {};
                data.course_key = request.course_key;
                data.usage_key = request.usage_key;
                data.session_id = request.session_id;
                data.user_id = request.user_id;
                data.action = action;
                data.info = {};
                data.info.number_of_one_way = request.number_of_one_way;
                data.info.number_of_return = request.number_of_return;
                data.info.accommodation = request.accommodation;
                data.info.comment = request.comment;
                request.status = action;
                Vue.http.post(data_url, data).then(function (resp) {
                    ILTValidationList.pending_all.splice(index, 1);
                    if (action === "approved") {
                        getValidationList()
                    } else {
                        getValidationList()
                    }
                })
            },

            unsubscribe: function (index, type) {
                LearningTribes.confirmation.show(gettext("Are you sure to unenroll this learner?"), function () {
                    var request = ILTValidationList[type][index],
                        url = "/courses/" + request.course_key + "/xblock/" + request.usage_key + "/handler_noauth/batch_unenroll";
                    Vue.http.post(url, {
                        identifiers: request.user_name,
                        session: request.session_id
                    }).then(function (resp) {
                        getValidationList()
                    })
                });
            },

            getCookie: function (name) {
                var value = '; ' + document.cookie,
                    parts = value.split('; ' + name + '=');
                if (parts.length === 2) return parts.pop().split(';').shift()
            },

            combineDate: function (date1, date2) {
                var d1 = moment(date1),
                    d2 = moment(date2);
                if (d1.isSame(d2, 'year') && d1.isSame(d2, 'month') && d1.isSame(d2, 'date')) {
                    return d1.format(this.date_format) + ' - ' + d2.format('HH:mm')
                } else {
                    return d1.format(this.date_format) + ' - ' + d2.format(this.date_format)
                }
            },

            convert_date: function (date) {
                var d = moment(date);
                return d.format(this.date_format)
            },

            edit: function (index, tab) {
                if (tab === 'approved') {
                    var request = this.current_approved_results[index];
                } else {
                    var request = this.pending_all[index];
                }
                this.cached_request[index] = Object.assign({}, request);
                request.is_editing = true
            },

            save: function (index, tab) {
                if (tab === 'approved') {
                    var request = this.current_approved_results[index];
                } else {
                    var request = this.pending_all[index];
                }
                var data = {};
                data.course_key = request.course_key;
                data.usage_key = request.usage_key;
                data.session_id = request.session_id;
                data.user_id = request.user_id;
                data.info = {};
                data.info.number_of_one_way = request.number_of_one_way;
                data.info.number_of_return = request.number_of_return;
                data.info.accommodation = request.accommodation;
                data.info.comment = request.comment;
                data.info.status = request.status;
                data.info.hotel = request.hotel;
                console.log(data);
                Vue.http.post(data_url, data).then(function (resp) {
                    request.is_editing = false;
                })
            },

            cancel: function (index, tab) {
                if (tab === 'approved') {
                    var request = this.current_approved_results[index];
                } else {
                    var request = this.pending_all[index];
                }
                request.number_of_one_way = this.cached_request[index].number_of_one_way;
                request.number_of_return = this.cached_request[index].number_of_return;
                request.accommodation = this.cached_request[index].accommodation;
                request.session_id = this.cached_request[index].session_id;
                request.comment = this.cached_request[index].comment;
                request.is_editing = false
            },

            chooseTab: function (tab) {
                if (tab === 'pending') {
                    $(".pending-tab").addClass("active");
                    $(".pending-requests").show();
                    $(".approved-tab").removeClass("active");
                    $(".declined-tab").removeClass("active");
                    $(".enrollment-tab").removeClass("active");
                    $(".approved-requests").hide();
                    $(".declined-requests").hide();
                    $(".enrollment-panel").hide();
                } else if (tab === 'approved') {
                    $(".pending-tab").removeClass("active");
                    $(".pending-requests").hide();
                    $(".approved-tab").addClass("active");
                    $(".declined-tab").removeClass("active");
                    $(".enrollment-tab").removeClass("active");
                    $(".approved-requests").show();
                    $(".declined-requests").hide();
                    $(".enrollment-panel").hide();
                } else if (tab === 'declined') {
                    $(".pending-tab").removeClass("active");
                    $(".pending-requests").hide();
                    $(".approved-tab").removeClass("active");
                    $(".declined-tab").addClass("active");
                    $(".enrollment-tab").removeClass("active");
                    $(".approved-requests").hide();
                    $(".declined-requests").show();
                    $(".enrollment-panel").hide();
                } else {
                    $(".pending-tab").removeClass("active");
                    $(".pending-requests").hide();
                    $(".approved-tab").removeClass("active");
                    $(".declined-tab").removeClass("active");
                    $(".enrollment-tab").addClass("active");
                    $(".approved-requests").hide();
                    $(".declined-requests").hide();
                    $(".enrollment-panel").show();
                }
            },

            isWithinDeadline: function (index, tab) {
                if (tab === 'approved') {
                    var request = this.current_approved_results[index];
                } else {
                    var request = this.pending_all[index];
                }
                var session_id = request.session_id;
                for (var i in request.dropdown_list) {
                    if (request.dropdown_list[i][2] == session_id) {
                        var class_names = request.dropdown_list[i][1];
                        return class_names.includes('within-deadline')
                    }
                }
            },

            trans: function (text) {
                return gettext(text)
            },

            reset: function () {
                this.input_name = ''
                this.selected_module = ''
                this.selected_start = ''
                this.current_approved_results = this.approved_all
                var module = $('select#id_select_module.select2-hidden-accessible')
                var start = $('select#id_select_start.select2-hidden-accessible')
                module.empty()
                    .select2({
                        data: this.current_approved_results,
                        placeholder: module[0].dataset.ph
                    }).val('0').change()
                start.empty()
                    .select2({
                        data: this.current_approved_results,
                        placeholder: start[0].dataset.ph
                    }).val('0').change()
            },

            reset_enrollment_search: function () {
                this.enrollment_selected_course = '';
                this.enrollment_selected_module = '';
                var current_modules = $('select#id_enrollment_select_module.select2-hidden-accessible'),
                    current_courses = $('select#id_enrollment_select_course.select2-hidden-accessible');
                current_courses.empty().select2({
                    data: this.current_enrollment_courses,
                    placeholder: current_courses[0].dataset.ph
                }).val('0').change();
                current_modules.empty().select2({
                    data: [],
                    placeholder: current_modules[0].dataset.ph
                }).val('0').change();
            },

            expand_session_card: function (idx) {
                var current_session_id = "#session-idx-" + idx,
                    $session = $(current_session_id);
                $('.session-title').show();
                $('.expanded-session').hide();
                $session.find('.session-title').hide();
                $session.find('.expanded-session').show();
                this.unselect_all_learners();
            },

            fold_session_card: function () {
                $('.session-title').show();
                $('.expanded-session').hide();
                this.unselect_all_learners();
            },

            unselect_all_learners: function () {
                var learners = this.current_enrollment_users;
                for (var key in learners) {
                    learners[key].checked = false;
                }
            },

            batch_enroll: function (session_nb, available_seats) {
                var learners = this.current_enrollment_users,
                    learner_list = [],
                    visible_to_staff_only = this.module_course_dict[this.enrollment_selected_module][2],
                    has_non_staff_learner = false,
                    non_staff_learner_list = [];
                for (var key in learners) {
                    if (learners[key].checked) {
                        learner_list.push(key);
                        if (!learners[key].is_staff) {
                            has_non_staff_learner = true;
                            non_staff_learner_list.push(learners[key].full_name + ' - ' + learners[key].user_name)
                        }
                    }
                }
                if (visible_to_staff_only && has_non_staff_learner) {
                    LearningTribes.dialog.show(gettext("This unit is visible to staff learner only. The following learners are not staff: <br><br>" + non_staff_learner_list.join('<br>')));
                    return
                }
                if (learner_list.length > 0) {
                    if (learner_list.length > available_seats) {
                        LearningTribes.dialog.show(gettext("There are not enough seats available!"));
                        return
                    }
                    Vue.http.post(batch_enroll_url, {
                        learners: learner_list,
                        session_nb: session_nb,
                        usage_key: this.enrollment_selected_module,
                        course_name: this.course_module_dict[this.enrollment_selected_course].course_name,
                        module_name: this.module_course_dict[this.enrollment_selected_module][0],
                        session_info: this.session_info[this.enrollment_selected_course][this.enrollment_selected_module][session_nb]
                    }).then(function (resp) {
                        LearningTribes.dialog.show(gettext("The enrollment is confirmed.<br>You can change information related to the demand by clicking on the << Upcoming Sessions >> tab."));
                        getValidationList()
                    })
                }
            },

            is_url_location: function (location) {
                // if location is a URL, then convert it to <a>location</a>
                var regexp = /(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?/;
                return regexp.test(location)
            }
        },
    });

    function fetchData(resp) {
        resp.json().then(function (data) {
            ILTValidationList.to_validate = {};
            ILTValidationList.to_unsubscribe = {};
            ILTValidationList.pending_all = data.pending_all;
            ILTValidationList.session_info = data.session_info;
            ILTValidationList.accommodation = data.accommodation;
            ILTValidationList.date_format = data.date_format;
            ILTValidationList.cached_request = {};
            ILTValidationList.approved_all = data.approved_all;
            ILTValidationList.declined_all = data.declined_all;
            ILTValidationList.start_format = data.date_format.substr(0, 10);
            ILTValidationList.course_module_dict = data.course_module_dict;
            ILTValidationList.module_course_dict = data.module_course_dict;
            ILTValidationList.current_approved_results = data.approved_all;
        })
    }

    function getValidationList() {
        Vue.http.get(data_url).then(function (resp) {
            fetchData(resp)
        })
    }

    // initialize
    getValidationList()
}