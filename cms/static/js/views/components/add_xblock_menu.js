define(['jquery', 'js/views/baseview', 'edx-ui-toolkit/js/utils/html-utils'],
    function($, BaseView, HtmlUtils) {

        const {React, ReactDOM} = LearningTribes.library;

        class IntroductionComponent extends React.Component {
            constructor(props) {
                super(props);
            }

            render() {
                const {display_name, category, GroupConfig}=this.props;
                var image_url = `/static/studio/images/component-images/${category}.png`;
                if (category === 'lbmdonexblock') {
                    image_url = `/static/studio/images/component-images/${category}.gif`;
                } else if (category === 'lti') {
                    image_url = '';
                }
                return (
                    <React.Fragment>
                        <div>
                            <figure>
                                <img src={`${image_url}`} />
                            </figure>
                            <h5>{gettext(display_name)}</h5>
                            <p>{gettext(GroupConfig[category]) || 'no comments'}</p>
                        </div>
                        <div>
                            {category != 'externality' ? '' : <div className="externality-supported-resources">
                                <img src='/static/studio/images/component-images/Genially.svg' className="icon_1"/>
                                <img src='/static/studio/images/component-images/Padlet.svg' className="icon_2"/>
                                <img src='/static/studio/images/component-images/Prezi.svg' className="icon_3"/>
                                <img src='/static/studio/images/component-images/canva.svg' className="icon_4"/>
                                <img src='/static/studio/images/component-images/Typeform.svg' className="icon_5"/>
                                <img src='/static/studio/images/component-images/Vimeo.svg' className="icon_6"/>
                            </div>}
                        </div>
                    </React.Fragment>
                );
            }
        }

        return BaseView.extend({
            className: function() {
                return 'new-component-templates new-component-' + this.model.type;
            },
            events: {
                "mouseenter li button" : "activateItem",
                "mouseleave li button" : "muteItem",
            },
            initialize: function() {
                BaseView.prototype.initialize.call(this);
                var template_name = this.model.type === 'problem' ? 'add-xblock-component-menu-problem' :
                    'add-xblock-component-menu';
                var support_indicator_template = this.loadTemplate('add-xblock-component-support-level');
                var support_legend_template = this.loadTemplate('add-xblock-component-support-legend');
                this.template = this.loadTemplate(template_name);
                HtmlUtils.setHtml(
                    this.$el,
                    HtmlUtils.HTML('<div class="tab-wrapper">'+this.template({
                        display_name: this.model.display_name,
                        type: this.model.type,
                        templates: this.model.templates,
                        support_legend: this.model.support_legend,
                        support_indicator_template: support_indicator_template,
                        support_legend_template: support_legend_template,
                        HtmlUtils: HtmlUtils
                    })+'</div>')
                );
                // Make the tabs on problems into "real tabs"
                this.$('.tab-group').tabs();
            },
            activateItem: function(e) {
                this.$el.find('ul li button').removeClass('active');
                var $item = $(e.currentTarget);
                $item.addClass('active');

                var $tabWrapper = this.$el.find('.tab-wrapper'); //.find('.introduction')
                var $introduction = $tabWrapper.find('>.introduction');
                if ($introduction.length <= 0) {
                    $introduction = $tabWrapper.append('<div class="introduction"></div>').find('>.introduction');
                    setTimeout(()=>{
                        $introduction.addClass('active')
                    }, 200)
                }else {
                    ReactDOM.unmountComponentAtNode($introduction[0]);
                }
                const display_name = $item.find('.name').text();
                var category = $item.data("category");
                if (category === 'problem' || category === 'html') {
                    var boilerplateFile = $item.data("boilerplate");
                    if (boilerplateFile !== undefined) {
                        var boilerplateName = boilerplateFile.split('.')[0];
                        category = boilerplateName
                    }
                }
                ReactDOM.render(<IntroductionComponent {...{display_name, category, GroupConfig:this.options.GroupsConfig[this.model.type] }}/>, $introduction[0]);
            },
            muteItem: function(e) {}

        });
    }); // end define();
