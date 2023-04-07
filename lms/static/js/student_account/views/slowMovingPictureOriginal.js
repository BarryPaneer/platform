
window.Animation_SlowMovingPicture = function ($bgImg, $bg) {
  var lFollowX = 0,
      lFollowY = 0,
      x = 0,
      y = 0,
      friction = 1 / 30;

  function moveBackground() {
    x += (lFollowX - x) * friction;
    y += (lFollowY - y) * friction;


    var halfWidth = $bgImg.width()/2;
    var halfHeight = $bgImg.height()/2;
    var translationStr = 'translate(' + (-halfWidth + x) + 'px, ' + (-halfHeight + y) + 'px) scale(1.1)';

    $bgImg.css({
      'transform': translationStr
    });

    window.requestAnimationFrame(moveBackground);
  }

  $bg.on('mousemove', function(e) {
    var lMouseX = Math.max(-100, Math.min(100, $(window).width() / 4 - e.clientX));
    var lMouseY = Math.max(-100, Math.min(100, $(window).height() / 2 - e.clientY));
    lFollowX = (20 * lMouseX) / 100; // 100 : 12 = lMouxeX : lFollow
    lFollowY = (10 * lMouseY) / 100;
  });

  moveBackground();
}
