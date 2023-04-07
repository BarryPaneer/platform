import * as momentTemp from 'moment'
import './commerce/credit.js'
import './dashboard/credit.js'
import './dashboard/donation.js'
import './dashboard/dropdown.js'
import './dashboard/legacy.js'
import './dashboard/progress_ring.js'
import './dashboard/track_events.js'

window.moment = momentTemp

const Dashboard = function () {
    const initializatie = ()=>{
        setTimeout(()=>{
            //these 2 lines needs to be rewrite and test.
            $('.last-activity').removeClass('skeleton')
            $('.course-container .course').removeClass('skeleton')
        },500)
    }

    var slidesNumber = $('.my-courses > .listing-courses > .course-item').length;
    var slidesNumberBookmark = $('.my-bookmarks > .listing-bookmarks > .bookmark-item').length;

    if (shouldInit(slidesNumber)) {
      courseSwiperInit();
    }

    if (shouldInit(slidesNumberBookmark)) {
      bookmarkSwiperInit();
    }

    function shouldInit(number) {
      return ((document.body.offsetWidth < 768) && (number > 1))
            || ((document.body.offsetWidth < 992) && (number > 2))
            || ((document.body.offsetWidth < 1200) && (number > 3))
            || ((document.body.offsetWidth >= 1200))
    }

    function courseSwiperInit() {
      new Swiper('.my-courses', {
          slidesPerView: 'auto',
          spaceBetween: 13,
          slidesOffsetAfter:160,

          navigation: {
            nextEl: '.my-courses .swiper-button-next',
            prevEl: '.my-courses .swiper-button-prev',
          },
          pagination: {
            el: '.my-courses .swiper-pagination',
            clickable: true,
          },
          on: {
            init: function () {
                setTimeout(()=>{
                    $('.my-courses article.skeleton, .last-activity').removeClass('skeleton')
                },500)
                $('.my-courses article.skeleton').removeClass('skeleton')
            },
          },
      });
    }

    function bookmarkSwiperInit() {
        new Swiper('.my-bookmarks', {
          slidesPerView: 'auto',
          spaceBetween: 13,
          slidesOffsetAfter: 160,

          navigation: {
            nextEl: '.my-bookmarks .swiper-button-next',
            prevEl: '.my-bookmarks .swiper-button-prev',
          },
          pagination: {
            el: '.my-bookmarks .swiper-pagination',
            clickable: true,
          },
      });
    }

    $(".my-courses .swiper-button-next").on("click",function() {
        var courseSwiper = document.querySelector('.my-courses').swiper
        var width = courseSwiper.slides.outerWidth()
        var index = courseSwiper.realIndex
        var translate = courseSwiper.translate
        console.log('wid', width, 'index', index, 'translate', translate)
    })

    $(".my-bookmarks .swiper-button-next").on("click",function() {
        var bookmarkSwiper = document.querySelector('.my-bookmarks').swiper
        var space_between = bookmarkSwiper.params.spaceBetween
        var width = bookmarkSwiper.slides.outerWidth()
        var index = bookmarkSwiper.activeIndex
        var translate = bookmarkSwiper.translate
        var border_left = parseInt($('.bookmark-item').css("border-left-width"))
        var border_right = parseInt($('.bookmark-item').css("border-right-width"))
        console.log('width', width, 'index', index, 'translate', translate)
    })

    $(function () {
        initializatie()
    })
}

export {Dashboard}
