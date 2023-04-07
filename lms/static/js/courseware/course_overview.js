$(function () {

    var descriptionInit = function () {
        let p = new Promise(function (resolve) {
            setTimeout(function () {
                var $courseDescription = $('.course-description');
                var $description = $('.subtitle-description-wrapper');
                if ($description.height() >= 172) {
                    $courseDescription.addClass('extend-mode');
                }
                var $subtitle = $courseDescription.find('.subtitle');
                if ($subtitle.height() <= 16) {
                    $courseDescription.addClass('no-title-mode');
                }
                resolve()
            }, 200)
        })
        return p
    }

    var skeletonRemove = function() {
        return new Promise(function (resolve) {
            setTimeout(function () {
                $('.container .intro').removeClass('skeleton')
                resolve()
            }, 100)
        })
    }

    var eventInit = function() {
        $('body').delegate('.extend-link', 'click', function (e) {
            var $src = $(e.currentTarget);
            var $courseDescription = $src.parent('.course-description');
            $courseDescription.toggleClass('all-paragraphs');
        })
    }

    // entrance
    skeletonRemove()
        .then(descriptionInit)
        .then(eventInit)

})
