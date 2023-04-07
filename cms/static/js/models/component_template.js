/**
 * Simple model for adding a component of a given type (for example, "video" or "html").
 */
define(['backbone', 'text!js/views/components/components.json'], function(Backbone, componentsText) {
    return Backbone.Model.extend({
        defaults: {
            type: '',
            // Each entry in the template array is an Object with the following keys:
            // display_name
            // category (may or may not match "type")
            // boilerplate_name (may be null)
            // is_common (only used for problems)
            templates: [],
            support_legend: {}
        },
        parse: function(response) {
            // Returns true only for templates that both have no boilerplate and are of
            // the overall type of the menu. This allows other component types to be added
            // and they will get sorted alphabetically rather than just at the top.
            // e.g. The ORA openassessment xblock is listed as an advanced problem.
            var isPrimaryBlankTemplate = function(template) {
                return !template.boilerplate_name && template.category === response.type;
            };

            this.type = response.type;
            this.templates = response.templates;
            this.display_name = response.display_name;
            this.support_legend = response.support_legend;

            var componentsConfig = JSON.parse(componentsText);
            var orderedComponents = [];
            for (var category in componentsConfig) {
                var components = componentsConfig[category];
                var components_list = Object.keys(components).map(function(component) {
                    return component;
                });
                orderedComponents.push(...components_list.slice(1));
            }

            var getTemplateType = function(template) {
                var type = template.category;
                if (type === 'problem' || type === 'html') {
                    var boilerplateFile = template.boilerplate_name;
                    if (boilerplateFile !== null && boilerplateFile !== undefined) {
                        var boilerplateName = boilerplateFile.split('.')[0];
                        type = boilerplateName
                    }
                }
                return type
            };

            // Sort the templates.
            if (this.templates.type != "quiz") {
                this.templates.sort(function(a, b) {
                    var type_a = getTemplateType(a);
                    var type_b = getTemplateType(b);
                    // The blank problem for the current type goes first
                    if (isPrimaryBlankTemplate(a)) {
                        return -1;
                    } else if (isPrimaryBlankTemplate(b)) {
                        return 1;
                    // Hinted problems should be shown at the end
                    } else if (a.hinted && !b.hinted) {
                        return 1;
                    } else if (!a.hinted && b.hinted) {
                        return -1;
                    } else if (orderedComponents.indexOf(type_a) > orderedComponents.indexOf(type_b)) {
                        return 1;
                    } else if (orderedComponents.indexOf(type_a) < orderedComponents.indexOf(type_b)) {
                        return -1;
                    }
                    return 0;
                });
            }
        }
    });
});
