from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from src.movies.models import Movie

from .models import Group, GroupMovie, UserScore

User = get_user_model()


class GroupViewsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username="testuser", password="testpass")

        cls.group = Group.objects.create(name="Test Group")
        cls.group.members.add(cls.user)

        cls.movie = Movie.objects.create(
            imdb_id="tt1234567",
            title="Test Movie",
            type="movie",
            description="Test description",
            year="2000-01-01",
            genre="Drama",
            director="Test Director",
            writers="Test Writer",
            actors="Test Actor",
            country="Test Country",
            poster="http://example.com/poster.jpg",
            awards="None",
            imdb_score="7.5",
            rottentomato_score="75%",
            metacritic_score="70",
            filmweb_score=None,
            imdb_url="https://www.imdb.com/title/tt1234567/",
            rottentomato_url="http://example.com/rottentomato",
            metacritic_url="http://example.com/metacritic",
            filmweb_url=None,
        )

        GroupMovie.objects.create(group=cls.group, movie=cls.movie, added_by=cls.user.username)

        cls.user2 = User.objects.create_user(username="testuser2", password="testpass2")
        cls.group.members.add(cls.user2)

    @classmethod
    def tearDownClass(cls):
        User.objects.filter(username="testuser").delete()
        User.objects.filter(username="testuser2").delete()
        Group.objects.filter(name="Test Group").delete()
        Movie.objects.filter(imdb_id="tt1234567").delete()
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
        response = self.client.get(reverse("group", args=[self.group.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.group.name)
        self.assertContains(response, self.movie.title)

    def test_join_group(self):
        self.client.logout()
        self.client.login(username="testuser2", password="testpass2")
        response = self.client.post(reverse("join_group"), {"code": self.group.code})
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.user2, self.group.members.all())

    def test_add_user_score(self):
        response = self.client.post(
            reverse("add_user_score"),
            {"movie_id": self.movie.imdb_id, "group_code": self.group.code, "score": 8},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(UserScore.objects.filter(user=self.user, movie=self.movie, group=self.group, score=8).exists())

    def test_group_info(self):
        response = self.client.get(reverse("group_info", args=[self.group.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.group.name)
        self.assertContains(response, self.user.username)

    def test_leave_group(self):
        response = self.client.post(reverse("leave_group"), {"group_code": self.group.code})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(self.user, self.group.members.all())

    def test_generate_invite_link(self):
        response = self.client.get(reverse("generate_invite_link", args=[self.group.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("invite_link", response.json())

    def test_join_group_by_link(self):
        invite_link_code = self.group.code
        self.client.logout()
        self.client.login(username="testuser2", password="testpass2")
        response = self.client.get(reverse("join_group_by_link", args=[invite_link_code]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.user2, self.group.members.all())
