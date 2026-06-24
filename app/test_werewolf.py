from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.urls import reverse

from .models import Friendship, WerewolfInvite, WerewolfLobby, WerewolfPlayer


class WerewolfGameTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.users = [User.objects.create_user(username=f"wolf-user-{index}", password="test-pass-123") for index in range(6)]
        self.host = self.users[0]
        self.client.force_login(self.host)

    def create_lobby(self, **overrides):
        data = {
            "action": "create",
            "name": "Testdorf",
            "visibility": "public",
            "max_players": "8",
            "werewolf_count": "1",
            "include_seer": "on",
            "include_witch": "on",
            "include_guard": "on",
            "reveal_roles_on_death": "on",
        }
        data.update(overrides)
        response = self.client.post(reverse("werewolf_home"), data)
        self.assertEqual(response.status_code, 302)
        return WerewolfLobby.objects.get(owner=self.host)

    def add_players(self, lobby, users=None):
        users = users or self.users[1:5]
        start_seat = lobby.players.count()
        for offset, user in enumerate(users):
            WerewolfPlayer.objects.create(lobby=lobby, user=user, display_name=user.username, seat=start_seat + offset)

    def test_password_lobby_hashes_password_and_rejects_wrong_password(self):
        lobby = self.create_lobby(visibility="password", password="mondlicht")
        self.assertNotEqual(lobby.password_hash, "mondlicht")
        self.assertTrue(check_password("mondlicht", lobby.password_hash))

        self.client.force_login(self.users[1])
        response = self.client.post(reverse("werewolf_join", args=[lobby.code]), {"password": "falsch"})
        self.assertRedirects(response, reverse("werewolf_home"))
        self.assertFalse(lobby.players.filter(user=self.users[1]).exists())

        response = self.client.post(reverse("werewolf_join", args=[lobby.code]), {"password": "mondlicht"})
        self.assertRedirects(response, reverse("werewolf_lobby", args=[lobby.code]))
        self.assertTrue(lobby.players.filter(user=self.users[1]).exists())

    def test_home_and_lobby_templates_render(self):
        response = self.client.get(reverse("werewolf_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Werwolf")
        lobby = self.create_lobby()
        response = self.client.get(reverse("werewolf_lobby", args=[lobby.code]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, lobby.name)
        self.assertContains(response, reverse("werewolf_state_api", args=[lobby.code]))

    def test_friends_only_lobby_allows_friend_and_rejects_stranger(self):
        lobby = self.create_lobby(visibility="friends")
        Friendship.objects.create(from_user=self.host, to_user=self.users[1], status=Friendship.STATUS_ACCEPTED)

        self.client.force_login(self.users[1])
        self.client.post(reverse("werewolf_join", args=[lobby.code]))
        self.assertTrue(lobby.players.filter(user=self.users[1]).exists())

        self.client.force_login(self.users[2])
        self.client.post(reverse("werewolf_join", args=[lobby.code]))
        self.assertFalse(lobby.players.filter(user=self.users[2]).exists())

    @patch("app.views.werewolf.random.SystemRandom.shuffle", side_effect=lambda roles: None)
    def test_start_assigns_roles_and_keeps_opponents_secret(self, _shuffle):
        lobby = self.create_lobby()
        self.add_players(lobby)
        response = self.client.post(reverse("werewolf_start_api", args=[lobby.code]))
        self.assertEqual(response.status_code, 200)
        lobby.refresh_from_db()
        self.assertEqual(lobby.status, WerewolfLobby.STATUS_NIGHT)
        self.assertEqual(lobby.players.exclude(role="").count(), 5)
        self.assertEqual(lobby.players.filter(role=WerewolfPlayer.ROLE_WEREWOLF).count(), 1)

        villager = lobby.players.exclude(role=WerewolfPlayer.ROLE_WEREWOLF).first()
        self.client.force_login(villager.user)
        payload = self.client.get(reverse("werewolf_state_api", args=[lobby.code])).json()
        opponent_rows = [row for row in payload["players"] if not row["isMe"]]
        self.assertTrue(all(row["role"] == "" for row in opponent_rows))

    def test_friend_invite_bypasses_password(self):
        lobby = self.create_lobby(visibility="password", password="mondlicht")
        friend = self.users[1]
        Friendship.objects.create(from_user=self.host, to_user=friend, status=Friendship.STATUS_ACCEPTED)
        invite = WerewolfInvite.objects.create(lobby=lobby, from_user=self.host, to_user=friend)
        self.client.force_login(friend)
        response = self.client.post(reverse("werewolf_invite_response", args=[invite.id]), {"action": "accept"})
        self.assertRedirects(response, reverse("werewolf_lobby", args=[lobby.code]))
        self.assertTrue(lobby.players.filter(user=friend).exists())

    def test_day_vote_eliminates_unique_target_and_finishes_for_village(self):
        lobby = self.create_lobby(include_seer="", include_witch="", include_guard="")
        self.add_players(lobby)
        lobby.status = WerewolfLobby.STATUS_DAY
        lobby.day_number = 1
        lobby.save(update_fields=["status", "day_number"])
        players = list(lobby.players.order_by("seat"))
        wolf = players[-1]
        wolf.role = WerewolfPlayer.ROLE_WEREWOLF
        wolf.save(update_fields=["role"])
        for player in players[:-1]:
            player.role = WerewolfPlayer.ROLE_VILLAGER
            player.vote_target = wolf
            player.save(update_fields=["role", "vote_target"])
        wolf.vote_target = players[0]
        wolf.save(update_fields=["vote_target"])

        response = self.client.post(reverse("werewolf_advance_api", args=[lobby.code]))
        self.assertEqual(response.status_code, 200)
        wolf.refresh_from_db()
        lobby.refresh_from_db()
        self.assertFalse(wolf.is_alive)
        self.assertEqual(lobby.status, WerewolfLobby.STATUS_FINISHED)
        self.assertEqual(lobby.winner, "village")
