import Backbone from 'backbone';

/**
 * Model for Course Programs.       card_image_url: {small = {'url': ''}}
 */
class ProgramModel extends Backbone.Model {
  initialize(data) {
    if (data) {
      var image_small = '';
      var image_x_small = '';
      var image_medium = '';
      if (data.card_image_url.hasOwnProperty('small')) {
          image_small = data.card_image_url.small.url;
          image_x_small = data.card_image_url['x-small'].url;
          image_medium = data.card_image_url.medium.url;
      }

      this.set({
        title: data.title,
        type: data.type,
        subtitle: data.subtitle,
        authoring_organizations: data.authoring_organizations,
        detailUrl: data.detail_url,
        aboutUrl: data.about_url,
        xsmallCardImageUrl: image_x_small,
        smallCardImageUrl: image_small,
        mediumCardImageUrl: image_medium,
        breakpoints: {
          max: {
            xsmall: '320px',
            small: '540px',
            medium: '768px',
            large: '979px',
          },
        },
      });
    }
  }
}

export default ProgramModel;
