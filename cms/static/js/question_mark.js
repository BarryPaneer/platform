import React from 'react';
import ReactDOM from 'react-dom';
import {QuestionMark} from '../../../lms/static/js/QuestionMark';

window.LearningTribes = window.LearningTribes || {};
window.LearningTribes.QuestionMark = function (element, tooltip) {
    if (element != null){
        ReactDOM.render(
          React.createElement(QuestionMark, {tooltip:$(element).data('title') || tooltip}, null),
          element
        );
    }
}
