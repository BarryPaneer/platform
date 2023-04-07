define(['domReady', 'jquery', 'underscore', 'js/utils/cancel_on_escape', 'js/views/utils/create_course_utils',
    'js/views/utils/create_path_utils',
    'js/views/utils/create_library_utils', 'common/js/components/utils/view_utils'],
    function(domReady, $, _, CancelOnEscape, CreateCourseUtilsFactory, CreatePathUtilsFactory, CreateLibraryUtilsFactory, ViewUtils) {
        'use strict';
        var CreateCourseUtils = new CreateCourseUtilsFactory({
            name: '.new-course-name',
            org: '.new-course-org',
            number: '.new-course-number',
            run: '.new-course-run',
            save: '.new-course-save',
            errorWrapper: '.create-course .wrap-error',
            errorMessage: '#course_creation_error',
            tipError: '.create-course span.tip-error',
            error: '.create-course .error',
            allowUnicode: '.allow-unicode-course-id'
        }, {
            shown: 'is-shown',
            showing: 'is-showing',
            hiding: 'is-hiding',
            disabled: 'is-disabled',
            error: 'error'
        });

        var CreateLibraryUtils = new CreateLibraryUtilsFactory({
            name: '.new-library-name',
            org: '.new-library-org',
            number: '.new-library-number',
            save: '.new-library-save',
            errorWrapper: '.create-library .wrap-error',
            errorMessage: '#library_creation_error',
            tipError: '.create-library  span.tip-error',
            error: '.create-library .error',
            allowUnicode: '.allow-unicode-library-id'
        }, {
            shown: 'is-shown',
            showing: 'is-showing',
            hiding: 'is-hiding',
            disabled: 'is-disabled',
            error: 'error'
        });

        var CreatePathUtils = new CreatePathUtilsFactory({
            name: '.new-path-name',
            org: '.new-path-org',
            //number: '.new-path-number',
            save: '.new-path-save',
            errorWrapper: '.create-path .wrap-error',
            errorMessage: '#path_creation_error',
            tipError: '.create-path  span.tip-error',
            error: '.create-path .error',
            allowUnicode: '.allow-unicode-path-id'
        }, {
            shown: 'is-shown',
            showing: 'is-showing',
            hiding: 'is-hiding',
            disabled: 'is-disabled',
            error: 'error'
        });

        var setNavigationButtonsStatus = function(status) {
            var $navActions = $('.mast .nav-actions')
            if (status) {
                $navActions.removeClass('hidden')
            }else{
                $navActions.addClass('hidden')
            }

        }

        var saveNewCourse = function(e) {
            e.preventDefault();

            if (CreateCourseUtils.hasInvalidRequiredFields()) {
                return;
            }

            var $newCourseForm = $(this).closest('#create-course-form');
            var display_name = $newCourseForm.find('.new-course-name').val();
            var org = $newCourseForm.find('.new-course-org').val();
            var number = $newCourseForm.find('.new-course-number').val();
            var run = $newCourseForm.find('.new-course-run').val();

            var course_info = {
                org: org,
                number: number,
                display_name: display_name,
                run: run
            };

            analytics.track('Created a Course', course_info);
            CreateCourseUtils.create(course_info, function(errorMessage) {
                $('.create-course .wrap-error').addClass('is-shown');
                $('#course_creation_error').html('<p>' + errorMessage + '</p>');
                $('.new-course-save').addClass('is-disabled').attr('aria-disabled', true);
            });
            setNavigationButtonsStatus(true)
        };

        var rtlTextDirection = function() {
            var Selectors = {
                new_course_run: '#new-course-run'
            };

            if ($('body').hasClass('rtl')) {
                $(Selectors.new_course_run).addClass('course-run-text-direction placeholder-text-direction');
                $(Selectors.new_course_run).on('input', function() {
                    if (this.value === '') {
                        $(Selectors.new_course_run).addClass('placeholder-text-direction');
                    } else {
                        $(Selectors.new_course_run).removeClass('placeholder-text-direction');
                    }
                });
            }
        };

        var makeCancelHandler = function(addType) {
            return function(e) {
                e && e.preventDefault();
                $('.new-' + addType + '-button').removeClass('is-disabled').attr('aria-disabled', false);
                $('.wrapper-create-' + addType).removeClass('is-shown');
                // Clear out existing fields and errors
                $('#create-' + addType + '-form input[type=text]').val('');
                $('#' + addType + '_creation_error').html('');
                $('.create-' + addType + ' .wrap-error').removeClass('is-shown');
                $('.new-' + addType + '-save').off('click');

                setNavigationButtonsStatus(true)
            };
        };

        var pathCreatingForm  = null
        var addNewPath = function(orgs) {
            const {ReactDOM,React}=LearningTribes
            var wrapper = document.querySelector('.wrapper-create-path')
            wrapper.classList.add('is-shown')
            pathCreatingForm = ReactDOM.render(
                React.createElement(PathCreatingForm, {
                    data:orgs,
                    onCancel:(e)=>{
                        ReactDOM.unmountComponentAtNode(wrapper)
                        makeCancelHandler('path')()
                    },
                    onSave:saveNewPath
                }, null),
                wrapper
            );
            //CreatePathUtils.setupOrgAutocomplete();
            CreatePathUtils.configureHandlers();
        }

        var saveNewPath = function(e, path_info) {
            if (CreatePathUtils.hasInvalidRequiredFields()) {
                return;
            }
            analytics.track('Created a Path', path_info);
            const extended_path_info = _.extend(path_info, {status:'unpublished', marketing_slug:path_info.title })
            CreatePathUtils.create(extended_path_info, function(data) {
                if (data && data.program_uuid) {
                    window.location = '/program_detail/?program_uuid='+ data.program_uuid
                }else{
                    LearningTribes.Notification.Error({
                        title:'error',
                        message:'wrong response from api "/program_detail/?program_uuid=?"',
                    })
                }
                /*LearningTribes.Notification.Info({
                    title:gettext('Creation of a new Learning Path'),
                    message:gettext('Your Learning Path has been successfully created.'),
                })*/
                $('.new-path-save').addClass('is-disabled').attr('aria-disabled', true);
            }, function(errObj){
                var msg = errObj.api_error_message.includes('Path name already exist.') ? gettext('Learning Path name already exists.') : errObj.api_error_message;
                LearningTribes.Notification.Error({
                    title: gettext('Error'),
                    message: msg,
                })
            });
        }

        var addNewCourse = function(e) {
            var $newCourse,
                $cancelButton,
                $courseName;
            $('.new-course-button').addClass('is-disabled').attr('aria-disabled', true);
            $('.new-course-save').addClass('is-disabled').attr('aria-disabled', true);
            $newCourse = $('.wrapper-create-course').addClass('is-shown');
            $cancelButton = $newCourse.find('.new-course-cancel, .close-icon');
            $courseName = $('.new-course-name');
            $courseName.focus().select();
            $('.new-course-save').on('click', saveNewCourse);
            $cancelButton.bind('click', makeCancelHandler('course'));
            $('.cover', $newCourse).bind('click', makeCancelHandler('course'))
            CancelOnEscape($cancelButton);
            CreateCourseUtils.setupOrgAutocomplete();
            CreateCourseUtils.configureHandlers();
            rtlTextDirection();
            setNavigationButtonsStatus(false)
        };

        var saveNewLibrary = function(e) {
            e.preventDefault();

            if (CreateLibraryUtils.hasInvalidRequiredFields()) {
                return;
            }

            var $newLibraryForm = $(this).closest('#create-library-form');
            var display_name = $newLibraryForm.find('.new-library-name').val();
            var org = $newLibraryForm.find('.new-library-org').val();
            var number = $newLibraryForm.find('.new-library-number').val();

            var lib_info = {
                org: org,
                number: number,
                display_name: display_name
            };

            analytics.track('Created a Library', lib_info);
            CreateLibraryUtils.create(lib_info, function(errorMessage) {
                $('.create-library .wrap-error').addClass('is-shown');
                $('#library_creation_error').html('<p>' + errorMessage + '</p>');
                $('.new-library-save').addClass('is-disabled').attr('aria-disabled', true);
            });
        };

        var addNewLibrary = function(e) {
            $('.new-library-button').addClass('is-disabled').attr('aria-disabled', true);
            $('.new-library-save').addClass('is-disabled').attr('aria-disabled', true);
            var $newLibrary = $('.wrapper-create-library').addClass('is-shown');
            var $cancelButton = $newLibrary.find('.new-library-cancel, .close-icon');
            var $libraryName = $('.new-library-name');
            $libraryName.focus().select();
            $('.new-library-save').on('click', saveNewLibrary);
            $cancelButton.bind('click', makeCancelHandler('library'));
            $('.cover', $newLibrary).bind('click', makeCancelHandler('library'))
            CancelOnEscape($cancelButton);

            CreateLibraryUtils.configureHandlers();
            setNavigationButtonsStatus(false)
        };


        var onReady = function(options) {
            $('.new-course-button').bind('click', addNewCourse);

            const buttonActions = {
                course: addNewCourse,
                path: addNewPath,
                library: addNewLibrary
            }
            const {orgs, is_program_enabled} = options
            var buttons = ReactDOM.render(
                React.createElement(NavActions, {
                    is_program_enabled: is_program_enabled,
                    onActviated: function (buttonName) {
                        buttonActions[buttonName](orgs)
                        _.without(Object.keys(buttonActions), buttonName).forEach(function (key) {
                            ReactDOM.unmountComponentAtNode(document.querySelector('.wrapper-create-' + key))
                            makeCancelHandler(key)()
                        })
                    }
                }, null),
                document.querySelector('.nav-actions ul')
            );

            window.sharing = {
                buttons: buttons
            }

            $('.dismiss-button').bind('click', ViewUtils.deleteNotificationHandler(function() {
                ViewUtils.reload();
            }));

            $('.action-reload').bind('click', ViewUtils.reload);


        };

        function initialize(options) {
            onReady(options)
        }

        return {
            initialize: initialize,
            onReady: onReady
        };
    });
