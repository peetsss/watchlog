from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from movies.models import Movie

from .models import Group, GroupMembership, GroupMovie, Review

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


class ModelStrTests(TestCase):
    def test_str_never_queries_db(self):
        user = User.objects.create_user(username="struser", password="pw")
        group = Group.objects.create(name="Str Group")
        group.members.add(user)
        membership = GroupMembership.objects.get(user=user, group=group)
        movie = Movie.objects.create(tmdb_id=999001, title="Str Movie")
        group_movie = GroupMovie.objects.create(group=group, movie=movie)
        review = Review.objects.create(group_movie=group_movie, user=user, score=8)
        with self.assertNumQueries(0):
            str(group)
            str(membership)
            str(group_movie)
            str(review)

    async def test_group_str_in_async_context(self):
        # Regression: under Daphne the debug toolbar stringifies template
        # context in async code; Group.__str__ queried members and raised
        # SynchronousOnlyOperation on the group page.
        user = await User.objects.acreate_user(username="asyncuser", password="pw")
        group = await Group.objects.acreate(name="Async Group")
        await group.members.aadd(user)
        str(group)  # must not raise
