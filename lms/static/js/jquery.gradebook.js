


var Gradebook = function($element) {
    "use strict";
    var $body = $('body');
    var $grades = $element.find('.grades');
    var $studentTable = $element.find('.student-table');
    var $gradeTable = $element.find('.grade-table');
    var $search = $element.find('.student-search-field');
    var $leftShadow = $('<div class="left-shadow"></div>');
    var $rightShadow = $('<div class="right-shadow"></div>');
    var tableHeight = $gradeTable.height();
    var maxScroll = $gradeTable.width() - $grades.width();

    var $edit = $('button.edit-grade'),
        $edit_siblings = $('button.confirm-grade'),
        $promote_button = $gradeTable.find('a.promote-section'),
        $undo_button = $gradeTable.find('a.undo-grade'),
        $grade_td = $gradeTable.find('tbody td'),
        grade_log = {};

    var mouseOrigin;
    var tableOrigin;

    var startDrag = function(e) {
        mouseOrigin = e.pageX;
        tableOrigin = $gradeTable.position().left;
        $body.addClass('no-select');
        $body.bind('mousemove', onDragTable);
        $body.bind('mouseup', stopDrag);
    };

    /**
     * - Called when the user drags the gradetable
     * - Calculates targetLeft, which is the desired position
     *   of the grade table relative to its leftmost position, using:
     *   - the new x position of the user's mouse pointer;
     *   - the gradebook's current x position, and;
     *   - the value of maxScroll (gradetable width - container width).
     * - Updates the position and appearance of the gradetable.
     */
    var onDragTable = function(e) {
        var offset = e.pageX - mouseOrigin;
        var targetLeft = clamp(tableOrigin + offset, maxScroll, 0);
        updateHorizontalPosition(targetLeft);
        setShadows(targetLeft);
    };

    var stopDrag = function() {
        $body.removeClass('no-select');
        $body.unbind('mousemove', onDragTable);
        $body.unbind('mouseup', stopDrag);
    };

    var setShadows = function(left) {
        var padding = 30;

        var leftPercent = clamp(-left / padding, 0, 1);
        $leftShadow.css('opacity', leftPercent);

        var rightPercent = clamp((maxScroll + left) / padding, 0, 1);
        $rightShadow.css('opacity', rightPercent);
    };

    var clamp = function(val, min, max) {
        if(val > max) { return max; }
        if(val < min) { return min; }
        return val;
    };

    /**
     * - Called when the browser window is resized.
     * - Recalculates maxScroll (gradetable width - container width).
     * - Calculates targetLeft, which is the desired position
     *   of the grade table relative to its leftmost position, using:
     *   - the gradebook's current x position, and:
     *   - the new value of maxScroll
     * - Updates the position and appearance of the gradetable.
     */
    var onResizeTable = function() {
        maxScroll = $gradeTable.width() - $grades.width();
        var targetLeft = clamp($gradeTable.position().left, maxScroll, 0);
        updateHorizontalPosition(targetLeft);
        setShadows(targetLeft);
    };

    /**
     * - Called on table drag and on window (table) resize.
     * - Takes a integer value for the desired (pixel) offset from the left
     *   (zero/origin) position of the grade table.
     * - Uses that value to position the table relative to its leftmost
     *   possible position within its container.
     *
     *   @param {Number} left - The desired pixel offset from left of the
     *     desired position. If the value is 0, the gradebook should be moved
     *     all the way to the left side relative to its parent container.
     */
    var updateHorizontalPosition = function(left) {
        $grades.scrollLeft(left);
    };

    var highlightRow = function() {
        $element.find('.highlight').removeClass('highlight').find('.promote-grade').css('display', 'none');
        var index = $(this).index();
        var $student_tr = $studentTable.find('tr').eq(index + 1);
        $student_tr.addClass('highlight');
        $gradeTable.find('tr').eq(index + 1).addClass('highlight');
    };

    var filter = function() {
        var term = $(this).val();
    };

    var $first_row = $gradeTable.find("tbody tr").first();
    var keys_dict = {},
        keys_list = [];
    $first_row.children().each(function () {
       var category = $(this).data('category'),
           usage_id = $(this).data('usage-id');
       if (usage_id != "") {
           if (keys_dict[category] == undefined) {
               keys_dict[category] = []
           }
           keys_dict[category].push(usage_id);
           keys_list.push(usage_id);
       }
    });
    var course_id = window.location.pathname.split('/')[2],
        override_link = '/api/grades/v1/gradebook/' + course_id + '/undo-override';

    $studentTable.on('click', '.indicate-icon a', function (e) {
        e.preventDefault();
        /*
        $.post(
            $(this).attr('href'),
            {user_id: $(this).parents('tr').data('id'), usage_ids: JSON.stringify(keys_list)},
            function (data) {
                for (var i in data) {
                    var id = '#' + i,
                        v = data[i],
                        $target = $gradeTable.find(id);

                    $target.find('.indicate-icon .fa-check').remove();
                    $target.find('td').each(function () {
                        var index = $(this).index(),
                            grade_data = v[index];
                        $(this).attr({
                            'class': grade_data['class'],
                            'title': grade_data['detail'],
                            'data-percent': grade_data['percent'],
                            'data-usage-id': grade_data['usage_key']
                        }).find('.score').text(grade_data['grade']);

                        if ($(this).find('.indicate-icon .fa-check').length == 0) {
                            if (grade_data['override'] == true) {
                                if (grade_data['grade'] == 100) {
                                    $(this).find('.indicate-icon').html('<i class="fa fa-check"></i>')
                                }
                                else {
                                    $(this).find('.indicate-icon').append('<i class="fa fa-check"></i>')
                                }
                            }
                        }
                    });
                }
            }
        );*/
        var target_id = $(this).parents('tr').index(),
            user_id = $(this).parents('tr').data('id'),
            usage_ids = JSON.stringify(keys_list),
            user_name = $(this).parents('td').find('a').eq(1).text();
        $('#revert-override').find('p strong').text(user_name);
        $('.revert-confirm').off('click');
        $('.revert-confirm').on('click',function () {

            $.post(
                override_link,
                {user_id: user_id, usage_ids: usage_ids},
                function (data) {
                    for (var i in data) {
                        var id = '#' + i,
                            v = data[i],
                            $target = $gradeTable.find(id);

                        $target.find('.indicate-icon .fa-check').remove();
                        $target.find('td').each(function () {
                            var index = $(this).index(),
                                grade_data = v[index];
                            $(this).attr({
                                'class': grade_data['class'],
                                'title': grade_data['detail'],
                                'data-percent': grade_data['percent']
                            }).find('.score').text(grade_data['grade']);

                        });
                        $studentTable.find('tbody tr').eq(target_id).find('.indicate-icon a').remove()
                    }
                    $("#revert-override").iziModal('close');
                    $studentTable.find('tbody tr').eq(target_id).find('a').notify("Success!", {position: 'right-middle'});
                    $studentTable.find('.notifyjs-container').css({"line-height": "20px", "top": "6px"})
                }
            )
        });
    });

    $gradeTable.find('tr td .score').keypress(function (e) {
            if (e.which == 13) {
                $(this).blur();
            }
        });
    $gradeTable.find('tr td .score').focusout(function () {
        var before = Math.round($(this).parent().attr('data-percent')*100),
            now = parseInt($(this).text());
        if (isNaN($(this).text())) {
            $(this).notify("Please input a valid number", {position: 'top', className: 'error'});
            $(this).parent().find('.undo-grade').show();
        }
        else if (now < before || now > 100) {
            $(this).notify("Please input a score between " + before + " and 100", {position: 'top', className: 'error'});
            $(this).parent().find('.undo-grade').show();
        }
        else if (now > before) {
            $(this).parent().find('.undo-grade').show();
            promote_log_info($(this).parent())
        }
        else {
            $(this).parent().find('.undo-grade').hide();
        }
        $gradeTable.find(".notifyjs-container").css("line-height", "20px")
    });

    $edit.click(function () {
        $(this).css('display', 'none');
        $edit_siblings.css('display', 'inline-block');
        var grade_html = $gradeTable.find('tbody').html();
        sessionStorage.setItem('grade_html', grade_html);
        grade_log = {};
        $gradeTable.find('.indicate-icon .fa-check').css('display', 'none');
        $studentTable.find('.indicate-icon .fa-undo').css('display', 'none');
        $gradeTable.find('tr td .score').each(function () {
            if ($(this).text() != '100') {
                $(this).attr('contenteditable', true)   
            }
        });
    });
    $edit_siblings.click(function () {
        $edit_siblings.css('display', 'none');
        $edit.css('display', 'inline-block');
        $gradeTable.find('.indicate-icon .fa-check').css('display', 'block');
        $studentTable.find('.indicate-icon .fa-undo').css('display', 'block');
        $gradeTable.find('.undo-grade').hide();
        if ($(this).hasClass('cancel-grade')) {

            $gradeTable.find('tbody').html(sessionStorage.getItem('grade_html'));
        }
        else {
            var log = JSON.stringify(grade_log),
                grade_html = sessionStorage.getItem('grade_html');
            if (log != '{}') {
                $.post(
                    '/api/grades/v1/gradebook/' + course_id + '/bulk-update',
                    {log: log, number_of_sections: keys_list.length},
                    function (data) {
                        $.each(data, function (i, item) {
                            if (item['success'] == true) {
                                var id = '#' + i,
                                v = item['grade_data'],
                                $target = $gradeTable.find(id);
                                $target.find('td').each(function () {
                                    var index = $(this).index(),
                                        grade_data = v[index];
                                    $(this).attr({
                                        'class': grade_data['class'],
                                        'title': grade_data['detail'],
                                        'data-percent': grade_data['percent'],
                                        'data-usage-id': grade_data['usage_key']
                                    }).find('span').first().text(grade_data['grade']);
                                    if ($(this).find('.indicate-icon .fa-check').length == 0) {
                                        if (grade_data['override'] == true) {
                                            $(this).find('.indicate-icon').append('<i class="fa fa-check"></i>')
                                        }
                                    }
                                });
                            }
                        });
                        $studentTable.find('tbody tr td').each(function () {
                            var id = $(this).parent().data('id');
                            if (id in data) {
                                if (data[id]['grade_data'][0]['override'] == true) {
                                    $(this).find('.indicate-icon').html('<a href=' + override_link + '><i class="fa fa-undo"></i></a>');
                                    $(this).find('.indicate-icon a').attr('data-izimodal-open', '#revert-override')
                                }
                            }
                        });
                        var position = 'right';
                        //if ($(window).width() <= 725) {
                        //    position = 'right'
                        //}
                        $edit.notify('saved successfully!', {position: position});
                    }
                )

                .fail(function () {
                    $gradeTable.find('tbody').html(grade_html);
                });
            }
        }
        $gradeTable.find('tr td .score').each(function () {
            $(this).removeAttr('contenteditable')
        });
        sessionStorage.clear();
        grade_log = {}
    });
    //if ($studentTable.find('tr').hasClass('promoted')) {
    //    $studentTable.find('tr .promote-grade').addClass('undo-grade');
    //}
    //$gradeTable.on('mouseenter', 'tbody td', function () {
    //    if ($edit.css('display') == 'none') {
    //        if ($(this).hasClass('grade-promoted')) {
    //            $(this).find('.undo-grade').css('display', 'inline-block');
    //        }
    //        else {
    //            $(this).find('.promote-section').css('display', 'inline-block')
    //        }
    //    }
    //}).on('mouseleave', 'tbody td', function () {
    //    if ($edit.css('display') == 'none') {
    //        $(this).find('a').css('display', 'none');
    //    }
    //});

    function promote_log_info($el) {
        var $parent = $el.parent(),
            id = $parent.data('id'),
            category = $el.data('category'),
            title = $el.attr("title"),
            usage_id = $el.data('usage-id'),
            override_score = parseInt($el.find('.score').text());

        if (grade_log[id] == undefined) {
            grade_log[id] = {}
        }
        if (category == 'Total') {
            for (let i = 0; i < keys_list.length; i++) {
                grade_log[id][keys_list[i]] = override_score
            }
        }
        else if (title.indexOf('Average') != -1) {
            for (let i = 0; i < keys_dict[category].length; i++) {
                grade_log[id][keys_dict[category][i]] = override_score
            }
        }
        else if (usage_id != '') {
            grade_log[id][usage_id] = override_score
        }
        console.log(grade_log)
    }
    function undo_log_info($el) {
        var $parent = $el.parent(),
            id = $parent.data('id'),
            category = $el.data('category'),
            title = $el.attr("title"),
            usage_id = $el.data('usage-id');

        if (grade_log[id] == undefined) {
            return
        }
        else if (category == 'Total') {
           let ele;
           for (ele in keys_list) {
               if (keys_list[ele] in grade_log[id]) {
                   delete grade_log[id][keys_list[ele]]
               }
           }
        }
        else if (title.indexOf('Average') != -1) {
            let ele;
            for (ele in keys_dict[category]) {
                if (keys_dict[category][ele] in grade_log[id]) {
                    delete grade_log[id][keys_dict[category][ele]]
                }
            }
        }
        else if (usage_id != '') {
            if (usage_id in grade_log[id]) {
                delete grade_log[id][usage_id]
            }
        }

        if (grade_log[id].length == 0) {
            delete grade_log[id]
        }
    }

    function reset_grade() {
        var $parent = $(this).parents('td');
        $parent.find('.score').text(Math.round($parent.attr('data-percent')*100));
        $(this).css('display', 'none');
        undo_log_info($(this).parents('td'))
    }
    $gradeTable.on('click', 'a.undo-grade', reset_grade);

    $leftShadow.css('height', tableHeight + 'px');
    $grades.append($leftShadow).append($rightShadow);
    setShadows(0);
    $grades.css('height', tableHeight+16);
    $gradeTable.bind('mousedown', startDrag);
    $element.find('tr').bind('mouseenter', highlightRow).bind('mouseleave', function () {
        $element.find('.highlight').removeClass('highlight');
    });
    $search.bind('keyup', filter);
    $(window).bind('resize', onResizeTable);
    
    $(".active-filter button").click(function () {
        window.location = window.location.pathname
    })
};
