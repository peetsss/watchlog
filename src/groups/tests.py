from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Group

User = get_user_model()


class GroupViewsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username="testuser", password="testpass")

        cls.group = Group.objects.create(name="Test Group")
        cls.group.members.add(cls.user)

        cls.user2 = User.objects.create_user(username="testuser2", password="testpass2")
        cls.group.members.add(cls.user2)

    @classmethod
    def tearDownClass(cls):
        User.objects.filter(username="testuser").delete()
        User.objects.filter(username="testuser2").delete()
        Group.objects.filter(name="Test Group").delete()
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        self.client.login(username="testuser", password="testpass")

    def test_create_group(self):
        response = self.client.post(reverse("create_group"), {"name": "New Group"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Group.objects.filter(name="New Group").exists())
        new_group = Group.objects.get(name="New Group")
        self.assertIn(self.user, new_group.members.all())

    def test_group_view(self):
        response = self.client.get(reverse("group", args=[self.group.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.group.name)

    def test_join_group(self):
        self.client.logout()
        self.client.login(username="testuser2", password="testpass2")
        response = self.client.post(reverse("join_group"), {"uuid": str(self.group.uuid)})
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.user2, self.group.members.all())

    def test_group_info(self):
        response = self.client.get(reverse("group_info", args=[self.group.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.group.name)
        self.assertContains(response, self.user.username)

    def test_leave_group(self):
        response = self.client.post(reverse("leave_group"), {"group_uuid": str(self.group.uuid)})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(self.user, self.group.members.all())

    def test_generate_invite_link(self):
        response = self.client.get(reverse("generate_invite_link", args=[self.group.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("invite_link", response.json())

    def test_join_group_by_link(self):
        invite_uuid = self.group.uuid
        self.client.logout()
        self.client.login(username="testuser2", password="testpass2")
        response = self.client.get(reverse("join_group_by_link", args=[invite_uuid]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.user2, self.group.members.all())
