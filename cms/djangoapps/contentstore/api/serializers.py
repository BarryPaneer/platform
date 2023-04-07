from rest_framework import serializers


class CourseSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """Serializer for Course objects providing minimal data about the course.
    """
    effort = serializers.CharField()
    end = serializers.DateTimeField()
    enrollment_start = serializers.DateTimeField()
    enrollment_end = serializers.DateTimeField()
    id = serializers.CharField()  # pylint: disable=invalid-name
    name = serializers.CharField(source='display_name_with_default_escaped')
    number = serializers.CharField(source='display_number_with_default')
    org = serializers.CharField(source='display_org_with_default')
    short_description = serializers.CharField()
    start = serializers.DateTimeField()
    start_display = serializers.CharField()
    start_type = serializers.CharField()
    pacing = serializers.CharField()
    mobile_available = serializers.BooleanField()
    hidden = serializers.SerializerMethodField()
    invitation_only = serializers.BooleanField()
    catalog_visibility = serializers.CharField()

    # 'course_id' is a deprecated field, please use 'id' instead.
    course_id = serializers.CharField(source='id', read_only=True)

    def get_hidden(self, course_overview):
        """
        Get the representation for SerializerMethodField `hidden`
        Represents whether course is hidden in LMS
        """
        catalog_visibility = course_overview.catalog_visibility
        return catalog_visibility in ['about', 'none']
