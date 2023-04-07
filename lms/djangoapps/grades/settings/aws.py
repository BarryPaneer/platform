def plugin_settings(settings):
    # Queue to use for updating persistent grades
    settings.RECALCULATE_GRADES_ROUTING_KEY = "edx.lms.core.grade"

    # Queue to use for updating course progress
    settings.RECALCULATE_PROGRESS_ROUTING_KEY = "edx.lms.core.progress"

    # Queue to use for updating leaderboard
    settings.RECALCULATE_LEADERBOARD_ROUTING_KEY = "edx.lms.core.leaderboard"

    # Queue to use for updating grades due to grading policy change
    settings.POLICY_CHANGE_GRADES_ROUTING_KEY = "edx.lms.core.high_mem"
