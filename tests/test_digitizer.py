import base64
import io
import json
import unittest

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from pyembroidery import COMMAND_MASK, STITCH, read_dst, read_pes

from app import app
from digitizer import RESOLUTION, covered, objects_for_color


def generate(mask, overrides=None, angle=45):
    return list(objects_for_color(mask, 0, .6, 2.5, angle, 4, overrides or {}))


class GeometryTests(unittest.TestCase):
    def test_vertical_satin_crosses_narrow_stroke_instead_of_filling_along_it(self):
        mask = np.zeros((220,100), dtype=bool)
        mask[10:210, 40:52] = True
        obj, = generate(mask)
        self.assertEqual(obj['type'], 'satin')
        self.assertEqual(len(obj['paths']), 1)
        delta = np.diff(obj['paths'][0], axis=0)
        self.assertGreater(np.median(abs(delta[:,0])), 2)
        self.assertLess(np.median(abs(delta[:,1])), .4)
        self.assertTrue((np.sign(delta[1:,0]) != np.sign(delta[:-1,0])).all())

    def test_curved_satin_follows_ring_without_sewing_across_its_hole(self):
        im = Image.new('1', (160,160))
        draw = ImageDraw.Draw(im)
        draw.ellipse((15,15,145,145), fill=1)
        draw.ellipse((25,25,135,135), fill=0)
        mask = np.array(im)
        obj, = generate(mask)
        self.assertEqual(obj['type'], 'satin')
        # Circumference is about 76 mm; alternating rail samples advance ~0.3 mm.
        self.assertGreater(sum(map(len,obj['paths'])), 200)
        all_points = np.concatenate(obj['paths']) / RESOLUTION
        sectors = np.arctan2(all_points[:,1]-80, all_points[:,0]-80)
        self.assertEqual(len(set(np.floor((sectors+np.pi)/(np.pi/4)).astype(int))), 8)
        for points in obj['paths']:
            points = np.asarray(points) / RESOLUTION
            for a,b in zip(points, points[1:]):
                self.assertTrue(covered(mask,a,b))

    def test_tatami_respects_holes_angle_max_length_and_staggers_needle_points(self):
        mask = np.zeros((200,250), dtype=bool)
        mask[10:190, 10:240] = True
        mask[70:130, 95:155] = False
        obj, = generate(mask, angle=0)
        self.assertEqual(obj['type'], 'tatami')
        row_phases = {}
        for path in obj['paths']:
            for a,b in zip(path,path[1:]):
                self.assertTrue(covered(mask,np.array(a)/RESOLUTION,np.array(b)/RESOLUTION))
                self.assertLessEqual(np.linalg.norm(np.array(b)-a), 2.51)
                if abs(a[1]-b[1]) < .01 and abs(a[0]-b[0]) > 2.49:
                    row_phases.setdefault(a[1], round(a[0] % 2.5, 2))
        self.assertGreater(len(set(row_phases.values())), 2)
        angled, = generate(mask, angle=30)
        deltas = np.concatenate([np.diff(path,axis=0) for path in angled['paths'] if len(path)>1])
        angles = np.degrees(np.arctan2(deltas[:,1],deltas[:,0])) % 180
        self.assertGreater(np.count_nonzero(abs(angles-30)<1)/len(angles), .7)

    def test_same_color_disconnected_stroke_and_fill_get_different_types(self):
        mask = np.zeros((230,300), dtype=bool)
        mask[10:210,20:32] = True
        mask[20:200,120:280] = True
        self.assertEqual({o['type'] for o in generate(mask)}, {'satin','tatami'})

    def test_manual_override_and_wide_satin_guard(self):
        mask = np.zeros((200,100), dtype=bool)
        mask[10:190,30:58] = True  # 5.6 mm, wider than automatic threshold
        obj, = generate(mask)
        self.assertEqual(obj['type'], 'tatami')
        forced, = generate(mask, {obj['id']:'satin'})
        self.assertEqual(forced['type'], 'satin')
        mask[10:190,10:90] = True
        with self.assertRaisesRegex(ValueError, 'quá rộng'):
            generate(mask, {obj['id']:'satin'})


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        im = Image.new('RGB',(300,230),'white')
        draw=ImageDraw.Draw(im)
        draw.rectangle((20,10,31,210),fill='blue')
        draw.rectangle((120,20,280,200),fill='blue')
        stream=io.BytesIO();im.save(stream,format='PNG')
        self.image=stream.getvalue()

    def convert(self, **fields):
        return self.client.post('/api/digitize', files={'image':('logo.png',self.image,'image/png')},
                                data={'width_mm':60,'colors':2,**fields})

    def test_mixed_types_export_and_manual_override_roundtrip(self):
        response=self.convert()
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual(result['object_counts'],{'satin':1,'tatami':1})
        for ext,reader in [('dst',read_dst),('pes',read_pes)]:
            pattern=reader(io.BytesIO(base64.b64decode(result['exports'][ext])))
            count=sum((s[2]&COMMAND_MASK)==STITCH for s in pattern.stitches)
            self.assertGreaterEqual(count,result['stitches'])
            self.assertGreater(count,100)
        satin=next(o for o in result['objects'] if o['type']=='satin')
        response=self.convert(object_types=json.dumps({satin['id']:'tatami'}))
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['object_counts'],{'satin':0,'tatami':2})

    def test_reject_invalid_parameters_and_input(self):
        for fields in [{'object_types':'[]'},{'object_types':'{"0-1":"bad"}'},
                       {'object_types':'{"0-1":[]}'},{'angle':999},{'stitch_length':0},
                       {'satin_width':20},{'width_mm':float('nan')}]:
            self.assertEqual(self.convert(**fields).status_code,422,fields)
        response=self.client.post('/api/digitize',files={'image':('bad.png',b'bad')})
        self.assertEqual(response.status_code,400)


if __name__ == '__main__':
    unittest.main()
