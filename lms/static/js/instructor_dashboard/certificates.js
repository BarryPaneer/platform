var edx = edx || {};
var onCertificatesReady = null;

(function($, gettext, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.certificates = {};

    onCertificatesReady = function() {
        /**
         * Show a confirmation message before letting staff members
         * enable/disable self-generated certificates for a course.
         */
        $('#enable-certificates-form').on('submit', function(event) {
            var isEnabled = $('#certificates-enabled').val() === 'true',
                confirmMessage = '';

            if (isEnabled) {
                confirmMessage = gettext('Allow learners to generate certificates for this course?');
            } else {
                confirmMessage = gettext('Prevent learners from generating certificates in this course?');
            }

            if (!confirm(confirmMessage)) {
                event.preventDefault();
            }
        });

        /**
         * Refresh the status for example certificate generation
         * by reloading the instructor dashboard.
         */
        $('#refresh-example-certificate-status').on('click', function() {
            window.location.reload();
        });

        /**
         * Certificates Export
         */
        $('#generate-cert').click(function() {
            var url = $(this).data('endpoint'),
                identifier_input = $('#export-identifiers').val(),
                $cert_download = $('.certificates-download');
            $(this).val('generating ..');
            $.ajax({
                type: 'POST',
                url: url,
                data: {
                    identifiers: identifier_input
                },
                success: function(data) {
                    $('#generate-cert').val('generate');
                    var $result = $('.certificates-error'),
                        fail_num = data.fail.length;
                    if (fail_num > 0) {
                        $result.show();
                        $result.find('ul').empty();
                        for (var i = 0; i < data.fail.length; i++) {
                            $result.find('ul').append(data.fail[i]);
                        }
                    }
                }
            });
        });

        var endpoint = $('.certificates-download').data('endpoint');
        function get_zip_links() {
            $.ajax({
                type: 'GET',
                url: endpoint,
                success: function(data) {
                    var $zip_list = $('.zip-file-list'),
                        link_num = data.links.length;
                    if (link_num > 0) {
                        $zip_list.show();
                        $zip_list.find('ul').empty();
                        for (var i = 0; i < data.links.length; i++) {
                            $zip_list.find('ul').append(data.links[i]);
                        }
                    }
                }
            });
        }
        get_zip_links();
        setInterval(get_zip_links, 30000);

        /**
         * Intermediate Certificates Export
         */
        // $('#generate-intermediate-certificates-submit').click(function(e) {
        //     e.preventDefault();
        //     var url = $(this).data('endpoint');
        //     console.log('url', url);
        //     // var $cert_list = $(".intermediate-certificates-list")
        //     // var cert_list_endpoint = $cert_list.data('endpoint')
        //     // console.log('cert_list_endpoint', cert_list_endpoint)
        //     window.open(url);
        //     // $.ajax({
        //     //     type: "POST",
        //     //     url: url,
        //     //     data: {
        //     //         users: "edx, Yu, audit",
        //     //     },
        //     //     success: function (data) {
        //     //         console.log('list data', data)
        //     //         var $zip_list = $('.cert-list'),
        //     //             link_num = data["links"].length;
        //     //         if (link_num > 0) {
        //     //             $zip_list.show();
        //     //             $zip_list.find('ul').empty();
        //     //             for (var i = 0; i < data["links"].length; i++) {
        //     //                 $zip_list.find('ul').append(data["links"][i])
        //     //             }
        //     //         }
        //     //     }
        //     // });
        // });

        /**
         * Start generating certificates for all students.
         */
        var $section = $('section#certificates');
        $section.on('click', '#btn-start-generating-certificates', function(event) {
            if (!confirm(gettext('Start generating certificates for all learners in this course?'))) {
                event.preventDefault();
                return;
            }

            var $btn_generating_certs = $(this),
                $certificate_generation_status = $('.certificate-generation-status');
            var url = $btn_generating_certs.data('endpoint');
            $.ajax({
                type: 'POST',
                url: url,
                success: function(data) {
                    $btn_generating_certs.attr('disabled', 'disabled');
                    $certificate_generation_status.text(data.message);
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    $certificate_generation_status.text(gettext('Error while generating certificates. Please try again.'));
                }
            });
        });

        /**
         * Start regenerating certificates for students.
         */
        $section.on('click', '#btn-start-regenerating-certificates', function(event) {
            LearningTribes.confirmation.show(gettext('Start regenerating certificates for learners in this course?'), function() {
                var $btn_regenerating_certs = $('#btn-start-regenerating-certificates'),
                    $certificate_regeneration_status = $('.certificate-regeneration-status'),
                    url = $btn_regenerating_certs.data('endpoint');

                $.ajax({
                    type: 'POST',
                    data: $('#certificate-regenerating-form').serializeArray(),
                    url: url,
                    success: function(data) {
                        $btn_regenerating_certs.attr('disabled', 'disabled');
                        if (data.success) {
                            $certificate_regeneration_status.text(data.message).addClass('message');
                        } else {
                            $certificate_regeneration_status.text(data.message).addClass('message');
                        }
                    },
                    error: function(jqXHR) {
                        try {
                            var response = JSON.parse(jqXHR.responseText);
                            $certificate_regeneration_status.text(gettext(response.message)).addClass('message');
                        } catch (error) {
                            $certificate_regeneration_status.
                                text(gettext('Error while regenerating certificates. Please try again.')).
                                addClass('message');
                        }
                    }
                });
            });
        });

        // $(".ic-type-sel").select2({
        //     placeholder: "Select a type",
        //     allowClear: true
        // });
    };

    // Call onCertificatesReady on document.ready event
    $(onCertificatesReady);

    var Certificates = (function() {
        function Certificates($section) {
            $section.data('wrapper', this);
            this.instructor_tasks = new window.InstructorDashboard.util.PendingInstructorTasks($section);
        }

        Certificates.prototype.onClickTitle = function() {
            return this.instructor_tasks.task_poller.start();
        };

        Certificates.prototype.onExit = function() {
            return this.instructor_tasks.task_poller.stop();
        };
        return Certificates;
    }());

    _.defaults(window, {
        InstructorDashboard: {}
    });

    _.defaults(window.InstructorDashboard, {
        sections: {}
    });

    _.defaults(window.InstructorDashboard.sections, {
        Certificates: Certificates
    });
}($, gettext, _));
