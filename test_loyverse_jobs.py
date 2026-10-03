"""Real concurrency tests, without external services or API tokens."""
import threading
import time
import unittest
from unittest.mock import patch
import loyverse_jobs as jobs


class UploadJobTests(unittest.TestCase):
    def wait(self, value):
        for _ in range(100):
            job = jobs.status(value)
            if job['state'] not in jobs.ACTIVE_STATES:
                return job
            threading.Event().wait(.01)
        self.fail('Background job failed to terminate')

    def test_returns_while_upload_blocked_then_publishes_partial_progress(self):
        value, entered, release = {}, threading.Event(), threading.Event()
        def upload(progress):
            entered.set()
            progress(done=1, created=['A'], current='B', phase='Enviando a Loyverse')
            release.wait(2)
            return {'done':2,'created':['A','B'],'completed':[],'error':None,'uncertain':None}
        try:
            response=jobs.launch(value,'preview',2,upload)
            self.assertTrue(entered.wait(1))
            self.assertIn(response['state'], jobs.ACTIVE_STATES)
            self.assertEqual(jobs.status(value)['done'],1)
            self.assertIsNone(jobs.status({},response['id']))
            self.assertIsNone(jobs.status(value,'another-session-job'))
            with self.assertRaises(ValueError):jobs.launch(value,'different-preview',1,upload)
        finally:
            release.set()
        self.assertEqual(self.wait(value)['created'],['A','B'])

    def test_lost_response_or_duplicate_submission_does_not_write_twice(self):
        value, writes = {}, []
        def upload(progress):
            writes.append('A')
            return {'done':1,'created':['A'],'error':None,'uncertain':None}
        first=jobs.launch(value,'same-preview',1,upload)
        self.wait(value)
        second=jobs.launch(value,'same-preview',1,upload)
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(writes,['A'])

    def test_crash_keeps_confirmed_skus_and_marks_current_write_uncertain(self):
        value={}
        def upload(progress):
            progress(done=1,created=['A'],current='B',phase='Enviando a Loyverse')
            raise RuntimeError('internal-secret-detail')
        jobs.launch(value,'preview',2,upload)
        result=self.wait(value)
        self.assertEqual(result['state'],'error')
        self.assertEqual(result['created'],['A'])
        self.assertEqual(result['uncertain'],'B')
        self.assertNotIn('internal-secret-detail',result['error'])
        snapshot=jobs.status(value);snapshot['created'].append('bad')
        self.assertEqual(jobs.status(value)['created'],['A'])

    def test_failure_before_write_does_not_mark_a_write_uncertain(self):
        value={}
        def upload(progress):
            progress(current='B',phase='Verificando producto')
            raise RuntimeError('read failed')
        jobs.launch(value,'preview',1,upload)
        self.assertIsNone(self.wait(value)['uncertain'])
