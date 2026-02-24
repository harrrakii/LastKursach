import json
from datetime import timedelta
from datetime import date, datetime

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView
from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from django.core.files.storage import default_storage

from .models import Group, Teacher, Parent, Student, MethodPackage, ScheduleSlot, ChatRoom, Message, Event, FeedPost, MethodAssignment, MethodAssignmentComment, UserProfile, Holiday, Subject, LessonTopic
from .serializers import (
    GroupSerializer,
    GroupDetailSerializer,
    TeacherSerializer,
    ParentSerializer,
    StudentSerializer,
    MethodPackageSerializer,
    ScheduleSlotSerializer,
    ChatRoomSerializer,
    MessageSerializer,
    EventSerializer,
    FeedPostSerializer,
    MethodAssignmentSerializer,
    MethodAssignmentCommentSerializer,
    UserProfileSerializer,
    HolidaySerializer,
    SubjectSerializer,
    LessonTopicSerializer,
)


CHAT_ROOM_TYPES = ('parents', 'students', 'management')
ROLE_CHAT_ACCESS = {
    'teacher': {'parents', 'students', 'management'},
    'manager': {'parents', 'students', 'management'},
    'parent': {'parents', 'students'},
    'student': {'students'},
    'admin': {'parents', 'students', 'management'},
    'methodist': {'parents', 'students', 'management'},
}


def _role_for_user(user):
    profile = getattr(user, 'profile', None)
    if profile and profile.role:
        return profile.role
    if user.is_staff:
        return 'admin'
    return ''


def _allowed_room_types_for_role(role: str):
    return ROLE_CHAT_ACCESS.get(role, set())


def _sender_meta(user, role: str):
    if role == 'teacher':
        teacher = getattr(user, 'teacher_profile', None)
        if teacher:
            return 'teacher', f"{teacher.last_name} {teacher.first_name}".strip()
    if role == 'manager':
        return 'manager', user.get_username() or 'Менеджер'
    if role == 'parent':
        parent = getattr(user, 'parent_profile', None)
        if parent:
            return 'parent', f"{parent.last_name} {parent.first_name}".strip()
    if role == 'student':
        student = getattr(user, 'student_profile', None)
        if student:
            return 'student', f"{student.last_name} {student.first_name}".strip()
    return 'system', user.get_username()


def _accessible_group_ids(user, role: str):
    if role in ('admin', 'methodist', 'manager') or user.is_staff:
        return set(Group.objects.values_list('id', flat=True))
    if role == 'teacher':
        teacher = getattr(user, 'teacher_profile', None)
        if not teacher:
            return set()
        return set(teacher.groups.values_list('id', flat=True))
    if role == 'student':
        student = getattr(user, 'student_profile', None)
        if not student or not student.group_id:
            return set()
        return {student.group_id}
    if role == 'parent':
        parent = getattr(user, 'parent_profile', None)
        if not parent:
            return set()
        return set(Group.objects.filter(students__parents=parent).values_list('id', flat=True).distinct())
    return set()


def _ensure_chat_rooms_for_groups(group_ids):
    if not group_ids:
        return
    existing = set(ChatRoom.objects.filter(group_id__in=group_ids).values_list('group_id', 'room_type'))
    to_create = []
    for group_id in group_ids:
        for room_type in CHAT_ROOM_TYPES:
            if (group_id, room_type) not in existing:
                to_create.append(ChatRoom(group_id=group_id, room_type=room_type))
    if to_create:
        ChatRoom.objects.bulk_create(to_create, ignore_conflicts=True)


def _can_access_group_chat(user, role: str, group_id: int, room_type: str):
    if room_type not in _allowed_room_types_for_role(role):
        return False
    return group_id in _accessible_group_ids(user, role)


