import * as gettext from 'gettext';
import * as Section from 'js/models/section';
import * as TextbookCollection from 'js/collections/textbook';
import * as ListTextbooksView from 'js/views/list_textbooks';
import './base';

import React from 'react';
import ReactDOM from 'react-dom';
import {QuestionMark} from '../../../../lms/static/js/QuestionMark';

function QuestionMarkWrapper(element, tooltip) {
    ReactDOM.render(
      React.createElement(QuestionMark, {tooltip:$(element).data('title') || tooltip}, null),
      element
    );
}

'use strict';
export default function TextbooksFactory(textbooksJson) {
    var textbooks = new TextbookCollection(textbooksJson, {parse: true}),
        tbView = new ListTextbooksView({collection: textbooks, QuestionMarkWrapper});
    var $contentPrimary = $('.content-primary')
    $contentPrimary.append(tbView.render().el);
    $('.nav-actions .new-button').click(function(event) {
        tbView.addOne(event);
    });
    $(window).on('beforeunload', function() {
        var dirty = textbooks.find(function(textbook) { return textbook.isDirty(); });
        if (dirty) {
            return gettext('You have unsaved changes. Do you really want to leave this page?');
        }
    });
};

export {TextbooksFactory}
