from rest_framework import serializers
import re
from django.contrib.auth import get_user_model

from .models import Group, Teacher, Parent, Student, MethodPackage, ScheduleSlot, ChatRoom, Message, Event, FeedPost, MethodAssignment, MethodAssignmentComment, UserProfile, Holiday, Subject, LessonTopic
User = get_user_model()


def _normalize_phone(phone: str) -> str:
    if not phone:
        return ''
    digits = re.sub(r'[^0-9+]', '', phone)
    if digits.startswith('+'):
        core = digits[1:]
        if not core.isdigit() or len(core) < 8:
            raise serializers.ValidationError('Неверный формат телефона')
        return '+' + core
    # если начинается с 8 или 7 — считаем российским и ставим +7
    if digits.startswith('8'):
        digits = digits[1:]
    elif digits.startswith('7'):
        digits = digits[1:]
    # если остались только цифры (10+), добавляем +7 по умолчанию
    if not digits.isdigit() or len(digits) < 10:
        raise serializers.ValidationError('Неверный формат телефона')
    return '+7' + digits


def _normalize_email(email: str) -> str:
    return email.lower() if email else ''


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name']


class MethodPackageSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    def validate(self, attrs):
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        method_number = attrs.get('method_number', getattr(self.instance, 'method_number', None))
        if not subject:
            raise serializers.ValidationError({'subject': 'Нужно выбрать предмет.'})
        if not method_number or method_number < 1 or method_number > 12:
            raise serializers.ValidationError({'method_number': 'Номер методпакета должен быть от 1 до 12.'})
        if self.instance and self.instance.subject_id == subject.id and self.instance.method_number == method_number:
            return attrs
        qs = MethodPackage.objects.filter(subject=subject, method_number=method_number)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError({'method_number': 'Для этого предмета такой номер уже занят.'})
        return attrs

    class Meta:
        model = MethodPackage
        fields = ['id', 'subject', 'subject_name', 'method_number', 'title', 'description', 'material_url', 'content_blocks', 'attachment']


class LessonTopicSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    method_package_title = serializers.CharField(source='method_package.title', read_only=True)

    class Meta:
        model = LessonTopic
        fields = ['id', 'name', 'subject', 'subject_name', 'method_package', 'method_package_title']


class ScheduleSlotSerializer(serializers.ModelSerializer):
    weekday = serializers.IntegerField(read_only=True)
    lesson_topic = LessonTopicSerializer(read_only=True)
    lesson_topic_id = serializers.PrimaryKeyRelatedField(
        source='lesson_topic',
        queryset=LessonTopic.objects.all(),
        write_only=True,
        allow_null=True,
        required=False,
    )
    method_package = MethodPackageSerializer(read_only=True)
    method_package_id = serializers.PrimaryKeyRelatedField(
        source='method_package',
        queryset=MethodPackage.objects.all(),
        write_only=True,
        allow_null=True,
        required=False,
    )

    occurrences_count = serializers.IntegerField(write_only=True, required=False, min_value=1, max_value=52, default=6)
    subject_id = serializers.IntegerField(write_only=True, required=False, min_value=1)
    start_method_number = serializers.IntegerField(write_only=True, required=False, min_value=1, max_value=12, default=1)
    apply_from_lesson_number = serializers.IntegerField(write_only=True, required=False, min_value=1)

    class Meta:
        model = ScheduleSlot
        fields = [
            'id',
            'lesson_date',
            'lesson_topic',
            'lesson_topic_id',
            'weekday',
            'lesson_number',
            'start_time',
            'duration_minutes',
            'method_package',
            'method_package_id',
            'subject_id',
            'start_method_number',
            'apply_from_lesson_number',
            'group',
            'moved_from_date',
            'occurrences_count',
        ]


class HolidaySerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model = Holiday
        fields = ['id', 'date', 'title', 'group', 'group_name', 'created_at']


class TeacherSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), many=True, required=False)
    username = serializers.CharField(source='user.username', read_only=True)
    initial_password = serializers.CharField(read_only=True)

    def validate_phone(self, value):
        return _normalize_phone(value)

    def validate_email(self, value):
        return _normalize_email(value)

    class Meta:
        model = Teacher
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'groups', 'username', 'initial_password']


class ParentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    initial_password = serializers.CharField(read_only=True)

    def validate_phone(self, value):
        return _normalize_phone(value)

    def validate_email(self, value):
        return _normalize_email(value)

    class Meta:
        model = Parent
        fields = ['id', 'first_name', 'last_name', 'phone', 'email', 'username', 'initial_password']


