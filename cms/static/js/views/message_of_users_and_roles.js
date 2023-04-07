/*
 Code for editing users and assigning roles within a course or library team context.
 */
define(['gettext'],
    function(gettext) {
        'use strict';
        const t = gettext;
        return {
            defaults: {
                confirmation: t('Ok'),
                changeRoleError: t("There was an error changing the user's role"),
                unknown: t('Unknown')
            },
            errors: {
                addUser: t('Error adding user'),
                deleteUser: t('Error removing user')
            },
            invalidEmail: {
                title: t('A valid email address is required'),
                message: t('You must enter a valid email address in order to add a new team member'),
                primaryAction: t('Return and add email address')
            },
            alreadyMember: {
                title: t('Already a member'),
                messageTpl: t('{email} is already on the {container} team. Recheck the email address if you want to add a new member.'),
                primaryAction: t('Return to team listing')
            },
            deleteUser: {
                title: t('Are you sure?'),
                messageTpl: t('Are you sure you want to delete {email} from the team for “{container}”?'),
                primaryAction: t('Delete'),
                secondaryAction: t('Cancel')
            }
        };

    });
