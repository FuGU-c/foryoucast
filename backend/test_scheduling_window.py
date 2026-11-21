import datetime as datetime_module
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import server

RealDatetime = datetime_module.datetime


class SchedulingWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.locations=patch.multiple(server,ROOT=root,DB=root/'test.db')
        self.locations.start()
        server.init()
        listener=server.profile('mila')
        listener.update(scheduled=True,onboarded=True,wake_time='08:15',timezone='Europe/Brussels')
        server.save_profile(listener)

    def tearDown(self):
        self.locations.stop()
        self.temp.cleanup()

    def clock(self,stamp):
        fixed=RealDatetime.fromisoformat(stamp)
        class FixedDatetime(RealDatetime):
            @classmethod
            def now(cls,tz=None):
                return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)
        return patch.object(server.dt,'datetime',FixedDatetime)

    def test_preparation_starts_thirty_minutes_before_listening(self):
        with self.clock('2026-11-21T06:45:00+00:00'):
            self.assertEqual(server.due_profiles(),[{'profile_id':'mila','day':'2026-11-21'}])
        with self.clock('2026-11-21T06:44:59+00:00'):
            self.assertEqual(server.due_profiles(),[])

    def test_just_after_midnight_schedule_is_found_on_previous_day(self):
        listener=server.profile('mila');listener['wake_time']='00:10';server.save_profile(listener)
        with self.clock('2026-11-20T22:45:00+00:00'):
            self.assertEqual(server.due_profiles(),[{'profile_id':'mila','day':'2026-11-21'}])
            with server.conn() as db:db.execute('INSERT INTO deliveries VALUES (?,?,?)',('mila','2026-11-21','reserved'))
            self.assertEqual(server.due_profiles(),[])