def _can_access_room(user, role: str, room: ChatRoom):
    return _can_access_group_chat(user, role, room.group_id, room.room_type)


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().prefetch_related('teachers', 'students')
    serializer_class = GroupSerializer

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return GroupDetailSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        group = self.get_object()
        serializer = ScheduleSlotSerializer(group.schedule.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        group = self.get_object()
        role = _role_for_user(request.user)
        room_type = (request.query_params.get('room_type') or 'students').strip().lower()
        if room_type not in CHAT_ROOM_TYPES:
            raise ValidationError({'room_type': f"Доступны только значения: {', '.join(CHAT_ROOM_TYPES)}."})
        if not _can_access_group_chat(request.user, role, group.id, room_type):
            raise PermissionDenied('Нет доступа к этому чату.')
        _ensure_chat_rooms_for_groups({group.id})
        room = ChatRoom.objects.get(group=group, room_type=room_type)

        if request.method.lower() == 'post':
            text = str(request.data.get('text', '')).strip()
            attachment = request.FILES.get('attachment')
            if not text and not attachment:
                raise ValidationError({'detail': 'Нужно передать текст сообщения или файл.'})
            sender_type, sender_name = _sender_meta(request.user, role)
            message = Message.objects.create(
                group=group,
                room=room,
                sender_type=sender_type,
                sender_name=sender_name,
                text=text,
                attachment=attachment,
                attachment_name=attachment.name if attachment else '',
            )
            return Response(MessageSerializer(message, context={'request': request}).data, status=status.HTTP_201_CREATED)
        messages_qs = room.messages.order_by('-created_at')[:100]
        return Response(MessageSerializer(messages_qs, many=True, context={'request': request}).data)


class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer


class ParentViewSet(viewsets.ModelViewSet):
    queryset = Parent.objects.all()
    serializer_class = ParentSerializer


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related('group').prefetch_related('parents')
    serializer_class = StudentSerializer


class MethodPackageViewSet(viewsets.ModelViewSet):
    queryset = MethodPackage.objects.all()
    serializer_class = MethodPackageSerializer

    def _role(self):
        profile = getattr(self.request.user, 'profile', None)
        return getattr(profile, 'role', '') if profile else ''

    def get_queryset(self):
        qs = super().get_queryset()
        role = self._role()
        if self.request.user.is_staff or role in ('admin', 'methodist', 'manager'):
            return qs.order_by('subject__name', 'method_number', 'title')
        if role == 'teacher':
            return qs.order_by('subject__name', 'method_number', 'title')
        return qs.none()

    def _can_manage(self):
        role = self._role()
        return self.request.user.is_staff or role in ('admin', 'methodist', 'manager')

    def _teacher_can_edit(self, method_obj: MethodPackage):
        return MethodAssignment.objects.filter(
            method_package=method_obj,
            teacher__user=self.request.user,
            can_edit=True,
        ).exists()

    def perform_create(self, serializer):
        if not self._can_manage():
            raise PermissionDenied('Только методист или админ может создавать методпакеты.')
        serializer.save()

    def perform_update(self, serializer):
        if self._can_manage():
            serializer.save()
            return
        role = self._role()
        if role == 'teacher' and self._teacher_can_edit(self.get_object()):
            serializer.save()
            return
        raise PermissionDenied('Нет прав на изменение этого методпакета.')

    def perform_destroy(self, instance):
        if not self._can_manage():
            raise PermissionDenied('Только методист или админ может удалять методпакеты.')
        instance.delete()


class ScheduleSlotViewSet(viewsets.ModelViewSet):
    queryset = ScheduleSlot.objects.select_related('group', 'method_package')
    serializer_class = ScheduleSlotSerializer

    def _ordered_methods_for_subject(self, subject, start_method_number: int):
        if not subject:
            raise ValidationError({'subject_id': 'Нужно выбрать предмет для автопривязки методпакетов.'})
        methods = list(MethodPackage.objects.filter(subject=subject).order_by('method_number', 'id'))
        if not methods:
            raise ValidationError({'subject_id': 'Для выбранного предмета нет методпакетов.'})
        index = next((i for i, m in enumerate(methods) if m.method_number == start_method_number), None)
        if index is None:
            raise ValidationError({'start_method_number': 'У предмета нет методпакета с этим номером.'})
        return methods, index

    def _method_by_offset(self, methods, start_index: int, offset: int):
        if not methods:
            return None
        return methods[(start_index + offset) % len(methods)]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        group = vd['group']
        lesson_date = vd.get('lesson_date')
        if not lesson_date:
            raise ValidationError({'lesson_date': 'Нужно указать дату первого занятия.'})
        start_time = vd['start_time']
        duration = 80
        break_minutes = 10
        lesson_topic = vd.get('lesson_topic')
        subject_id = vd.get('subject_id')
        subject = Subject.objects.filter(id=subject_id).first() if subject_id else None
        if not subject and lesson_topic:
            subject = lesson_topic.subject
        start_method_number = int(vd.get('start_method_number') or 1)
        methods, start_idx = self._ordered_methods_for_subject(subject, start_method_number)
        occurrences = int(vd.get('occurrences_count') or 6)
        lesson_number = int(vd.get('lesson_number') or 1)
        base_dt = datetime.combine(date.today(), start_time)
        second_start = (base_dt + timedelta(minutes=duration + break_minutes)).time()

        created = []
        for idx in range(occurrences):
            current_date = lesson_date + timedelta(days=7 * idx)
            first_lesson_number = lesson_number + (idx * 2)
            first_method = self._method_by_offset(methods, start_idx, idx * 2)
            second_method = self._method_by_offset(methods, start_idx, (idx * 2) + 1)
            slot1 = ScheduleSlot.objects.create(
                group=group,
                lesson_date=current_date,
                lesson_topic=lesson_topic,
                weekday=current_date.weekday(),
                lesson_number=first_lesson_number,
                start_time=start_time,
                duration_minutes=duration,
                method_package=first_method,
            )
            slot2 = ScheduleSlot.objects.create(
                group=group,
                lesson_date=current_date,
                lesson_topic=lesson_topic,
                weekday=current_date.weekday(),
                lesson_number=first_lesson_number + 1,
                start_time=second_start,
                duration_minutes=duration,
                method_package=second_method,
            )
            created.extend([slot1, slot2])

        data = self.get_serializer(created, many=True).data
        return Response(data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.lesson_date:
            weekday = instance.lesson_date.weekday()
            if weekday != instance.weekday:
                instance.weekday = weekday
        instance.save()

        apply_from = self.request.data.get('apply_from_lesson_number')
        subject_id = self.request.data.get('subject_id')
        start_method_number = self.request.data.get('start_method_number')
        if apply_from and subject_id and start_method_number:
            try:
                from_lesson = int(apply_from)
                subject = Subject.objects.get(id=int(subject_id))
                start_num = int(start_method_number)
            except (ValueError, Subject.DoesNotExist):
                return
            methods, start_idx = self._ordered_methods_for_subject(subject, start_num)
            target_slots = list(
                ScheduleSlot.objects.filter(group=instance.group, lesson_number__gte=from_lesson)
                .order_by('lesson_number', 'lesson_date', 'start_time', 'id')
            )
            for offset, slot in enumerate(target_slots):
                slot.method_package = self._method_by_offset(methods, start_idx, offset)
                slot.save(update_fields=['method_package'])


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.select_related('group')
    serializer_class = HolidaySerializer

    def perform_create(self, serializer):
        holiday = serializer.save()
        self._shift_lessons(holiday)

    def _shift_lessons(self, holiday):
        day_slots = ScheduleSlot.objects.filter(lesson_date=holiday.date)
        if holiday.group_id:
            day_slots = day_slots.filter(group_id=holiday.group_id)

        for slot in day_slots:
            target_date = slot.lesson_date + timedelta(days=7)
            for _ in range(52):
                clash_holiday = Holiday.objects.filter(date=target_date).filter(group_id=slot.group_id).exists()
                clash_global = Holiday.objects.filter(date=target_date, group__isnull=True).exists()
                clash_slot = ScheduleSlot.objects.filter(
                    group_id=slot.group_id,
                    lesson_date=target_date,
                    start_time=slot.start_time,
                ).exclude(id=slot.id).exists()
                if not (clash_holiday or clash_global or clash_slot):
                    break
                target_date = target_date + timedelta(days=7)
            slot.moved_from_date = slot.lesson_date
            slot.lesson_date = target_date
            slot.weekday = target_date.weekday()
            slot.save(update_fields=['lesson_date', 'weekday', 'moved_from_date'])


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer

    def _role(self):
        profile = getattr(self.request.user, 'profile', None)
        return getattr(profile, 'role', '') if profile else ''

    def _can_manage(self):
        role = self._role()
        return self.request.user.is_staff or role in ('admin', 'methodist', 'manager')

    def perform_create(self, serializer):
        if not self._can_manage():
            raise PermissionDenied('Только методист, менеджер или админ может создавать предметы.')
        serializer.save()

    def perform_update(self, serializer):
        if not self._can_manage():
            raise PermissionDenied('Только методист, менеджер или админ может редактировать предметы.')
        serializer.save()

    def perform_destroy(self, instance):
        if not self._can_manage():
            raise PermissionDenied('Только методист, менеджер или админ может удалять предметы.')
        instance.delete()


class LessonTopicViewSet(viewsets.ModelViewSet):
    queryset = LessonTopic.objects.select_related('subject', 'method_package')
    serializer_class = LessonTopicSerializer


class ChatRoomViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ChatRoom.objects.select_related('group')
    serializer_class = ChatRoomSerializer

    def get_queryset(self):
        role = _role_for_user(self.request.user)
        allowed_room_types = _allowed_room_types_for_role(role)
        if not allowed_room_types:
            return ChatRoom.objects.none()
        group_ids = _accessible_group_ids(self.request.user, role)
        _ensure_chat_rooms_for_groups(group_ids)
        return (
            super()
            .get_queryset()
            .filter(group_id__in=group_ids, room_type__in=allowed_room_types)
            .order_by('group__name', 'room_type')
        )

    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        room = self.get_object()
        role = _role_for_user(request.user)
        if not _can_access_room(request.user, role, room):
            raise PermissionDenied('Нет доступа к этому чату.')

        if request.method.lower() == 'post':
            text = str(request.data.get('text', '')).strip()
            attachment = request.FILES.get('attachment')
            if not text and not attachment:
                raise ValidationError({'detail': 'Нужно передать текст сообщения или файл.'})
            sender_type, sender_name = _sender_meta(request.user, role)
            message = Message.objects.create(
                group=room.group,
                room=room,
                sender_type=sender_type,
                sender_name=sender_name,
                text=text,
                attachment=attachment,
                attachment_name=attachment.name if attachment else '',
            )
            return Response(MessageSerializer(message, context={'request': request}).data, status=status.HTTP_201_CREATED)

        messages_qs = room.messages.order_by('-created_at')[:100]
        return Response(MessageSerializer(messages_qs, many=True, context={'request': request}).data)


class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Message.objects.select_related('group', 'room')
    serializer_class = MessageSerializer

    def get_queryset(self):
        role = _role_for_user(self.request.user)
        group_ids = _accessible_group_ids(self.request.user, role)
        allowed_room_types = _allowed_room_types_for_role(role)
        if not group_ids or not allowed_room_types:
            return Message.objects.none()
        qs = (
            super()
            .get_queryset()
            .filter(group_id__in=group_ids, room__room_type__in=allowed_room_types)
            .order_by('-created_at')
        )
        room_id = self.request.query_params.get('room')
        if room_id:
            qs = qs.filter(room_id=room_id)
        return qs


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.select_related('group')
    serializer_class = EventSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        group_id = self.request.query_params.get('group')
        if group_id:
            qs = qs.filter(group_id=group_id)
        return qs


class FeedPostViewSet(viewsets.ModelViewSet):
    queryset = FeedPost.objects.select_related('group')
    serializer_class = FeedPostSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        group_id = self.request.query_params.get('group')
        if group_id:
            qs = qs.filter(group_id=group_id)
        return qs


class MethodAssignmentViewSet(viewsets.ModelViewSet):
    queryset = MethodAssignment.objects.select_related('method_package', 'teacher', 'teacher__user', 'granted_by')
    serializer_class = MethodAssignmentSerializer

    def _role(self):
        profile = getattr(self.request.user, 'profile', None)
        return getattr(profile, 'role', '') if profile else ''

    def _display_name(self):
        user = self.request.user
        role = self._role()
        if user.is_staff and role in ('', 'admin'):
            return user.get_username() or 'Админ'
        if role == 'teacher':
            t = getattr(user, 'teacher_profile', None)
            if t:
                return f"{t.last_name} {t.first_name}".strip()
        if role == 'methodist':
            return user.get_username() or 'Методист'
        return user.get_username() or 'Пользователь'

    def _subject_id_for_assignment(self, assignment: MethodAssignment):
        return getattr(assignment.method_package, 'subject_id', None)

    def _ordered_subject_assignments(self, teacher: Teacher, subject_id: int):
        if not subject_id:
            return MethodAssignment.objects.none()
        return (
            MethodAssignment.objects
            .filter(teacher=teacher, method_package__subject_id=subject_id)
            .select_related('method_package')
            .order_by('method_package__method_number', 'id')
        )

    def _enforce_sequential_access(self, teacher: Teacher, subject_id: int):
        """
        Для предмета у преподавателя в разработке может быть доступен только один следующий метод:
        - done/review => can_edit=False
        - первый из todo/in_progress => can_edit=True
        - остальные todo/in_progress => can_edit=False
        """
        qs = list(self._ordered_subject_assignments(teacher, subject_id))
        next_open_given = False
        for item in qs:
            if item.status == 'done':
                desired = False
            elif item.status == 'review':
                desired = False
                next_open_given = True
            elif item.status in ('todo', 'in_progress'):
                if not next_open_given:
                    desired = True
                    next_open_given = True
                else:
                    desired = False
            else:
                desired = item.can_edit
            if item.can_edit != desired:
                item.can_edit = desired
                item.save(update_fields=['can_edit'])

    def get_queryset(self):
        qs = super().get_queryset()
        role = self._role()
        if self.request.user.is_staff or role in ('admin', 'methodist'):
            return qs
        if role == 'teacher':
            return qs.filter(teacher__user=self.request.user)
        return qs.none()

    def perform_create(self, serializer):
        role = self._role()
        if not (self.request.user.is_staff or role in ('admin', 'methodist')):
            raise PermissionDenied('Только методист или админ может назначать методпакеты.')
        assignment = serializer.save(granted_by=self.request.user)
        subject_id = self._subject_id_for_assignment(assignment)
        if subject_id:
            self._enforce_sequential_access(assignment.teacher, subject_id)

    def perform_update(self, serializer):
        role = self._role()
        if self.request.user.is_staff or role in ('admin', 'methodist'):
            serializer.save()
            return
        if role == 'teacher':
            instance = self.get_object()
            if instance.teacher.user_id != self.request.user.id:
                raise PermissionDenied('Можно изменять только свои назначения.')
            allowed = {'status', 'notes'}
            incoming = set(serializer.validated_data.keys())
            if not incoming.issubset(allowed):
                raise PermissionDenied('Преподаватель может менять только статус и заметки.')
            if not instance.can_edit and ('status' in incoming or 'notes' in incoming):
                raise PermissionDenied('Этот метод пока недоступен для разработки. Сначала завершите предыдущий.')
            serializer.save()
            return
        raise PermissionDenied('Нет прав.')

    def perform_destroy(self, instance):
        role = self._role()
        if not (self.request.user.is_staff or role in ('admin', 'methodist')):
            raise PermissionDenied('Только методист или админ может удалять назначения.')
        instance.delete()

    @action(detail=False, methods=['post'])
    def bulk_assign_subject(self, request):
        role = self._role()
        if not (self.request.user.is_staff or role in ('admin', 'methodist')):
            raise PermissionDenied('Только методист или админ может назначать методпакеты.')

        teacher_id = request.data.get('teacher')
        subject_id = request.data.get('subject')
        if not teacher_id:
            raise ValidationError({'teacher': 'Нужно выбрать преподавателя.'})
        if not subject_id:
            raise ValidationError({'subject': 'Нужно выбрать предмет.'})

        try:
            teacher = Teacher.objects.get(id=int(teacher_id))
        except (Teacher.DoesNotExist, TypeError, ValueError):
            raise ValidationError({'teacher': 'Преподаватель не найден.'})
        try:
            subject = Subject.objects.get(id=int(subject_id))
        except (Subject.DoesNotExist, TypeError, ValueError):
            raise ValidationError({'subject': 'Предмет не найден.'})

        status_value = str(request.data.get('status') or 'todo')
        if status_value not in dict(MethodAssignment.STATUS_CHOICES):
            raise ValidationError({'status': 'Недопустимый статус.'})
        try:
            start_method_number = int(request.data.get('start_method_number') or 1)
        except (TypeError, ValueError):
            raise ValidationError({'start_method_number': 'Номер урока должен быть числом от 1 до 12.'})
        if start_method_number < 1 or start_method_number > 12:
            raise ValidationError({'start_method_number': 'Номер урока должен быть от 1 до 12.'})
        deadline_value = request.data.get('deadline') or None
        notes_value = str(request.data.get('notes') or '').strip()

        methods = list(MethodPackage.objects.filter(subject=subject).order_by('method_number', 'id'))
        by_number = {int(m.method_number): m for m in methods}
        placeholder_methods_created = []
        for n in range(1, 13):
            if n in by_number:
                continue
            method_obj, created_flag = MethodPackage.objects.get_or_create(
                subject=subject,
                method_number=n,
                defaults={
                    'title': f'Урок {n}',
                    'description': '',
                    'content_blocks': [],
                },
            )
            by_number[n] = method_obj
            if created_flag:
                placeholder_methods_created.append(n)
        missing_numbers = [n for n in range(1, 13) if n not in by_number]

        existing_assignments = {
            int(mid) for mid in MethodAssignment.objects.filter(
                teacher=teacher,
                method_package_id__in=[m.id for m in by_number.values()],
            ).values_list('method_package_id', flat=True)
        }

        created = []
        skipped_existing = []
        for n in range(start_method_number, 13):
            method_obj = by_number.get(n)
            if not method_obj:
                continue
            if method_obj.id in existing_assignments:
                skipped_existing.append(n)
                continue
            assignment = MethodAssignment.objects.create(
                method_package=method_obj,
                teacher=teacher,
                granted_by=request.user,
                deadline=deadline_value,
                can_edit=False,
                status=status_value,
                notes=notes_value,
            )
            created.append(assignment)
            if notes_value:
                self._add_comment(assignment, notes_value)

        self._enforce_sequential_access(teacher, subject.id)

        return Response({
            'teacher': teacher.id,
            'teacher_name': f"{teacher.last_name} {teacher.first_name}".strip(),
            'subject': subject.id,
            'subject_name': subject.name,
            'start_method_number': start_method_number,
            'created_count': len(created),
            'existing_methods_skipped': skipped_existing,
            'missing_method_numbers': missing_numbers,
            'placeholder_methods_created': placeholder_methods_created,
            'created': MethodAssignmentSerializer(created, many=True).data,
        })

    def _can_access_assignment(self, instance):
        role = self._role()
        if self.request.user.is_staff or role in ('admin', 'methodist'):
            return True
        return role == 'teacher' and instance.teacher.user_id == self.request.user.id

    def _add_comment(self, assignment, text: str):
        text = str(text or '').strip()
        if not text:
            return None
        role = self._role()
        sender_role = 'admin' if (self.request.user.is_staff and role in ('', 'admin')) else (role or 'user')
        return MethodAssignmentComment.objects.create(
            assignment=assignment,
            sender=self.request.user,
            sender_role=sender_role,
            sender_name=self._display_name(),
            text=text,
        )

    @action(detail=True, methods=['get', 'post'])
    def comments(self, request, pk=None):
        assignment = self.get_object()
        if not self._can_access_assignment(assignment):
            raise PermissionDenied('Нет доступа к комментариям этого назначения.')
        if request.method.lower() == 'post':
            text = str(request.data.get('text', '')).strip()
            if not text:
                raise ValidationError({'text': 'Комментарий не может быть пустым.'})
            comment = self._add_comment(assignment, text)
            return Response(MethodAssignmentCommentSerializer(comment).data, status=status.HTTP_201_CREATED)
        qs = assignment.comments.select_related('sender').order_by('-created_at')[:200]
        return Response(MethodAssignmentCommentSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        assignment = self.get_object()
        role = self._role()
        if not (role == 'teacher' and assignment.teacher.user_id == self.request.user.id):
            raise PermissionDenied('Только назначенный преподаватель может отправить метод на проверку.')
        if not assignment.can_edit:
            raise PermissionDenied('Этот метод пока недоступен для сдачи. Сначала завершите предыдущий.')
        assignment.status = 'review'
        assignment.can_edit = False
        assignment.save(update_fields=['status', 'can_edit'])
        self._add_comment(assignment, request.data.get('comment') or request.data.get('text') or 'Отправлено на проверку.')
        subject_id = self._subject_id_for_assignment(assignment)
        if subject_id:
            self._enforce_sequential_access(assignment.teacher, subject_id)
        return Response(MethodAssignmentSerializer(assignment).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        role = self._role()
        if not (self.request.user.is_staff or role in ('admin', 'methodist')):
            raise PermissionDenied('Только методист или админ может подтверждать метод.')
        assignment = self.get_object()
        assignment.status = 'done'
        assignment.can_edit = False
        assignment.save(update_fields=['status', 'can_edit'])
        self._add_comment(assignment, request.data.get('comment') or request.data.get('text') or 'Методпакет подтвержден и опубликован.')
        subject_id = self._subject_id_for_assignment(assignment)
        if subject_id:
            self._enforce_sequential_access(assignment.teacher, subject_id)
        return Response(MethodAssignmentSerializer(assignment).data)

    @action(detail=True, methods=['post'])
    def rework(self, request, pk=None):
        role = self._role()
        if not (self.request.user.is_staff or role in ('admin', 'methodist')):
            raise PermissionDenied('Только методист или админ может отправить на доработку.')
        assignment = self.get_object()
        comment_text = str(request.data.get('comment') or request.data.get('text') or '').strip()
        if not comment_text:
            raise ValidationError({'comment': 'Укажите комментарий для доработки.'})
        assignment.status = 'in_progress'
        assignment.can_edit = True
        assignment.notes = comment_text
        assignment.save(update_fields=['status', 'can_edit', 'notes'])
        self._add_comment(
            assignment,
            f'Отправлено на доработку.\nКомментарий методиста: {comment_text}'
        )
        subject_id = self._subject_id_for_assignment(assignment)
        if subject_id:
            self._enforce_sequential_access(assignment.teacher, subject_id)
        return Response(MethodAssignmentSerializer(assignment).data)


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.select_related('user')
    serializer_class = UserProfileSerializer

    def _actor_role(self):
        profile = getattr(self.request.user, 'profile', None)
        return getattr(profile, 'role', '') if profile else ''

    def _can_manage_profiles(self):
        role = self._actor_role()
        return self.request.user.is_staff or role in ('admin', 'methodist')

    def _target_role_from_request(self, instance=None):
        target_role = str(self.request.data.get('role') or '').strip().lower()
        if not target_role and instance is not None:
            target_role = str(instance.role or '').strip().lower()
        if target_role not in ('methodist', 'manager'):
            raise ValidationError({'role': 'Доступны только роли: methodist, manager.'})
        return target_role

    def get_queryset(self):
        if not self._can_manage_profiles():
            return UserProfile.objects.none()
        qs = super().get_queryset()
        role_filter = self.request.query_params.get('role')
        if role_filter:
            qs = qs.filter(role=role_filter)
        return qs

    def perform_create(self, serializer):
        if not self._can_manage_profiles():
            raise PermissionDenied('Недостаточно прав.')
        serializer.save(role=self._target_role_from_request())

    def perform_update(self, serializer):
        if not self._can_manage_profiles():
            raise PermissionDenied('Недостаточно прав.')
        instance = self.get_object()
        if instance.role not in ('methodist', 'manager'):
            raise PermissionDenied('Можно редактировать только методистов и менеджеров.')
        serializer.save(role=self._target_role_from_request(instance))

    def perform_destroy(self, instance):
        if not self._can_manage_profiles():
            raise PermissionDenied('Недостаточно прав.')
        if instance.role not in ('methodist', 'manager'):
            raise PermissionDenied('Можно удалять только методистов и менеджеров.')
        user = instance.user
        instance.delete()
        if user:
            user.delete()


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            # fallback: treat staff as admin if no profile created
            data = {
                'username': request.user.username,
                'email': request.user.email,
                'role': 'admin' if request.user.is_staff else 'unknown',
                'is_staff': request.user.is_staff,
            }
            return Response(data)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)


class MediaUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'Файл не передан'}, status=status.HTTP_400_BAD_REQUEST)
        path = default_storage.save(f'uploads/{file_obj.name}', file_obj)
        return Response({'url': default_storage.url(path), 'path': path})


@ensure_csrf_cookie
def login_page(request):
    return render(request, 'login.html')


@ensure_csrf_cookie
def admin_console(request):
    return render(request, 'console.html', {
        'console_title': 'Консоль управления',
        'console_root': '/console/',
        'console_create_root': '/console/create/',
    })


@ensure_csrf_cookie
def admin_create_page(request, model):
    allowed = {'groups', 'parents', 'students', 'teachers', 'methodists', 'managers', 'subjects', 'lessons', 'methods', 'assignments', 'schedule', 'holidays', 'events', 'feed'}
    if model not in allowed:
        model = 'groups'
    return render(request, 'console_create.html', {
        'model': model,
        'console_root': '/console/',
        'console_create_root': '/console/create/',
    })


@ensure_csrf_cookie
def student_page(request):
    return render(request, 'student.html')


@ensure_csrf_cookie
def parent_page(request):
    return render(request, 'role_portal.html', {
        'portal_role': 'parent',
        'portal_title': 'Классы ребенка',
    })


@ensure_csrf_cookie
def teacher_page(request):
    return render(request, 'role_portal.html', {
        'portal_role': 'teacher',
        'portal_title': 'Мои классы',
    })


@ensure_csrf_cookie
def methodist_page(request):
    return render(request, 'methodist_portal.html', {
        'portal_title': 'Кабинет методиста',
    })


@ensure_csrf_cookie
def manager_page(request):
    return render(request, 'role_portal.html', {
        'portal_role': 'manager',
        'portal_title': 'Кабинет менеджера учебного процесса',
    })


@ensure_csrf_cookie
def manager_console_page(request):
    return render(request, 'console.html', {
        'console_title': 'Управление учебным процессом',
        'console_root': '/manager/console/',
        'console_create_root': '/manager/create/',
    })


@ensure_csrf_cookie
def manager_create_page(request, model):
    allowed = {'groups', 'parents', 'students', 'teachers', 'schedule', 'holidays', 'events', 'feed'}
    if model not in allowed:
        model = 'groups'
    return render(request, 'console_create.html', {
        'model': model,
        'console_root': '/manager/console/',
        'console_create_root': '/manager/create/',
    })


@csrf_exempt
@require_POST
def session_login(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    username = str(payload.get('username', '')).strip()
    password = str(payload.get('password', ''))
    if not username or not password:
        return JsonResponse({'detail': 'Логин и пароль обязательны.'}, status=400)

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({'detail': 'Неверный логин или пароль.'}, status=401)

    login(request, user)
    profile = getattr(user, 'profile', None)
    role = getattr(profile, 'role', 'admin' if user.is_staff else 'unknown')
    return JsonResponse({
        'ok': True,
        'username': user.username,
        'role': role,
        'is_staff': user.is_staff,
    })


@csrf_exempt
@require_POST
def session_logout(request):
    logout(request)
    return JsonResponse({'ok': True})
