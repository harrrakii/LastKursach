from django.db import models
from django.conf import settings
from django.utils.text import slugify


class Group(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name


class Teacher(models.Model):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    groups = models.ManyToManyField(Group, related_name='teachers', blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='teacher_profile')
    initial_password = models.CharField(max_length=32, blank=True, help_text='Сгенерированный пароль (показывается один раз, попросите сменить).')

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}"

    @property
    def username(self):
        return self.user.username if self.user else None


class Parent(models.Model):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='parent_profile')
    initial_password = models.CharField(max_length=32, blank=True, help_text='Сгенерированный пароль (показывается один раз, попросите сменить).')

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}"

    @property
    def username(self):
        return self.user.username if self.user else None


class Student(models.Model):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    group = models.ForeignKey(Group, related_name='students', on_delete=models.CASCADE)
    parents = models.ManyToManyField(Parent, related_name='children', blank=True)
    notes = models.TextField(blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='student_profile')
    initial_password = models.CharField(max_length=32, blank=True, help_text='Сгенерированный пароль (показывается один раз, попросите сменить).')

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}"

    @property
    def username(self):
        return self.user.username if self.user else None


class MethodPackage(models.Model):
    subject = models.ForeignKey('Subject', related_name='method_packages', on_delete=models.SET_NULL, null=True, blank=True)
    method_number = models.PositiveSmallIntegerField(default=1, help_text='Номер методпакета в рамках предмета (1-12).')
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    material_url = models.URLField(blank=True)
    content_blocks = models.JSONField(default=list, blank=True)
    attachment = models.FileField(upload_to='method_packages/', blank=True, null=True)

    def __str__(self) -> str:
        return self.title


class ScheduleSlot(models.Model):
    WEEKDAY_CHOICES = [
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    ]

    group = models.ForeignKey(Group, related_name='schedule', on_delete=models.CASCADE)
    lesson_topic = models.ForeignKey('LessonTopic', related_name='schedule_slots', on_delete=models.SET_NULL, null=True, blank=True)
    lesson_date = models.DateField(null=True, blank=True)
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES)
    lesson_number = models.PositiveSmallIntegerField(help_text='Порядковый номер занятия')
    start_time = models.TimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=90)
    method_package = models.ForeignKey(MethodPackage, related_name='schedule_slots', on_delete=models.SET_NULL, null=True)
    moved_from_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['group', 'lesson_date', 'weekday', 'start_time', 'lesson_number']

    def __str__(self) -> str:
        if self.lesson_date:
            return f"{self.group.name} | {self.lesson_date} {self.start_time}"
        return f"{self.group.name} | {self.get_weekday_display()} #{self.lesson_number}"


class Holiday(models.Model):
    date = models.DateField(unique=True)
    title = models.CharField(max_length=180, blank=True, default='Праздничный день')
    group = models.ForeignKey(Group, related_name='holidays', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']

    def __str__(self) -> str:
        if self.group_id:
            return f"{self.date} | {self.group.name}"
        return f"{self.date} | Все группы"


class Subject(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class LessonTopic(models.Model):
    name = models.CharField(max_length=180, unique=True)
    subject = models.ForeignKey(Subject, related_name='lesson_topics', on_delete=models.CASCADE)
    method_package = models.ForeignKey(MethodPackage, related_name='lesson_topics', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class ChatRoom(models.Model):
    ROOM_TYPES = [
        ('parents', 'Родители'),
        ('students', 'Студенты'),
        ('management', 'Менеджер и преподаватель'),
    ]

    group = models.ForeignKey(Group, related_name='chat_rooms', on_delete=models.CASCADE)
    room_type = models.CharField(max_length=16, choices=ROOM_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['group', 'room_type']
        unique_together = ('group', 'room_type')

    def __str__(self) -> str:
        return f"{self.group.name}: {self.get_room_type_display()}"


class Message(models.Model):
    SENDER_TYPES = [
        ('teacher', 'Преподаватель'),
        ('manager', 'Менеджер'),
        ('parent', 'Родитель'),
        ('student', 'Ученик'),
        ('system', 'Система'),
    ]

    group = models.ForeignKey(Group, related_name='messages', on_delete=models.CASCADE)
    room = models.ForeignKey(ChatRoom, related_name='messages', on_delete=models.CASCADE, null=True, blank=True)
    sender_type = models.CharField(max_length=10, choices=SENDER_TYPES)
    sender_name = models.CharField(max_length=120)
    text = models.TextField()
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        if self.room_id and self.group_id != self.room.group_id:
            self.group_id = self.room.group_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.group.name}: {self.sender_name}"


class Event(models.Model):
    MEDIA_CHOICES = [
        ('none', 'Без медиа'),
        ('image', 'Изображение'),
        ('video', 'Видео'),
    ]

    group = models.ForeignKey(Group, related_name='events', on_delete=models.CASCADE)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    event_date = models.DateField(null=True, blank=True)
    media_type = models.CharField(max_length=10, choices=MEDIA_CHOICES, default='none')
    media_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-event_date', '-created_at']

    def __str__(self) -> str:
        return f"{self.group.name}: {self.title}"


class FeedPost(models.Model):
    MEDIA_CHOICES = [
        ('none', 'Без медиа'),
        ('image', 'Изображение'),
        ('video', 'Видео'),
    ]

    group = models.ForeignKey(Group, related_name='feed_posts', on_delete=models.CASCADE)
    author_name = models.CharField(max_length=120)
    text = models.TextField()
    media_type = models.CharField(max_length=10, choices=MEDIA_CHOICES, default='none')
    media_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.group.name}: {self.author_name}"


class MethodAssignment(models.Model):
    STATUS_CHOICES = [
        ('todo', 'К выполнению'),
        ('in_progress', 'В работе'),
        ('review', 'На проверке'),
        ('done', 'Готово'),
    ]

    method_package = models.ForeignKey(MethodPackage, related_name='assignments', on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, related_name='method_assignments', on_delete=models.CASCADE)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='granted_method_assignments', on_delete=models.SET_NULL, null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    can_edit = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('method_package', 'teacher')
        ordering = ['deadline', '-created_at']

    def __str__(self) -> str:
        return f"{self.method_package.title} -> {self.teacher}"


class MethodAssignmentComment(models.Model):
    assignment = models.ForeignKey(MethodAssignment, related_name='comments', on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='method_assignment_comments', on_delete=models.SET_NULL, null=True, blank=True)
    sender_role = models.CharField(max_length=20, blank=True)
    sender_name = models.CharField(max_length=120, blank=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"Comment #{self.id} for assignment #{self.assignment_id}"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Админ'),
        ('methodist', 'Методист'),
        ('manager', 'Менеджер учебного процесса'),
        ('parent', 'Родитель'),
        ('student', 'Ребенок'),
        ('teacher', 'Учитель'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='profile', on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.get_role_display()})"
