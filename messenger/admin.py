from django.contrib import admin

from .models import Group, Teacher, Parent, Student, MethodPackage, ScheduleSlot, ChatRoom, Message, Event, FeedPost, MethodAssignment, UserProfile, Holiday, Subject, LessonTopic


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'email', 'username', 'initial_password')
    search_fields = ('last_name', 'first_name', 'email', 'user__username')
    filter_horizontal = ('groups',)
    readonly_fields = ('user', 'initial_password')


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'phone', 'email', 'username', 'initial_password')
    search_fields = ('last_name', 'first_name', 'phone', 'email', 'user__username')
    readonly_fields = ('user', 'initial_password')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'group', 'username', 'initial_password')
    search_fields = ('last_name', 'first_name', 'user__username')
    list_filter = ('group',)
    filter_horizontal = ('parents',)
    readonly_fields = ('user', 'initial_password')


@admin.register(MethodPackage)
class MethodPackageAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'material_url')
    search_fields = ('title', 'subject__name')


@admin.register(ScheduleSlot)
class ScheduleSlotAdmin(admin.ModelAdmin):
    list_display = ('group', 'lesson_date', 'weekday', 'lesson_number', 'start_time', 'method_package', 'moved_from_date')
    list_filter = ('group', 'weekday', 'lesson_date')


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'title', 'group', 'created_at')
    list_filter = ('group', 'date')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(LessonTopic)
class LessonTopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'method_package')
    list_filter = ('subject',)
    search_fields = ('name', 'subject__name', 'method_package__title')


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('group', 'room_type', 'created_at')
    list_filter = ('room_type', 'group')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('group', 'room', 'sender_name', 'sender_type', 'attachment_name', 'created_at')
    list_filter = ('group', 'room__room_type', 'sender_type')
    search_fields = ('text', 'sender_name')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'group', 'event_date', 'media_type', 'created_at')
    list_filter = ('group', 'media_type')
    search_fields = ('title', 'description')


@admin.register(FeedPost)
class FeedPostAdmin(admin.ModelAdmin):
    list_display = ('author_name', 'group', 'media_type', 'created_at')
    list_filter = ('group', 'media_type')
    search_fields = ('author_name', 'text')


@admin.register(MethodAssignment)
class MethodAssignmentAdmin(admin.ModelAdmin):
    list_display = ('method_package', 'teacher', 'deadline', 'status', 'can_edit', 'granted_by')
    list_filter = ('status', 'can_edit', 'deadline')
    search_fields = ('method_package__title', 'teacher__last_name', 'teacher__first_name', 'teacher__user__username')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
