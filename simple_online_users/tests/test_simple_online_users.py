import json
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, new_test_user, tagged

PASSWORD = "online-users-test"


@tagged("post_install", "-at_install")
class TestSimpleOnlineUsers(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal = cls._new_user("online_portal", "base.group_portal")
        cls.plain = cls._new_user("online_plain", "base.group_user")
        cls.boss = cls._new_user("online_boss", "base.group_user,base.group_system")

    @classmethod
    def _new_user(cls, login, groups):
        return new_test_user(cls.env, login=login, groups=groups, password=PASSWORD)

    def _visible_to(self, group):
        self.env["ir.config_parameter"].sudo().set_param(
            "online_users.visibility_group", group
        )

    def _set_presence(self, user, status, minutes=0):
        when = fields.Datetime.now() - timedelta(minutes=minutes)
        values = {"status": status, "last_poll": when, "last_presence": when}
        presence = self.env["mail.presence"].sudo().search([("user_id", "=", user.id)])
        if presence:
            presence.write(values)
            return presence
        return presence.create(dict(values, user_id=user.id))

    def _call(self, user, route):
        self.authenticate(user.login, PASSWORD)
        return self.url_open(
            f"/online_users/{route}",
            data=json.dumps({"jsonrpc": "2.0", "params": {}}),
            headers={"Content-Type": "application/json"},
        ).json()

    def _listed(self):
        result = self._call(self.boss, "get_online_users")["result"]
        return {user["login"]: user for user in result["users"]}

    def test_portal_never_reads_staff(self):
        groups = ("base.group_system", "base.group_user", "base.group_portal")
        for group in groups:
            self._visible_to(group)
            for route in ("get_online_users", "get_count"):
                self.assertIn("error", self._call(self.portal, route), (group, route))

    def test_setting_is_checked_by_the_server(self):
        self._visible_to("base.group_system")
        self.assertIn("error", self._call(self.plain, "get_online_users"))
        self._visible_to("base.group_user")
        self.assertIn("result", self._call(self.plain, "get_online_users"))

    def test_poll_keeps_away_user_away(self):
        self._visible_to("base.group_system")
        presence = self._set_presence(self.boss, "away", minutes=40)
        self._call(self.boss, "get_count")
        presence.invalidate_recordset()
        self.assertEqual(presence.status, "away")

    def test_count_is_the_length_of_the_list(self):
        self._visible_to("base.group_system")
        self._set_presence(self.plain, "online", minutes=4)
        count = self._call(self.boss, "get_count")["result"]["count"]
        self.assertEqual(count, len(self._listed()))

    def test_status_follows_discuss(self):
        self._visible_to("base.group_system")
        # Odoo writes the presence on a change only, not every minute
        self._set_presence(self.plain, "online", minutes=90)
        self.assertEqual(self._listed()[self.plain.login]["status"], "online")
        self._set_presence(self.plain, "away", minutes=40)
        self.assertEqual(self._listed()[self.plain.login]["status"], "away")
        self._set_presence(self.plain, "offline")
        self.assertNotIn(self.plain.login, self._listed())

    def test_appear_offline_is_respected(self):
        self._visible_to("base.group_system")
        self._set_presence(self.plain, "online")
        self.plain.manual_im_status = "offline"
        self.assertNotIn(self.plain.login, self._listed())

    def test_upgrade_keeps_the_setting(self):
        data = self.env["ir.model.data"].search(
            [
                ("module", "=", "simple_online_users"),
                ("name", "=", "online_users_visibility_group_param"),
            ]
        )
        self.assertTrue(data.noupdate)
