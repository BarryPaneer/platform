"""
Config file with json(dict) data for advanced settings usage
"""
import copy

from django.utils.translation import ugettext as _

studio_config_data = [
    {"name": "Deprecated", "items": ["discussion_link", "course_survey_required", "source_file", "info_sidebar_name", "course_edit_method", "certificates_show_before_end", "course_survey_name", "end_of_course_survey_url", "bypass_home", "xqa_key", "hide_progress_tab", "css_class"]},
    {"name": "Schedule Your Course", "items": ["days_early_for_beta"]},
    {"name": "Target Your Learners", "items": [{"key":"invitation_only", "componentType":"switcher"}, "max_student_enrollments_allowed"]},
    {"name": "Content", "items": [{"key":"enable_subsection_gating", "componentType":"switcher"}, {"key":"video_auto_advance", "componentType":"switcher"},
                                     {"key":"show_calculator", "componentType":"switcher"}]},
    {"name": "Graded Activities", "items": [{"key":"enable_timed_exams", "componentType":"switcher"}, {"key":"rerandomize", "componentType":"dropdown"}, "teams_configuration"]},
    {"name": "Discussions", "items": [{"key":"discussion_sort_alpha", "componentType":"switcher"}, {"key":"discussion_blackouts", "componentType":"dropdown"}]}
]

platform_config_data = [
    {"name": "Deprecated", "items": ["discussion_link", "course_survey_required", "source_file", "info_sidebar_name", "course_edit_method", "certificates_show_before_end", "course_survey_name", "end_of_course_survey_url", "bypass_home", "xqa_key", "hide_progress_tab", "css_class"]},
    {"name": "Schedule Your Course", "items": ["days_early_for_beta"]},
    {"name": "Target Your Learners", "items": [{"key":"invitation_only", "componentType":"switcher"}, "max_student_enrollments_allowed"]},
    {"name": "Content", "items": [{"key":"enable_subsection_gating", "componentType":"switcher"}, {"key":"video_auto_advance", "componentType":"switcher"},
                                     {"key":"show_calculator", "componentType":"switcher"}]},
    {"name": "Graded Activities", "items": ["max_attempts", {"key":"showanswer", "componentType":"dropdown"}, {"key":"show_reset_button", "componentType":"switcher"},
                                               {"key":"enable_timed_exams", "componentType":"switcher"}, {"key":"rerandomize", "componentType":"dropdown"},
                                               {"key":"enable_proctored_exams", "componentType":"switcher"},
                                               "allow_proctoring_opt_out", "teams_configuration"]},
    {"name": "Certificates", "items": [{"key":"certificates_display_behavior", "componentType":"dropdown"}]},
    {"name": "Discussions", "items": [{"key":"allow_anonymous", "componentType":"switcher"}, {"key":"allow_anonymous_to_peers", "componentType":"switcher"}, "discussion_blackouts",
                                         "discussion_sort_alpha"]},
    {"name": "Pages", "items": ["html_textbooks"]}
]

super_config_data = [
    {"name": "Deprecated", "items": ["discussion_link", "course_survey_required", "source_file", "info_sidebar_name", "course_edit_method", "certificates_show_before_end", "course_survey_name", "end_of_course_survey_url", "bypass_home", "xqa_key", "hide_progress_tab", "css_class"]},
    {"name": "Basic Information", "items": ["display_name"]},
    {"name": "Schedule Your Course", "items": [{"key":"advertised_start", "componentType":"date"}, {"key":"announcement", "componentType":"date"}, "days_early_for_beta"]},
    {"name": "E-commerce", "items": ["cosmetic_display_price"]},
    {"name": "Target Your Learners", "items": [{"key":"invitation_only", "componentType":"switcher"}, "max_student_enrollments_allowed",
                                                  "enrollment_domain", {"key":"mobile_available", "componentType":"switcher"}]},
    {"name": "Content", "items": [{"key":"enable_subsection_gating", "componentType":"switcher"}, {"key":"advanced_modules", "componentType":"checkboxgroup"}, "static_asset_path",
                                     {"key":"video_auto_advance", "componentType":"switcher"}, "video_upload_pipeline", "display_organization",
                                     {"key":"video_speed_optimizations", "componentType":"switcher"},
                                     {"key":"show_calculator", "componentType":"switcher"},
                                     "lti_passports", "annotation_token_secret",
                                     "annotation_storage_url"]},
    {"name": "Graded Activities", "items": ["max_attempts", {"key":"showanswer", "componentType":"dropdown"}, {"key":"show_reset_button", "componentType":"switcher"},
                                               {"key":"enable_timed_exams", "componentType":"switcher"}, {"key":"rerandomize", "componentType":"dropdown"},
                                               {"key":"enable_proctored_exams", "componentType":"switcher"},
                                               {"key":"allow_proctoring_opt_out", "componentType":"switcher"}, {"key":"due", "componentType":"date"}, "due_date_display_format",
                                               "teams_configuration", {"key":"create_zendesk_tickets", "componentType":"switcher"}, "remote_gradebook"]},
    {"name": "Certificates", "items": [{"key":"certificates_display_behavior", "componentType":"dropdown"} ]},
    {"name": "Discussions", "items": [{"key":"allow_anonymous", "componentType":"switcher"}, {"key":"allow_anonymous_to_peers", "componentType":"switcher"},
                                         {"key":"discussion_blackouts", "componentType":"dropdown"}, {"key":"discussion_sort_alpha", "componentType":"switcher"},
                                         "discussion_topics"]},
    {"name": "Pages", "items": ["html_textbooks", {"key":"anderspink_boards", "componentType":"dropdown"}]},
    {"name": "Wiki", "items": [{"key":"allow_public_wiki_access", "componentType":"switcher"}]}
]


def get_advanced_settings_data(user, course_metadata):
    """
    Use config_data according to user permission with group and order info for course metadata to generate json api
    data.
    """
    config_data = studio_config_data
    if user.is_staff and user.is_superuser:
        config_data = super_config_data
    elif user.is_staff:
        config_data = platform_config_data

    # for item in config_data:
    #     item['name'] = _(item['name'])

    # avoid mutable value used as dict key.
    settings_data = copy.deepcopy(config_data)
    #for group in settings_data:
    #    group["items"] = [{key: course_metadata.get(key)} for key in group["items"]]

    return settings_data
