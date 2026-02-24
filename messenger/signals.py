import secrets
import string

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from .models import Teacher, Parent, Student, UserProfile, Group, ChatRoom

User = get_user_model()


def _random_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


RUS_TO_LAT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def _to_latin(text: str) -> str:
    result = []
    for ch in text.lower():
        if 'a' <= ch <= 'z' or ch.isdigit():
            result.append(ch)
        elif ch in RUS_TO_LAT:
            result.append(RUS_TO_LAT[ch])
        elif ch == ' ' or ch == '-':
            result.append('-')
    return ''.join(result)


def _unique_username(base: str) -> str:
    base = _to_latin(base)
    base = slugify(base)[:18] or 'user'
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{base[:15]}{suffix}"
    return candidate


def _build_base_username(last_name: str, first_name: str) -> str:
    ln = _to_latin(last_name) or 'user'
    fi = (_to_latin(first_name[:1]) or '') if first_name else ''
    return f"{ln}_{fi}".strip('_')


def _ensure_profile(user, role: str):
    UserProfile.objects.get_or_create(user=user, defaults={'role': role})


def _ensure_group_chat_rooms(group: Group):
    ChatRoom.objects.get_or_create(group=group, room_type='parents')
    ChatRoom.objects.get_or_create(group=group, room_type='students')


@receiver(post_save, sender=Group)
def create_group_chat_rooms(sender, instance: Group, created, **kwargs):
    if created:
        _ensure_group_chat_rooms(instance)


@receiver(post_save, sender=Parent)
def create_parent_user(sender, instance: Parent, created, **kwargs):
    if not created or instance.user:
        return
    base = _build_base_username(instance.last_name, instance.first_name)
    username = _unique_username(base)
    password = _random_password()

    user = User.objects.create(username=username, first_name=instance.first_name, last_name=instance.last_name, email=instance.email)
    user.set_password(password)
    user.save(update_fields=['password', 'first_name', 'last_name', 'email'])

    instance.user = user
    instance.initial_password = password
    instance.save(update_fields=['user', 'initial_password'])
    _ensure_profile(user, 'parent')


@receiver(post_save, sender=Student)
def create_student_user(sender, instance: Student, created, **kwargs):
    if not created or instance.user:
        return
    base = _build_base_username(instance.last_name, instance.first_name)
    username = _unique_username(base)
    password = _random_password()

    user = User.objects.create(username=username, first_name=instance.first_name, last_name=instance.last_name)
    user.set_password(password)
    user.save(update_fields=['password', 'first_name', 'last_name'])

    instance.user = user
    instance.initial_password = password
    instance.save(update_fields=['user', 'initial_password'])
    _ensure_profile(user, 'student')


@receiver(post_save, sender=Teacher)
def create_teacher_user(sender, instance: Teacher, created, **kwargs):
    if not created or instance.user:
        return
    base = _build_base_username(instance.last_name, instance.first_name)
    username = _unique_username(base)
    password = _random_password()

    user = User.objects.create(username=username, first_name=instance.first_name, last_name=instance.last_name, email=instance.email)
    user.set_password(password)
    user.save(update_fields=['password', 'first_name', 'last_name', 'email'])

    instance.user = user
    instance.initial_password = password
    instance.save(update_fields=['user', 'initial_password'])
    _ensure_profile(user, 'teacher')
