"use strict";

!function () {
  var today = moment(),
      event_list = document.querySelector('.ilt-events-list');

  var isDayInEvent = function isDayInEvent(ev, day) {
    return ev.start_date.isSame(day, 'day') || ev.end_date.isSame(day, 'day') || day.isBetween(ev.start_date, ev.end_date);
  };

  var filterEventsByDay = function filterEventsByDay(evs, day) {
    return evs.filter(function (ev) {
      return isDayInEvent(ev, day);
    });
  };

  function Calendar(selector, events, availableEvents) {
    this.el = document.querySelector(selector);
    this.el.innerHTML = '';
    this.events = events;
    this.availableEvents = availableEvents;
    this.eventsDisplayType = 'all'; // 'my'

    this.current = moment().date(1);
    this.next = true;
    this.draw();
    this.initSwiper(false);
    this.initTypeSwitcher();
  }

  Calendar.prototype.draw = function () {
    //Create Header
    this.drawHeader(); // Draw week day names

    this.drawDayName(); //Draw Month

    this.drawMonth();
  };

  Calendar.prototype.drawHeader = function () {
    var self = this;

    if (!this.header) {
      //Create the header elements
      this.header = createElement('div', 'header');
      this.header.className = 'header';
      this.title = createElement('h2', 'month-name');
      this.viewSessionButton = createElement('a', 'view-session');
      this.viewSessionButton.innerHTML = '<span>View sessions</span><i class="far fa-chevron-right"/>';
      this.viewSessionButton.setAttribute('href', '#');
      this.navigator = createElement('div', 'calendar-nav');
      var right = createElement('span', 'nav-right far fa-chevron-right');
      right.addEventListener('click', function () {
        self.nextMonth();
      });
      var left = createElement('span', 'nav-left far fa-chevron-left');
      left.addEventListener('click', function () {
        self.prevMonth();
      }); //Append the Elements

      this.navigator.appendChild(left);
      this.navigator.appendChild(right);
      this.header.appendChild(this.title);
      this.header.appendChild(this.navigator);
      this.header.appendChild(this.viewSessionButton);
      this.viewSessionButton.addEventListener('click', function (e) {
        $("#calendar").hide();
        $(".ilt-events-wrapper").removeClass("mobile-events");
        self.drawAllEvents();
        e.stopPropagation();
        e.preventDefault();
        return false;
      });
      this.el && this.el.appendChild(this.header);
    }

    this.title.innerHTML = this.current.format('MMMM YYYY');
    var icon = createElement('i', 'far fa-calendar-week');
    this.title.insertAdjacentElement('afterbegin', icon);
  };

  Calendar.prototype.drawDayName = function () {
    var self = this,
        name_list = moment.weekdaysShort();

    if (!this.day_names) {
      this.day_names = createElement('div', 'day-names');

      for (var i = 0; i < name_list.length; i++) {
        var name = createElement('div', 'day-name' + ' weekday-' + i, name_list[i]);
        this.day_names.appendChild(name);
      }

      this.el && this.el.appendChild(this.day_names);
    }

    $(".day-names .day-name").removeClass('highlight');
  };

  Calendar.prototype.drawMonth = function () {
    var self = this;

    if (this.month) {
      this.oldMonth = this.month;
      this.oldMonth.className = 'month out ' + (!self.next ? 'next' : 'prev');
      this.oldMonth.addEventListener('webkitAnimationEnd', function () {
        self.oldMonth.parentNode.removeChild(self.oldMonth);
        self.month = createElement('div', 'month');
        self.backFill();
        self.currentMonth();
        self.fowardFill();
        self.el.appendChild(self.month);
        window.setTimeout(function () {
          self.month.className = 'month in ' + (!self.next ? 'next' : 'prev');

          if (today.month() === self.current.month()) {
            var highlight_selector = ".weekday-" + today.day(),
                active_day = document.querySelector(".today");
            $(highlight_selector).addClass("highlight");
            self.drawAllEvents();
          }
        }, 16);
      });
    } else {
      this.month = createElement('div', 'month');
      this.el && this.el.appendChild(this.month);
      this.backFill();
      this.currentMonth();
      this.fowardFill();
      this.month.className = 'month new';

      if (today.month() === self.current.month()) {
        var highlight_selector = ".weekday-" + today.day();
        $(highlight_selector).addClass("highlight");
      }
    }
  };

  Calendar.prototype.backFill = function () {
    var clone = this.current.clone();
    var dayOfWeek = clone.day();

    if (!dayOfWeek) {
      return;
    }

    clone.subtract('days', dayOfWeek + 1);

    for (var i = dayOfWeek; i > 0; i--) {
      this.drawDay(clone.add('days', 1));
    }
  };

  Calendar.prototype.fowardFill = function () {
    var clone = this.current.clone().add('months', 1).subtract('days', 1);
    var dayOfWeek = clone.day();

    if (dayOfWeek === 6) {
      return;
    }

    for (var i = dayOfWeek; i < 6; i++) {
      this.drawDay(clone.add('days', 1));
    }
  };

  Calendar.prototype.currentMonth = function () {
    var clone = this.current.clone();

    while (clone.month() === this.current.month()) {
      this.drawDay(clone);
      clone.add('days', 1);
    }
  };

  Calendar.prototype.getWeek = function (day) {
    if (!this.week || day.day() === 0) {
      this.week = createElement('div', 'week');
      this.month.appendChild(this.week);
    }
  };

  Calendar.prototype.drawDay = function (day) {
    var self = this;
    this.getWeek(day); //Outer Day

    var outer = createElement('div', this.getDayClass(day));
    var current_day = day.clone();
    outer.addEventListener('click', function () {
      $(".ilt-calendar-wrapper").removeClass('no-upcoming-session');

      if (window.outerWidth < 768) {
        $("#calendar").hide();
        $(".ilt-events-wrapper").removeClass("mobile-events");
      }

      self.openDay(this, current_day);
      var week_days = document.getElementsByClassName('day');

      for (var i = 0; i < week_days.length; i++) {
        week_days[i].classList.remove('active-day');
        week_days[i].classList.add('inactive-day');
      }

      this.classList.add("active-day");
      this.classList.remove("inactive-day");
      $(".highlight").removeClass("highlight");
      var highlight_selector = ".weekday-" + current_day.day();
      $(highlight_selector).addClass("highlight");
    });
    var day_wrapper = createElement('span', 'day-wrapper'); //Day Number

    var number = createElement('span', 'day-number', day.format('DD'));
    var dayEvents = filterEventsByDay(this.events, day);

    if (dayEvents.length > 0) {
      outer.classList.add('has-event');
    } else {
      var dayAvailableEvents = filterEventsByDay(this.availableEvents, day);
      if (dayAvailableEvents.length) outer.classList.add('has-open-event');
    } // outer.appendChild(name);


    day_wrapper.appendChild(number);
    outer.appendChild(day_wrapper); //outer.appendChild(events);

    this.week.appendChild(outer);
  };

  Calendar.prototype.getDayClass = function (day) {
    var classes = ['day', 'weekday-' + day.day()];

    if (day.month() !== this.current.month()) {
      classes.push('other');
    } else if (today.isSame(day, 'day')) {
      classes.push('today');
    }

    return classes.join(' ');
  };

  Calendar.prototype.openDay = function (el, day) {
    var details, arrow;
    var currentOpened = document.querySelector('.ilt-details'); //Check to see if there is an open detais box on the current row

    if (currentOpened && currentOpened.parentNode === el.parentNode) {
      details = currentOpened;
      arrow = document.querySelector('.arrow');
    } else {
      //Close the open events on differnt week row
      //currentOpened && currentOpened.parentNode.removeChild(currentOpened);
      if (currentOpened) {
        currentOpened.addEventListener('webkitAnimationEnd', function () {
          currentOpened.parentNode.removeChild(currentOpened);
        });
        currentOpened.addEventListener('oanimationend', function () {
          currentOpened.parentNode.removeChild(currentOpened);
        });
        currentOpened.addEventListener('msAnimationEnd', function () {
          currentOpened.parentNode.removeChild(currentOpened);
        });
        currentOpened.addEventListener('animationend', function () {
          currentOpened.parentNode.removeChild(currentOpened);
        });
        currentOpened.className = 'ilt-details out';
      } //Create the Details Container


      details = createElement('div', 'ilt-details in'); //Create the arrow

      var arrow = createElement('div', 'arrow'); //Create the event wrapper

      details.appendChild(arrow);
      el.parentNode.appendChild(details);
    }

    var todaysEvents = filterEventsByDay(this.computedAllEvents(), day);
    this.renderEvents(todaysEvents, details);
    this.drawEventsList(todaysEvents, day);
    var offset = Math.abs(el.offsetLeft - (el.previousSibling || el.nextElementSibling).offsetLeft) / 2;
    arrow.style.left = el.offsetLeft - el.parentNode.offsetLeft + offset + 'px';
  };

  Calendar.prototype.convert_date = function (start, end) {
    var date_format = "MM/DD HH:mm";

    if (start.isSame(end, 'day')) {
      date_format = 'HH:mm';
    } else if (moment.locale() == 'fr') {
      date_format = "DD/MM HH:mm";
    }

    return start.format(date_format) + "\xa0-\xa0" + end.format(date_format);
  };

  Date.prototype.addHours = function (h) {
    this.setTime(this.getTime() + h * 60 * 60 * 1000);
    return this;
  };

  Calendar.prototype.teacherTimeToLocal = function (time, offsetHours) {
    time += time.toUpperCase().endsWith('Z') ? '' : 'Z';
    var dateObj = new Date(time);
    dateObj.addHours(-offsetHours);
    return dateObj.toISOString();
  };

  Calendar.prototype.drawEventsList = function (events, day) {
    var self = this;
    event_list.innerHTML = '';
    this.swiper.destroy();

    if (events.length > 0) {
      events.forEach(function (ev) {
        var left_info2;
        var wrapper = createElement('div', 'ilt-event swiper-slide'),
            session_info = createElement('div', 'ilt-event-info'),
            link = createElement('a', 'ilt-link', ''),
            course_name = createElement('h3', 'ilt-event-title', ev.course + " : "),
            title = createElement('h3', 'ilt-event-title', ev.title),
            time = createElement('span', 'ilt-event-time', self.convert_date(ev.start_date, ev.end_date) + '\xa0 (' + ev.timezone + ')'),
            location = createElement('span', 'ilt-event-location', ev.location),
            time_icon = createElement('i', 'far fa-clock', ''),
            location_icon = createElement('i', 'far fa-location-circle', ''),
            left_info = createElement('div', 'left-info'),
            right_info = createElement('div', 'right-info'),
            duration = createElement('span', 'ilt-event-duration', ev.duration + ' ' + ngettext('hour', 'hours', ev.duration)),
            duration_icon = createElement('i', 'far fa-history', ''),
            area = createElement('span', 'ilt-event-area', ev.area_region),
            area_icon = createElement('i', 'far fa-globe-stand', ''),
            address = createElement('span', 'ilt-event-address', ev.address),
            address_icon = createElement('i', 'far fa-location-circle', ''),
            zip_code = createElement('span', 'ilt-event-zip', moment.locale() == 'fr' ? ev.zip_code + ", " + ev.city : ev.city + ", " + ev.zip_code),
            zip_code_icon = createElement('i', 'far fa-location-circle', ''),
            location_id = createElement('span', 'ilt-event-location-id', ev.location_id),
            location_id_icon = createElement('i', 'far fa-map-marker-alt', ''),
            event_day = createElement('section', 'event-day', ''),
            event_day_name = createElement('div', 'event-day-name', day.format('MMM')),
            event_day_number = createElement('h2', 'event-day-number', day.date()),
            event_date = createElement('span', 'event-date', formatDate2(day.toDate(), 'en', '')),
            regexp = /(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?/;

        if (regexp.test(ev.location)) {
          var location = createElement('a', 'ilt-event-location', ev.location);
          location.href = ev.location;
          location.target = "_blank";
        } else {
          var location = createElement('span', 'ilt-event-location', ev.location);
        }

        link.href = ev.url;
        link.target = "_blank";
        time.insertAdjacentElement('afterbegin', time_icon);
        area.classList.add("hidden");

        if (ev.instructor) {
          var instructor = createElement('span', 'ilt-event-instructor', ev.instructor);
          var instructor_icon = createElement('i', 'far fa-user', '');
          instructor.insertAdjacentElement('afterbegin', instructor_icon);
          left_info2 = createElement('div', 'left-info');
          left_info2.appendChild(instructor);
        }

        location.insertAdjacentElement('afterbegin', location_icon);
        link.appendChild(course_name);
        link.appendChild(title);
        duration.insertAdjacentElement('afterbegin', duration_icon);
        area.insertAdjacentElement('afterbegin', area_icon);
        address.insertAdjacentElement('afterbegin', address_icon);
        zip_code.insertAdjacentElement('afterbegin', zip_code_icon);
        location_id.insertAdjacentElement('afterbegin', location_id_icon);

        if (ev.duration == undefined) {
          duration.classList.add("hidden");
        }

        if (ev.area_region == undefined) {
          area.classList.add("hidden");
        }

        if (ev.address == undefined) {
          address.classList.add("hidden");
        }

        if (ev.zip_code == undefined && ev.city == undefined) {
          zip_code.classList.add("hidden");
        }

        if (ev.location_id == undefined) {
          location_id.classList.add("hidden");
        }

        left_info.appendChild(time);
        left_info.appendChild(duration);
        left_info.appendChild(area);
        right_info.appendChild(location);
        right_info.appendChild(address);
        right_info.appendChild(zip_code);
        right_info.appendChild(location_id);
        session_info.appendChild(left_info);
        session_info.appendChild(right_info);
        if (left_info2) session_info.appendChild(left_info2);
        event_day.appendChild(event_day_name);
        event_day.appendChild(event_day_number);
        wrapper.appendChild(event_day);
        wrapper.appendChild(event_date);
        wrapper.appendChild(link);
        self.drawDownloadButton(ev, wrapper);
        wrapper.appendChild(session_info);
        event_list.appendChild(wrapper);
      });
      var loop = events.length > 1;
      this.initSwiper(loop);
      $(".upcoming-session").removeClass("hidden");

      if (loop) {
        $('.ilt-calendar-wrapper').find('.swiper-button-next').removeClass("swiper-button-disabled");
        $('#ilt-calendar').find('.swiper-pagination').removeClass('hide');
      } else {
        $('.ilt-calendar-wrapper').find('.swiper-button-next').addClass("swiper-button-disabled");
        $('#ilt-calendar').find('.swiper-pagination').addClass('hide');
      }
    } else {
      var empty_event = createElement('h3', 'ilt-empty-event', gettext('There are no training events scheduled for this day.'));
      event_list.appendChild(empty_event);
      $(".upcoming-session").addClass("hidden");
      $('.ilt-calendar-wrapper').find('.swiper-button-next').addClass("swiper-button-disabled");
      $('#ilt-calendar').find('.swiper-pagination').addClass('hide');
    }
  };

  Calendar.prototype.drawAllEvents = function () {
    var self = this;
    event_list.innerHTML = '';
    var upcomingEvents = this.computedAllEvents().filter(function (ev) {
      return today.isSameOrBefore(ev.end_date, 'day');
    });

    if (upcomingEvents.length > 0) {
      var event_length = 0;
      upcomingEvents.forEach(function (ev) {
        var clone_event_date;

        if (today.isSameOrBefore(ev.start_date)) {
          clone_event_date = ev.start_date.clone();
        } else {
          clone_event_date = today.clone();
        }

        while (clone_event_date.isSameOrBefore(ev.end_date) || clone_event_date.date() == ev.end_date.date()) {
          var left_info2 = void 0;
          var wrapper = createElement('div', 'ilt-event swiper-slide'),
              session_info = createElement('div', 'ilt-event-info'),
              link = createElement('a', 'ilt-link', ''),
              course_name = createElement('h3', 'ilt-event-title', ev.course + " : "),
              title = createElement('h3', 'ilt-event-title', ev.title),
              time = createElement('span', 'ilt-event-time', self.convert_date(ev.start_date, ev.end_date) + '\xa0(' + ev.timezone + ')'),
              time_icon = createElement('i', 'far fa-clock', ''),
              location_icon = createElement('i', 'far fa-location-circle', ''),
              left_info = createElement('div', 'left-info'),
              right_info = createElement('div', 'right-info'),
              duration = createElement('span', 'ilt-event-duration', ev.duration + ' ' + ngettext('hour', 'hours', ev.duration)),
              duration_icon = createElement('i', 'far fa-history', ''),
              area = createElement('span', 'ilt-event-area', ev.area_region),
              area_icon = createElement('i', 'far fa-globe-stand', ''),
              address = createElement('span', 'ilt-event-address', ev.address),
              address_icon = createElement('i', 'far fa-location-circle', ''),
              zip_code = createElement('span', 'ilt-event-zip', moment.locale() == 'fr' ? ev.zip_code + ", " + ev.city : ev.city + ", " + ev.zip_code),
              zip_code_icon = createElement('i', 'far fa-location-circle', ''),
              location_id = createElement('span', 'ilt-event-location-id', ev.location_id),
              location_id_icon = createElement('i', 'far fa-map-marker-alt', ''),
              event_day = createElement('section', 'event-day', ''),
              event_day_name = createElement('div', 'event-day-name', clone_event_date.format('MMM')),
              event_day_number = createElement('h2', 'event-day-number', clone_event_date.date()),
              event_date = createElement('span', 'event-date', formatDate2(clone_event_date.startOf('day').toDate(), 'en', '')),
              regexp = /(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?/;

          if (regexp.test(ev.location)) {
            var location = createElement('a', 'ilt-event-location', ev.location);
            location.href = ev.location;
            location.target = "_blank";
          } else {
            var location = createElement('span', 'ilt-event-location', ev.location);
          }

          link.href = ev.url;
          link.target = "_blank";
          time.insertAdjacentElement('afterbegin', time_icon);
          area.classList.add("hidden");

          if (ev.instructor) {
            var instructor = createElement('span', 'ilt-event-instructor', ev.instructor);
            var instructor_icon = createElement('i', 'far fa-user', '');
            instructor.insertAdjacentElement('afterbegin', instructor_icon);
            left_info2 = createElement('div', 'left-info');
            left_info2.appendChild(instructor);
          }

          location.insertAdjacentElement('afterbegin', location_icon);
          link.appendChild(course_name);
          link.appendChild(title);
          duration.insertAdjacentElement('afterbegin', duration_icon);
          area.insertAdjacentElement('afterbegin', area_icon);
          address.insertAdjacentElement('afterbegin', address_icon);
          zip_code.insertAdjacentElement('afterbegin', zip_code_icon);
          location_id.insertAdjacentElement('afterbegin', location_id_icon);

          if (ev.duration == undefined) {
            duration.classList.add("hidden");
          }

          if (ev.area_region == undefined) {
            area.classList.add("hidden");
          }

          if (ev.address == undefined) {
            address.classList.add("hidden");
          }

          if (ev.zip_code == undefined && ev.city == undefined) {
            zip_code.classList.add("hidden");
          }

          if (ev.location_id == undefined) {
            location_id.classList.add("hidden");
          }

          left_info.appendChild(time);
          left_info.appendChild(duration);
          left_info.appendChild(area);
          right_info.appendChild(location);
          right_info.appendChild(address);
          right_info.appendChild(zip_code);
          right_info.appendChild(location_id);
          session_info.appendChild(left_info);
          session_info.appendChild(right_info);
          if (left_info2) session_info.appendChild(left_info2);
          event_day.appendChild(event_day_name);
          event_day.appendChild(event_day_number);
          wrapper.appendChild(event_day);
          wrapper.appendChild(event_date);
          wrapper.appendChild(link);
          self.drawDownloadButton(ev, wrapper);
          wrapper.appendChild(session_info);
          event_list.appendChild(wrapper);
          clone_event_date.add(1, 'day');
          event_length += 1;
        }
      });
      var loop = event_length > 1;
      this.swiper.destroy();
      this.initSwiper(loop);

      if (loop) {
        $('.ilt-calendar-wrapper').find('.swiper-button-next').removeClass("swiper-button-disabled");
        $('#ilt-calendar').find('.swiper-pagination').removeClass('hide');
      }

      if (this.events.length) $(".ilt-calendar-wrapper").addClass('has-past-session');
      $(".ilt-calendar-wrapper").removeClass('no-upcoming-session');
    } else {
      $(".ilt-calendar-wrapper").addClass('no-upcoming-session');
      $('#ilt-calendar').find('.swiper-pagination').addClass('hide');
    }
  };

  Calendar.prototype.drawDownloadButton = function (ev, wrapper) {
    var _this = this;

    var div = createElement('div', 'button-group-wrapper');
    var invitationButton = createElement('a', 'ical-download invitation');
    var button = createElement('a', 'ical-download');
    wrapper.appendChild(div);
    div.appendChild(button);

    if (ev.enrolled) {
      var button_icon = createElement('i', 'far fa-calendar-plus', ''),
          invitation_button_icon = createElement('i', 'far fa-arrow-circle-down', ''),
          button_text = createElement('span', 'ical-download-text', gettext('Add to Calendar')),
          invitation_button_text = createElement('span', 'ical-download-text', gettext('Download the invitation'));

      if (event_list.classList.contains("show-invitation")) {
        div.appendChild(invitationButton);
      }

      button.appendChild(button_icon);
      button.appendChild(button_text);
      invitationButton.appendChild(invitation_button_icon);
      invitationButton.appendChild(invitation_button_text);
      button.addEventListener('click', function () {
        var cal = ics();
        var uid = ev.url.split("/").slice(-2, -1)[0];
        cal.addEvent(uid, ev.title, ev.course, ev.location, _this.teacherTimeToLocal(ev.start_at, ev.timezone_offset), _this.teacherTimeToLocal(ev.end_at, ev.timezone_offset));
        cal.download();
      });
      invitationButton.addEventListener('click', function () {
        window.location.href = "/download_invitation/" + ev.usage_id + "/" + ev.key + "/";
      });
    } else {
      initEnrollButton(button, ev);
    }

    return button;
  };

  Calendar.prototype.renderEvents = function (events, ele) {
    //Remove any events in the current details element
    var currentWrapper = ele.querySelector('.events');
    var wrapper = createElement('div', 'events in' + (currentWrapper ? ' new' : ''));
    events.forEach(function (ev) {
      var div = createElement('div', 'event');
      var square = createElement('div', 'event-category ' + ev.color);
      var span = createElement('span', '', ev.title);
      div.appendChild(square);
      div.appendChild(span);
      wrapper.appendChild(div);
    });

    if (!events.length) {
      var div = createElement('div', 'event empty');
      var span = createElement('span', '', gettext('No Events'));
      div.appendChild(span);
      wrapper.appendChild(div);
    }

    if (currentWrapper) {
      currentWrapper.className = 'events out';
      currentWrapper.addEventListener('webkitAnimationEnd', function () {
        currentWrapper.parentNode.removeChild(currentWrapper);
        ele.appendChild(wrapper);
      });
      currentWrapper.addEventListener('oanimationend', function () {
        currentWrapper.parentNode.removeChild(currentWrapper);
        ele.appendChild(wrapper);
      });
      currentWrapper.addEventListener('msAnimationEnd', function () {
        currentWrapper.parentNode.removeChild(currentWrapper);
        ele.appendChild(wrapper);
      });
      currentWrapper.addEventListener('animationend', function () {
        currentWrapper.parentNode.removeChild(currentWrapper);
        ele.appendChild(wrapper);
      });
    } else {
      ele.appendChild(wrapper);
    }
  };

  Calendar.prototype.drawLegend = function () {
    var legend = createElement('div', 'legend');
    var calendars = this.events.map(function (e) {
      return e.calendar + '|' + e.color;
    }).reduce(function (memo, e) {
      if (memo.indexOf(e) === -1) {
        memo.push(e);
      }

      return memo;
    }, []).forEach(function (e) {
      var parts = e.split('|');
      var entry = createElement('span', 'entry ' + parts[1], parts[0]);
      legend.appendChild(entry);
    });
    this.el && this.el.appendChild(legend);
  };

  Calendar.prototype.nextMonth = function () {
    this.current.add('months', 1);
    this.next = true;
    this.draw();
  };

  Calendar.prototype.prevMonth = function () {
    this.current.subtract('months', 1);
    this.next = false;
    this.draw();
  };

  window.Calendar = Calendar;

  function createElement(tagName, className, innerText) {
    var ele = document.createElement(tagName);

    if (className) {
      ele.className = className;
    }

    if (innerText) {
      ele.innderText = ele.textContent = innerText;
    }

    return ele;
  }

  Calendar.prototype.initSwiper = function (loop) {
    var swiper = new Swiper('#ilt-events', {
      slidesPerView: 1,
      spaceBetween: 20,
      loop: loop,
      cssMode: true,
      navigation: {
        nextEl: '#ilt-calendar .swiper-button-next',
        prevEl: '#ilt-calendar .swiper-button-prev'
      },
      pagination: {
        el: '#ilt-calendar .swiper-pagination'
      },
      keyboard: true
    });
    this.swiper = swiper;
  };

  Calendar.prototype.initTypeSwitcher = function (type) {
    var _this2 = this;

    this.eventsDisplayType = type;
    var $switcherWrapper = document.querySelector('.ilt-events-type-switcher-wrapper');
    if (!$switcherWrapper) return;
    $switcherWrapper.querySelectorAll('.ilt-events-type').forEach(function ($el, _, $els) {
      var type = $el.dataset.type;

      $el.onclick = function () {
        if (_this2.eventsDisplayType === type) return;
        $els.forEach(function ($el) {
          return $el.classList.remove('active');
        });
        $el.classList.add('active');
        _this2.eventsDisplayType = type;

        _this2.drawAllEvents();

        var $iltCalendarWrapper = document.querySelector('.ilt-calendar-wrapper');

        if ($iltCalendarWrapper) {
          $iltCalendarWrapper.classList.remove('ilt-calendar-wrapper--type-all');
          $iltCalendarWrapper.classList.remove('ilt-calendar-wrapper--type-my');
          $iltCalendarWrapper.classList.add('ilt-calendar-wrapper--type-' + type);
          $iltCalendarWrapper.classList.remove('has-past-session');
          $iltCalendarWrapper.classList.add('has-past-session');
        }
      };
    });
    this.drawAllEvents();
  };

  Calendar.prototype.computedAllEvents = function (type) {
    if (this.eventsDisplayType === 'my') return this.events;
    return this.events.concat(this.availableEvents);
  };

  $(".back-to-calendar").on('click', function () {
    $("#calendar").show();
    $(".ilt-events-wrapper").addClass("mobile-events");
  });

  function initEnrollButton(el, props) {
    var template = "<a class=\"ical-download\" @click=\"openEnroll\">\n    <span class=\"ical-download-text enroll-text\">{{ gettext('Enroll') }}</span><span class=\"secondary-text\">{{ seatsAvailable }} {{ seatsLeftStr }}</span>\n\n    <modal v-if=\"modalVisible\"\n        name=\"enroll-ilt\"\n        :title=\"gettext('Enroll')\"\n        confirmText=\"Enroll\"\n        @close=\"cancel\"\n        @confirm=\"confirm\"\n    >\n        <div v-if=\"accommodationEnabled\" class=\"ilt-registration-accommodation field\">\n            <span>{{ gettext(\"Accommodation Need\") }}: </span>\n            <switcher v-model=\"enrollment.accommodation\"></switcher>\n        </div>\n\n        <div class=\"ilt-registration-comment field\">\n            <label for=\"ilt-comment\">{{ gettext(\"Comment\") }}:</label>\n            <textarea id=\"ilt-comment\" v-model=\"enrollment.comment\" :placeholder=\"gettext('accommodation, preferences, specific diet...')\"></textarea>\n        </div>\n\n        <div class=\"ilt-registration-trip field\">\n            <label for=\"ilt-one-way-trip\">{{ gettext(\"Number of one way\") }}: </label>\n            <input type=\"text\" id=\"ilt-one-way-trip\" v-model=\"enrollment.number_of_one_way\">\n            <label for=\"ilt-return-trip\">{{ gettext(\"Number of return\") }}: </label>\n            <input type=\"text\" id=\"ilt-return-trip\" v-model=\"enrollment.number_of_return\">\n        </div>\n    </modal>\n</a>\n";
    return new Vue({
      el: el,
      template: template,
      data: function data() {
        return {
          accommodationEnabled: window.iltAccommodationEnabled === 'True',
          seatsAvailable: props.seats_available || 0,
          modalVisible: false,
          seatsLeftStr: ngettext('seat left', 'seats left', props.seats_available),
          enrollment: {
            accommodation: false,
            comment: '',
            number_of_one_way: '1',
            number_of_return: '1'
          }
        };
      },
      methods: {
        openEnroll: function openEnroll() {
          this.modalVisible = true;
        },
        cancel: function cancel() {
          this.modalVisible = false;
        },
        confirm: function confirm() {
          var _this3 = this;

          this.enroll().then(function () {
            _this3.modalVisible = false;
          });
        },
        enroll: function enroll() {
          var body = {
            session: props.key,
            request_info: Object.assign({}, this.enrollment, {
              accommodation: {
                "true": 'yes',
                "false": 'no'
              }[this.enrollment.accommodation] || this.enrollment.accommodation || ''
            })
          };
          return Vue.http.post(props.enrollment_url, body).then(function (resp) {
            resp.json().then(function (value) {
              LearningTribes.Notification.Info({
                title: gettext('ILT Enrollment'),
                message: gettext('Enrollment succeeded.')
              });
              initILTCalendar();
            });
          })["catch"](function (err) {
            console.error(err);
            LearningTribes.Notification.Error({
              title: gettext('ILT Enrollment'),
              message: gettext('Enrollment failed.')
            });
          });
        },
        gettext: window.gettext || function (v) {
          return v;
        }
      }
    });
  }

  Vue.http.interceptors.push(function (request, next) {
    if (request.method === 'POST') {
      request.headers.set('X-CSRFToken', $.cookie('csrftoken'));
    }

    next();
  });
}();

function initILTCalendar() {
  var locale = document.documentElement.lang;
  moment.locale(locale);
  $.ajax({
    url: '/enrolled_ilt_sessions',
    success: function success(data) {
      var enrolledEvents = data.ilt_sessions || [];
      var availableEvents = data.open_ilt_sessions || [];
      var allEvents = enrolledEvents.concat(availableEvents);
      var today = moment();
      var colors = ['orange', 'blue', 'yellow', 'green'];
      var has_upcoming_sessions = false;

      if (allEvents.length) {
        var sortEvent = function sortEvent(a, b) {
          if (a.start_date.isBefore(b.start_date)) return -1;

          if (a.start_date.isSame(b.start_date)) {
            if (a.end_date.isBefore(b.end_date)) return -1;
            return 1;
          }

          return 1;
        };

        allEvents.forEach(function (ev) {
          ev.start_date = moment(ev.start_at);
          ev.end_date = moment(ev.end_at);
          ev.color = colors[Math.floor(Math.random() * 4)];

          if (ev.end_date.isSame(today, 'day') || ev.end_date.isAfter(today, 'day')) {
            has_upcoming_sessions = true;
          }
        });
        enrolledEvents.forEach(function (ev) {
          ev.enrolled = true;
        });
        enrolledEvents.sort(sortEvent);
        availableEvents.sort(sortEvent);
        if (enrolledEvents.length) $(".ilt-calendar-wrapper").addClass('has-past-session');
        var calendar = new Calendar('#calendar', enrolledEvents, availableEvents);
        $('.ilt-calendar-wrapper').find('.swiper-button-next').addClass("swiper-button-disabled");

        if (has_upcoming_sessions) {
          $(".ilt-calendar-wrapper").removeClass('no-upcoming-session');
          calendar.drawAllEvents();
        }
      }
    }
  });
}

initILTCalendar();