// leanModal v1.1 by Ray Stone - http://finelysliced.com.au
// Dual licensed under the MIT and GPL

// Updated to prevent divs with duplicate IDs from being rendered.

(function($) {
    $.fn.extend({
        leanModal: function(options) {
            var defaults = {
                top: 100,
                overlay: 0.5,
                closeButton: null
            };

            // Only append the overlay element if it isn't already present.
            if ($("#lean_overlay").length == 0) {
                var overlay = $("<div id='lean_overlay'></div>");
                $("body").append(overlay);
            }

            options = $.extend(defaults, options);
            return this.each(function() {
                var o = options;
                $(this).click(function(e) {
                    var modal_id = $(this).attr("href");
                    var $modal = $(modal_id)
                    $("#lean_overlay").click(function() {
                        close_modal(modal_id)
                    });
                    $('.close-button-wrapper i', $modal).click(function () {
                        close_modal(modal_id)
                    })
                    $(o.closeButton).click(function() {
                        close_modal(modal_id)
                    });
                    var $modal = $(modal_id)
                    $modal.css({'display':'block'})
                    $modal.removeClass('hidden')
                    $("#lean_overlay").show()

                    e.preventDefault()
                })
            });

            function close_modal(modal_id) {
                var $modal = $(modal_id)
                $modal.addClass('hidden')
                $("#lean_overlay").hide()
            }
        }
    })
})(jQuery);
