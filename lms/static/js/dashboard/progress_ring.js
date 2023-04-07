$(document).ready(function () {
   $(".progress-icon").each(function () {
        var $progressRing = $(this).find('.progress-ring');
        var progressRing = $(this).find('.progress-ring')[0],
            percent = $progressRing.data('percent'),
            circle = $(this).find('.progress-ring__circle')[0]
        if (!circle) return
        var circleBg = $(this).find('.progress-ring__circle-bg')[0],
            radius = circle.r.baseVal.value,
            size = (radius + 7) * 2,
            circumference = radius * 2 * Math.PI,
            offset = circumference - percent / 100 * circumference;
        progressRing.style.height = size + "px";
        progressRing.style.width = size + "px";
        progressRing.style.strokeDasharray = circumference + " " + circumference;
        progressRing.style.strokeDashoffset = circumference;
        circle.style.strokeDashoffset = offset;
        circle.style.transformOrigin = (radius + 6) + "px " + (radius + 6) + "px";
        circleBg.style.strokeDashoffset = circumference - 100 / 100 * circumference;
      });
});
