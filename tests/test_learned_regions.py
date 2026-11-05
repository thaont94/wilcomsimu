import base64
import io
import unittest
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from pyembroidery import read_dst, read_pes

from app import app
from learned_regions import load_model, split_regions


class LearnedRegionTests(unittest.TestCase):
    def test_partition_preserves_foreground_and_separates_thin_and_broad_regions(self):
        mask = np.zeros((220,300),dtype=bool)
        mask[10:200,10:20] = True
        mask[10:200,80:280] = True
        parts = dict(split_regions(mask,.2))
        np.testing.assert_array_equal(parts['satin'] | parts['tatami'],mask)
        self.assertFalse((parts['satin'] & parts['tatami']).any())
        self.assertGreater(parts['satin'][10:200,10:20].mean(),.9)
        self.assertGreater(parts['tatami'][50:160,120:240].mean(),.9)

    def test_model_metadata_records_limited_training_scope(self):
        model=load_model()
        self.assertEqual(model['metadata']['design_count'],3)
        self.assertTrue(model['metadata']['experimental'])
        self.assertFalse(model['metadata']['default_enabled'])

    def test_learned_api_exports_real_stitches_and_preserves_manual_override(self):
        image=Image.new('RGB',(150,100),'white')
        draw=ImageDraw.Draw(image)
        draw.rectangle((10,10,16,90),fill='blue')
        draw.rectangle((50,10,140,90),fill='blue')
        stream=io.BytesIO();image.save(stream,format='PNG')
        def convert(**fields):
            return TestClient(app).post('/api/digitize',files={'image':('fixture.png',stream.getvalue())},
                                       data={'width_mm':40,'colors':1,'background_mode':'white',**fields})
        legacy=convert().json()
        self.assertEqual(legacy['recognition']['mode'],'geometry')
        response=convert(digitizer_mode='learned')
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual(result['recognition']['model']['design_count'],3)
        for ext,reader in [('dst',read_dst),('pes',read_pes)]:
            self.assertGreater(len(reader(io.BytesIO(base64.b64decode(result['exports'][ext]))).stitches),100)
        satin=next(o for o in result['objects'] if o['type']=='satin')
        import json
        changed=convert(digitizer_mode='learned',object_types=json.dumps({satin['id']:'tatami'}))
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(next(o for o in changed.json()['objects'] if o['id']==satin['id'])['type'],'tatami')
        with patch('app.load_model',side_effect=FileNotFoundError):
            self.assertEqual(convert(digitizer_mode='learned').status_code,503)
        self.assertEqual(convert(digitizer_mode='invalid').status_code,422)


if __name__=='__main__':unittest.main()
