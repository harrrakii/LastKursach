from django.test import TestCase
from messenger.models import Group


class GroupModelTest(TestCase):
    def test_str(self):
        group = Group.objects.create(name='Группа А')
        self.assertEqual(str(group), 'Группа А')
