/* globals gettext */
/* eslint-disable react/no-danger, import/prefer-default-export */
import React from 'react';
import PropTypes from 'prop-types';
import { Button, Icon, StatusAlert } from '@edx/paragon/static';
import StringUtils from 'edx-ui-toolkit/js/utils/string-utils';
import StudentAccountDeletionModal from './StudentAccountDeletionModal';

export class StudentAccountDeletion extends React.Component {
  constructor(props) {
    super(props);
    this.closeDeletionModal = this.closeDeletionModal.bind(this);
    this.loadDeletionModal = this.loadDeletionModal.bind(this);
    this.state = {
      deletionModalOpen: false,
      isActive: props.isActive,
      socialAuthConnected: this.getConnectedSocialAuth(),
    };
  }

  getConnectedSocialAuth() {
    const { socialAccountLinks } = this.props;
    if (socialAccountLinks && socialAccountLinks.providers) {
      return socialAccountLinks.providers.reduce((acc, value) => acc || value.connected, false);
    }

    return false;
  }

  closeDeletionModal() {
    this.setState({ deletionModalOpen: false });
    this.modalTrigger.focus();
  }

  loadDeletionModal() {
    this.setState({ deletionModalOpen: true });
  }

  render() {
    const { deletionModalOpen, socialAuthConnected, isActive } = this.state;

    const showError = socialAuthConnected || !isActive;

    const socialAuthError = StringUtils.interpolate(
      gettext('Before proceeding, please {htmlStart}unlink all social media accounts{htmlEnd}.'),
      {
        htmlStart: '<a href="https://support.edx.org/hc/en-us/articles/207206067" target="_blank">',
        htmlEnd: '</a>',
      },
    );

    const activationError = StringUtils.interpolate(
      gettext('Before proceeding, please {htmlStart}activate your account{htmlEnd}.'),
      {
        htmlStart: '<a href="https://support.edx.org/hc/en-us/articles/115000940568-How-do-I-activate-my-account-" target="_blank">',
        htmlEnd: '</a>',
      },
    );

    return (
      <div className="account-deletion-details">
        <p className="account-settings-header-subtitle">{ gettext('We’re sorry to see you go!') }</p>
        <p className="account-settings-header-subtitle">{ gettext('Please note: Deletion of your account and personal data is permanent and cannot be undone. You may also lose access to verified certificates. We will not be able to recover your account or the data that is deleted.') }</p>
        <p className="account-settings-header-subtitle" > {
          StringUtils.interpolate(gettext('Once your account is deleted, you cannot use it to take courses on {platformName}.'), {
            platformName: this.props.platformName,
          })
        }</p>

        <Button
          id="delete-account-btn"
          className={['btn-outline-primary']}
          disabled={showError}
          label={gettext('Delete My Account')}
          inputRef={(input) => { this.modalTrigger = input; }}
          onClick={this.loadDeletionModal}
        />
        {showError &&
          <StatusAlert
            dialog={(
              <div className="modal-alert">
                <div className="icon-wrapper">
                  <Icon id="delete-confirmation-body-error-icon" className={['fa', 'fa-exclamation-circle']} />
                </div>
                <div className="alert-content">
                  {socialAuthConnected && isActive &&
                    <p dangerouslySetInnerHTML={{ __html: socialAuthError }} />
                  }
                  {!isActive && <p dangerouslySetInnerHTML={{ __html: activationError }} /> }
                </div>
              </div>
            )}
            alertType="danger"
            dismissible={false}
            open
          />
        }
        {deletionModalOpen && <StudentAccountDeletionModal
          onClose={this.closeDeletionModal}
          platformName={this.props.platformName}
        />}
      </div>
    );
  }
}

StudentAccountDeletion.propTypes = {
  isActive: PropTypes.bool.isRequired,
  socialAccountLinks: PropTypes.shape({
    providers: PropTypes.arrayOf(PropTypes.object),
  }).isRequired,
  platformName: PropTypes.string.isRequired,
};
