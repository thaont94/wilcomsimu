import asyncio
import base64
import io
import json
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from PIL import Image

import app as application
from design_analysis import AnalysisLimiter, encode_image


def sample_plan():
    return {"summary": "Chữ dùng satin, mảng rộng dùng tatami.", "background_mode": "white", "colors": 1,
            "satin_spacing": .36, "tatami_spacing": .4, "tatami_length": 4, "tatami_angle": 45,
            "regions": [{"name": "Chữ", "stitch_type": "satin", "reason": "Nét hẹp; cần chia cột ở góc.",
                         "x0": .1, "y0": .1, "x1": .9, "y1": .9}],
            "cautions": ["Chưa kiểm chứng thêu trên vải."]}


class DesignAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.image = io.BytesIO()
        Image.new('RGB', (40, 40), 'blue').save(self.image, format='PNG')
        self.environment = patch.dict(os.environ, {'THREAD_OPENAI_KEY': 'test-api-key-not-real',
                                                  'THREAD_REQUIRE_AUTH': '0'})
        self.environment.start()
        self.limiter = patch.object(application, 'analysis_limiter', AnalysisLimiter())
        self.limiter.start()

    def tearDown(self):
        self.limiter.stop()
        self.environment.stop()

    def post(self, **fields):
        return TestClient(application.app).post('/api/analyze', files={'image': ('logo.png', self.image.getvalue())},
                                                data={'width_mm': 70, **fields})

    def provider(self, status=200, body=None):
        if body is None:
            body = {'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': json.dumps(sample_plan())}]}]}
        self.seen = []
        def handle(request):
            self.seen.append(request)
            return httpx.Response(status, json=body)
        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        return patch('design_analysis.httpx.AsyncClient', return_value=client)

    def test_schema_image_and_server_only_auth_are_sent_and_valid_plan_returns(self):
        with self.provider():
            response = self.post(notes='Viền satin')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['applied'])
        self.assertEqual(response.json()['plan']['colors'], 1)
        request = self.seen[0]
        self.assertEqual(str(request.url), 'https://api.openai.com/v1/responses')
        self.assertEqual(request.headers['Authorization'], 'Bearer test-api-key-not-real')
        payload = json.loads(request.content)
        self.assertFalse(payload['store'])
        self.assertTrue(payload['text']['format']['strict'])
        self.assertTrue(payload['input'][0]['content'][1]['image_url'].startswith('data:image/png;base64,'))
        self.assertNotIn('test-api-key-not-real', response.text)
        config = TestClient(application.app).get('/api/config')
        self.assertTrue(config.json()['analysis']['configured'])
        self.assertNotIn('test-api-key-not-real', config.text)

    def test_missing_key_and_bad_input_do_not_call_provider(self):
        with patch.dict(os.environ, {'THREAD_OPENAI_KEY': '', 'OPENAI_API_KEY': ''}):
            self.assertEqual(self.post().status_code, 503)
        self.assertEqual(self.post(width_mm=500).status_code, 422)
        self.assertEqual(self.post(notes='x'*2001).status_code, 422)
        self.assertEqual(TestClient(application.app).post('/api/analyze', files={'image': ('bad.png', b'bad')}).status_code, 400)
        self.assertEqual(TestClient(application.app).post('/api/analyze', files={'image': ('large.png', b'x'*10_000_001)}).status_code, 413)

    def test_provider_failures_do_not_leak_provider_body(self):
        for status, expected in [(401,503), (403,503), (429,429), (500,502)]:
            with self.provider(status, {'error': 'sensitive-provider-message'}):
                response = self.post()
            self.assertEqual(response.status_code, expected)
            self.assertNotIn('sensitive-provider-message', response.text)
        for body in [{'status': 'incomplete', 'output': []}, {'status':'completed','output': []}]:
            with self.provider(200, body):
                self.assertEqual(self.post().status_code, 502)

    def test_invalid_model_regions_are_rejected(self):
        plan=sample_plan();plan['regions'][0]['x1']=.01
        body={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(plan)}]}]}
        with self.provider(200,body):
            self.assertEqual(self.post().status_code,502)

    def test_transparent_image_preserves_visible_white_foreground(self):
        image=Image.new('RGBA',(20,20),(0,0,0,0));image.putpixel((10,10),(255,255,255,255))
        stream=io.BytesIO();image.save(stream,format='PNG')
        encoded, transparent=encode_image(stream.getvalue())
        preview=Image.open(io.BytesIO(base64.b64decode(encoded.split(',',1)[1])))
        self.assertTrue(transparent)
        self.assertEqual(preview.getpixel((10,10)),(255,255,255))
        self.assertNotEqual(preview.getpixel((0,0)),(255,255,255))

    def test_busy_and_rate_limit(self):
        limiter=AnalysisLimiter()
        self.assertTrue(limiter.acquire());self.assertFalse(limiter.acquire());limiter.release()
        for _ in range(9):
            self.assertTrue(limiter.acquire());limiter.release()
        self.assertFalse(limiter.acquire())


class WebAccessTests(unittest.TestCase):
    def test_internal_login_guards_pages_and_api_but_health_stays_public(self):
        with patch.dict(os.environ, {'THREAD_REQUIRE_AUTH':'1','THREAD_APP_PASSWORD':'test-password-at-least-12','THREAD_APP_USERNAME':'admin'}):
            with TestClient(application.app) as client:
                self.assertEqual(client.get('/health').status_code,200)
                for path in ['/', '/api/config', '/analysis-ui.js']:
                    self.assertEqual(client.get(path).status_code,401)
                    self.assertEqual(client.get(path,auth=('admin','incorrect')).status_code,401)
                    self.assertEqual(client.get(path,auth=('admin','test-password-at-least-12')).status_code,200)
                self.assertEqual(client.post('/api/analyze').status_code,401)
                self.assertEqual(client.post('/api/digitize').status_code,401)
                auth=('admin','test-password-at-least-12')
                self.assertEqual(client.post('/api/analyze',auth=auth,headers={'Origin':'https://other.example'}).status_code,403)
                self.assertEqual(client.post('/api/analyze',auth=auth,headers={'Origin':'null'}).status_code,403)
                self.assertEqual(client.post('/api/analyze',auth=auth,headers={'Origin':'http://['}).status_code,403)
                self.assertEqual(client.post('/api/analyze',auth=auth,headers={'Origin':'http://testserver'}).status_code,422)

    def test_online_start_rejects_missing_password(self):
        with patch.dict(os.environ, {'THREAD_REQUIRE_AUTH':'1','THREAD_APP_PASSWORD':''}):
            with self.assertRaisesRegex(RuntimeError,'THREAD_APP_PASSWORD'):
                with TestClient(application.app):pass


if __name__=='__main__':unittest.main()
