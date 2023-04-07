$(document).ready(function() {
    $('ul.tabs li').click(function() {
        $('ul.tabs li').removeClass('enabled');
        $(this).addClass('enabled');

        var data_class = '.' + $(this).attr('data-class');

        $('.tab').slideUp();
        $(data_class + ':hidden').slideDown();
    });

    $(document).on('click', '.learner-unroll-button', function () {
        $.ajax({
          url: "/change_enrollment",
          type: "POST",
          data: {enrollment_action: "unenroll", course_id: $(this).data("course_id")},
          success: function () {
            location.reload()
          },
          error: function(jqXHR, textStatus, errorThrown) {
            $('#unenroll_error').html(jqXHR.responseText).css("display", "block");
          }
        })
      })
});
