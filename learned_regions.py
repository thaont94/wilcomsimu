"""CPU-only inference for the experimental satin/tatami segmentation forest.

The JSON forest is trained offline; inference needs no sklearn or pickle loading.
It predicts stitch families, not needle coordinates, sequencing or underlay.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy import ndimage

FEATURE_NAMES = ["radius_mm", "nearby_radius_mm", "occupancy_0.4mm", "occupancy_1mm",
                 "occupancy_2mm", "occupancy_4mm", "anisotropy_1mm", "anisotropy_2mm"]
MODEL_PATH = Path(__file__).with_name("models") / "region-guide.json"


def geometry_features(mask, resolution):
    mask = np.pad(np.asarray(mask, dtype=bool), 2)
    distance = ndimage.distance_transform_edt(mask) * resolution
    features = [distance, ndimage.maximum_filter(distance, size=11)]
    image = mask.astype(np.float32)
    for size in (.4, 1, 2, 4):
        features.append(ndimage.gaussian_filter(image, size/resolution))
    gx, gy = np.gradient(ndimage.gaussian_filter(image, .3/resolution))
    for size in (1, 2):
        xx = ndimage.gaussian_filter(gx*gx, size/resolution)
        yy = ndimage.gaussian_filter(gy*gy, size/resolution)
        xy = ndimage.gaussian_filter(gx*gy, size/resolution)
        features.append(np.sqrt((xx-yy)**2 + 4*xy**2)/(xx+yy+1e-10))
    return np.stack(features, axis=-1)[2:-2,2:-2].astype(np.float32)


@lru_cache(maxsize=1)
def load_model():
    model = json.loads(MODEL_PATH.read_text())
    if model.get("format") != "thread-region-forest-v1" or model.get("features") != FEATURE_NAMES:
        raise ValueError("Unsupported region model")
    return model


def predict_probability(features, model):
    """Return probability of tatami. Features are physical, orientation invariant."""
    features = np.asarray(features, dtype=np.float32)
    output = np.zeros(len(features), dtype=np.float64)
    for tree in model["trees"]:
        left = np.asarray(tree["left"])
        right = np.asarray(tree["right"])
        feature = np.asarray(tree["feature"])
        threshold = np.asarray(tree["threshold"])
        probability = np.asarray(tree["probability"])
        nodes = np.zeros(len(features), dtype=np.int32)
        for _ in range(model["max_depth"] + 2):
            active = np.flatnonzero(left[nodes] != -1)
            if not len(active):
                break
            n = nodes[active]
            nodes[active] = np.where(features[active, feature[n]] <= threshold[n], left[n], right[n])
        else:
            raise ValueError("Region model tree exceeds expected depth")
        output += probability[nodes]
    return (output / len(model["trees"])).astype(np.float32)


def split_regions(mask, resolution, model=None):
    model = load_model() if model is None else model
    features = geometry_features(mask, resolution)
    probability = np.zeros(mask.shape, dtype=np.float32)
    probability[mask] = predict_probability(features[mask], model)
    # Normalize smoothing by foreground weight so the background cannot erode
    # predicted tatami merely by pulling probability toward zero at an edge.
    weight = ndimage.gaussian_filter(mask.astype(np.float32), .3/resolution)
    probability = ndimage.gaussian_filter(probability, .3/resolution) / np.maximum(weight, 1e-6)
    tatami = mask & (probability >= .5)
    # Remove small tatami fragments, without removing any source foreground.
    components, _ = ndimage.label(tatami)
    areas = np.bincount(components.ravel()) * resolution**2
    tatami &= areas[components] >= .4
    return [("satin", mask & ~tatami), ("tatami", tatami)]