class StudentSerializer(serializers.ModelSerializer):
    parents = serializers.PrimaryKeyRelatedField(queryset=Parent.objects.all(), many=True, required=False)
    parents_detail = ParentSerializer(source='parents', many=True, read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    initial_password = serializers.CharField(read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id',
            'first_name',
            'last_name',
            'notes',
            'group',
            'group_name',
            'parents',
            'parents_detail',
            'username',
            'initial_password',
        ]


class GroupSerializer(serializers.ModelSerializer):
    teachers = TeacherSerializer(many=True, read_only=True)
    students = StudentSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'teachers', 'students']


class ChatRoomSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    room_label = serializers.CharField(source='get_room_type_display', read_only=True)

    class Meta:
        model = ChatRoom
        fields = ['id', 'group', 'group_name', 'room_type', 'room_label', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    room_type = serializers.CharField(source='room.room_type', read_only=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'group',
            'room',
            'room_type',
            'sender_type',
            'sender_name',
            'text',
            'attachment',
            'attachment_name',
            'attachment_url',
            'created_at',
        ]
        read_only_fields = ['group', 'room', 'room_type', 'sender_type', 'sender_name']

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.attachment.url)
        return obj.attachment.url


class EventSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model = Event
        fields = [
            'id',
            'group',
            'group_name',
            'title',
            'description',
            'event_date',
            'media_type',
            'media_url',
            'created_at',
        ]


class FeedPostSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model = FeedPost
        fields = [
            'id',
            'group',
            'group_name',
            'author_name',
            'text',
            'media_type',
            'media_url',
            'created_at',
        ]


class MethodAssignmentSerializer(serializers.ModelSerializer):
    method_title = serializers.CharField(source='method_package.title', read_only=True)
    method_number = serializers.IntegerField(source='method_package.method_number', read_only=True)
    method_subject_name = serializers.CharField(source='method_package.subject.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    teacher_username = serializers.CharField(source='teacher.user.username', read_only=True)
    granted_by_username = serializers.CharField(source='granted_by.username', read_only=True)

    def get_teacher_name(self, obj):
        return f"{obj.teacher.last_name} {obj.teacher.first_name}".strip()

    class Meta:
        model = MethodAssignment
        fields = [
            'id',
            'method_package',
            'method_title',
            'method_number',
            'method_subject_name',
            'teacher',
            'teacher_name',
            'teacher_username',
            'granted_by',
            'granted_by_username',
            'deadline',
            'can_edit',
            'status',
            'notes',
            'created_at',
        ]
        read_only_fields = ['granted_by']


class MethodAssignmentCommentSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = MethodAssignmentComment
        fields = [
            'id',
            'assignment',
            'sender',
            'sender_username',
            'sender_role',
            'sender_name',
            'text',
            'created_at',
        ]
        read_only_fields = ['assignment', 'sender', 'sender_username', 'sender_role', 'sender_name', 'created_at']


class GroupDetailSerializer(GroupSerializer):
    schedule = ScheduleSlotSerializer(many=True, read_only=True)

    class Meta(GroupSerializer.Meta):
        fields = GroupSerializer.Meta.fields + ['schedule']


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username')
    email = serializers.EmailField(source='user.email', required=False, allow_blank=True)
    is_staff = serializers.BooleanField(source='user.is_staff', read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'password', 'role', 'is_staff']

    def create(self, validated_data):
        user_data = validated_data.pop('user', {})
        password = validated_data.pop('password', None)
        username = user_data.get('username')
        email = user_data.get('email', '')
        if not username:
            raise serializers.ValidationError({'username': 'Логин обязателен.'})
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError({'username': 'Пользователь с таким логином уже существует.'})
        if not password:
            raise serializers.ValidationError({'password': 'Пароль обязателен при создании.'})
        user = User.objects.create(username=username, email=email)
        user.set_password(password)
        user.save(update_fields=['password', 'email'])
        return UserProfile.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        password = validated_data.pop('password', None)
        user = instance.user

        username = user_data.get('username')
        if username and username != user.username:
            if User.objects.filter(username=username).exclude(id=user.id).exists():
                raise serializers.ValidationError({'username': 'Пользователь с таким логином уже существует.'})
            user.username = username

        if 'email' in user_data:
            user.email = user_data.get('email', '')
        if password:
            user.set_password(password)
        user.save()

        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance
