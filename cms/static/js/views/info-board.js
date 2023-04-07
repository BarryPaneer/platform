/**
 * XBlockAccessEditor is a view that allows the user to restrict access at the unit level on the container page.
 * This view renders the button to restrict unit access into the appropriate place in the unit page.
 */
define(['js/views/baseview', 'edx-ui-toolkit/js/utils/html-utils', 'common/js/components/utils/view_utils'],
    function(BaseView, HtmlUtils, ViewUtils) {
        'use strict';
        var InfoBoard = BaseView.extend({
            // takes XBlockInfo as a model
            initialize: function() {
                BaseView.prototype.initialize.call(this);
                this.template = this.loadTemplate('info-board');
                this.model.on('sync', this.onSync, this);
            },
            onSync: function(model) {
                if (ViewUtils.hasChangedAttributes(model, [
                    'has_changes', 'published', 'visibility_state'
                ])) {
                    this.render();
                }
            },
            getUnitStatus: function() {
                var visibilityState= this.model.get('visibility_state'),
                            hasChanges= this.model.get('has_changes'),
                            published= this.model.get('published');
                var title = gettext("Draft (Never published)");
                /*if (visibilityState === 'staff_only') {
                    title = gettext("Visible to Staff Only");
                } else {}*/

                if (visibilityState === 'live') {
                    title = gettext("Published and Live");
                } else if (published && !hasChanges) {
                    title = gettext("Published (not yet released)");
                } else if (published && hasChanges) {
                    title = gettext("Draft (Unpublished changes)");
                }
                return title;
            },

            render: function() {
                HtmlUtils.setHtml(
                    this.$el,
                    HtmlUtils.HTML(this.template({
                        visibilityState:this.model.get('visibility_state'),
                        unitStatus: this.getUnitStatus()
                    }))
                );
                return this;
            }
        });

        return InfoBoard;
    }); // end define();
