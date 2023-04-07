define([
    'jquery', 'gettext', 'js/models/settings/advanced', 'js/views/settings/advanced'
], function($, gettext, AdvancedSettingsModel, AdvancedSettingsView) {
    'use strict';
    return function(advancedDict, advancedGroup, advancedSettingsUrl, anderspinkBoardsList) {
        var advancedModel, editor;

        $('form :input')
            .focus(function() {
                $('label[for="' + this.id + '"]').addClass('is-focused');
            })
            .blur(function() {
                $('label').removeClass('is-focused');
            });
        
        // proactively populate advanced b/c it has the filtered list and doesn't really follow the model pattern
        if(anderspinkBoardsList.length == 0 ){
            delete advancedDict["anderspink_boards"]
            advancedGroup.find(f => f.name == "Pages").items.splice(1,1)
        }
        advancedModel = new AdvancedSettingsModel(advancedDict, {parse: true});
        advancedModel.url = advancedSettingsUrl;
        
        editor = new AdvancedSettingsView({
            el: $('.settings-advanced'),
            model: advancedModel,
            advancedGroup: advancedGroup,
            anderspinkBoardsList: formatBoards()
        });
        editor.render();

        function formatBoards(){
            return anderspinkBoardsList.length ==0 ? [] : [{"display_name": "", value : ""}, ...anderspinkBoardsList.map(b => {
                return {"display_name": b.text.length > 30 ? `${b.text.substring(0,30)}...`: b.text, "value" : b.value}})]
        }

        $('#deprecated-settings').click(function() {
            var $wrapperDeprecatedSetting = $('.wrapper-deprecated-setting'),
                $deprecatedSettingsLabel = $('.deprecated-settings-label');

            if ($(this).is(':checked')) {
                $wrapperDeprecatedSetting.addClass('is-set');
                $deprecatedSettingsLabel.text(gettext('Hide Deprecated Settings'));
                editor.render_deprecated = true;
            } else {
                $wrapperDeprecatedSetting.removeClass('is-set');
                $deprecatedSettingsLabel.text(gettext('Show Deprecated Settings'));
                editor.render_deprecated = false;
            }

            editor.render();
        });
    };
});
