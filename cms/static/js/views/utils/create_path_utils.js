/**
 * Provides utilities for validating libraries during creation.
 */
define(['jquery', 'gettext', 'common/js/components/utils/view_utils', 'js/views/utils/create_utils_base'],
    function($, gettext, ViewUtils, CreateUtilsFactory) {
        'use strict';
        return function(selectors, classes) {
            var keyLengthViolationMessage = gettext('The combined length of the organization and library code fields cannot be more than <%=limit%> characters.');
            var keyFieldSelectors = []; //[selectors.org, selectors.number];
            var nonEmptyCheckFieldSelectors = [selectors.name]; //, selectors.org, selectors.number

            CreateUtilsFactory.call(this, selectors, classes, keyLengthViolationMessage, keyFieldSelectors, nonEmptyCheckFieldSelectors);

            this.create = function(pathInfo, successHandler, errorHandler) {
                $.post(
                    //'/library/',
                    '/api/proxy/discovery/api/v1/programs/',
                    pathInfo
                ).done(function(data) {
                    successHandler(data);
                    //handler(data)
                    //ViewUtils.redirect(data.url);
                }).fail(function(jqXHR, textStatus, errorThrown) {
                    var obj = $.parseJSON(jqXHR.responseJSON) //.api_error_message
                    errorHandler(obj);
                    //if (obj.textStatus)
                    //debugger
                    /*var reason = errorThrown;
                    if (jqXHR.responseText) {
                        try {
                            var detailedReason = $.parseJSON(jqXHR.responseText).ErrMsg;
                            if (detailedReason) {
                                reason = detailedReason;
                            }
                        } catch (e) {}
                    }
                    handler(reason);*/
                });
            };
        };
    });
