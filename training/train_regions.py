"""Train the small region classifier from an explicit, reviewed paired manifest.

Run from repo root: python -m training.train_regions --manifest /path/manifest.json
Raw images, DSTs and annotations remain outside the repository by default.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score
import sklearn
import pyembroidery as pe

from learned_regions import FEATURE_NAMES, geometry_features, predict_probability

RESOLUTION = .2
SEED = 42


def foreground(image, kind):
    rgba = image.convert("RGBA")
    a = np.asarray(rgba).astype(np.int16)
    r,g,b,alpha = a.transpose(2,0,1)
    if kind == "blue":
        return (b-r>35) & (g-r>15) & (alpha>=128)
    if kind == "white":
        return (np.minimum(np.minimum(r,g),b)>200) & (alpha>=128)
    if kind == "cyan":
        return (g-r>50) & (b-r>50) & (alpha>=128)
    raise ValueError("Unknown reviewed foreground selection")


def prepare(entry):
    with Image.open(entry["image"]) as image:
        mask = foreground(image, entry["foreground"])
        ys,xs = np.nonzero(mask)
        box = [int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
        mask = mask[box[1]:box[3],box[0]:box[2]]
        width = round(entry["width_mm"] / RESOLUTION)
        height = round(width * mask.shape[0]/mask.shape[1])
        mask = np.asarray(Image.fromarray(mask).resize((width,height),Image.Resampling.NEAREST))
        # Labels are coarse annotations derived from user's notes and reviewed
        # image regions, NOT fill metadata supposedly recovered from DST.
        label_image = Image.new("1", image.size)
        for polygon in entry.get("tatami_polygons",[]):
            ImageDraw.Draw(label_image).polygon([tuple(p) for p in polygon],fill=1)
        positive = np.asarray(label_image.crop(tuple(box)).resize((width,height),Image.Resampling.NEAREST))
    labels = positive.astype(np.uint8)
    supervised = mask.copy()
    if entry.get("tatami_polygons"):
        # Exclude uncertain seams of coarse masks, rather than label them with
        # fabricated exact Wilcom object boundaries.
        seam_distance = ndimage.distance_transform_edt(positive) + ndimage.distance_transform_edt(~positive)
        supervised &= seam_distance*RESOLUTION >= .6
    features = geometry_features(mask, RESOLUTION)
    pattern = pe.read_dst(entry["dst"])
    stitch_points = np.asarray([(x/10,y/10) for x,y,c in pattern.stitches if c&pe.COMMAND_MASK == pe.STITCH])
    minimum,maximum = stitch_points.min(axis=0),stitch_points.max(axis=0)
    extent = maximum-minimum
    pixel = (stitch_points-minimum)/extent * np.array([width-1,height-1])
    distance = ndimage.distance_transform_edt(~mask)*RESOLUTION
    px = np.clip(np.rint(pixel[:,0]).astype(int),0,width-1)
    py = np.clip(np.rint(pixel[:,1]).astype(int),0,height-1)
    near = float(np.mean(distance[py,px] <= .8))
    if near < .8:
        raise ValueError(f"Poor source-DST alignment for {entry['name']}: {near:.3f}")
    metadata = {"name":entry["name"],"artwork_bbox_xyxy":box,"width_mm":entry["width_mm"],
                "reference_extent_mm":extent.tolist(),"reference_stitches":len(stitch_points),
                "reference_points_within_0.8mm_of_foreground_after_bbox_alignment":near,
                "image_sha256":hashlib.sha256(Path(entry["image"]).read_bytes()).hexdigest(),
                "dst_sha256":hashlib.sha256(Path(entry["dst"]).read_bytes()).hexdigest(),
                "label_counts":np.bincount(labels[supervised],minlength=2).tolist()}
    return features,labels,supervised,metadata,mask


def fit(rows):
    rng = np.random.default_rng(SEED)
    xs,ys,weights = [],[],[]
    for features,labels,valid,*_ in rows:
        x,y = features[valid],labels[valid]
        for kind in np.unique(y):
            indices = np.flatnonzero(y==kind)
            chosen = rng.choice(indices, min(len(indices),4000),replace=False)
            xs.append(x[chosen]);ys.append(y[chosen])
            # Each design/class contributes equal weight, not each pixel.
            weights.extend([1/len(chosen)]*len(chosen))
    x,y = np.concatenate(xs),np.concatenate(ys)
    forest = RandomForestClassifier(n_estimators=48,max_depth=8,min_samples_leaf=12,
                                    random_state=SEED,n_jobs=2,max_features=.8)
    forest.fit(x,y,sample_weight=weights)
    return forest,x,y


def export(forest):
    trees=[]
    class_index = list(forest.classes_).index(1) if 1 in forest.classes_ else None
    for estimator in forest.estimators_:
        t=estimator.tree_
        values=t.value[:,0,:]
        probability=np.zeros(len(values)) if class_index is None else values[:,class_index]/values.sum(axis=1)
        trees.append({"left":t.children_left.tolist(),"right":t.children_right.tolist(),
                      "feature":t.feature.tolist(),"threshold":t.threshold.tolist(),
                      "probability":probability.tolist()})
    return {"format":"thread-region-forest-v1","features":FEATURE_NAMES,"max_depth":8,"trees":trees}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--output",default="models/region-guide.json",type=Path)
    parser.add_argument("--report",default="training/report.json",type=Path)
    args=parser.parse_args()
    entries=json.loads(args.manifest.read_text())["samples"]
    for entry in entries:
        for key in ("image", "dst"):
            entry[key] = str((args.manifest.resolve().parent / entry[key]).resolve())
    if len({e["name"] for e in entries})!=len(entries):raise ValueError("Duplicate design groups")
    rows=[prepare(e) for e in entries]
    folds=[]
    for i,row in enumerate(rows):
        train=[r for j,r in enumerate(rows) if j!=i]
        forest,_,_=fit(train)
        x,y=row[0][row[2]],row[1][row[2]]
        predicted=forest.predict(x)
        folds.append({"held_out_design":entries[i]["name"],"training_designs":[e["name"] for j,e in enumerate(entries) if j!=i],
                      "training_has_both_classes":len(forest.classes_)==2,
                      "confusion_matrix_rows_true_columns_predicted_satin_tatami":confusion_matrix(y,predicted,labels=[0,1]).tolist(),
                      "macro_f1":float(f1_score(y,predicted,labels=[0,1],average="macro",zero_division=0)),
                      "satin_recall":float(np.mean(predicted[y==0]==0)) if np.any(y==0) else None,
                      "tatami_recall":float(np.mean(predicted[y==1]==1)) if np.any(y==1) else None})
    forest,x,y=fit(rows)
    model=export(forest)
    exported=predict_probability(x,model)
    expected=forest.predict_proba(x)[:,list(forest.classes_).index(1)]
    if not np.allclose(exported,expected,atol=1e-6):raise ValueError("JSON inference differs from trained forest")
    report={"seed":SEED,"sklearn_version":sklearn.__version__,"model_scope":"local satin/tatami segmentation only",
            "supervision":"User notes: GM247 and MSTEK all satin; XAY DUNG coarse hand-annotated tatami regions, ambiguous seams excluded. DST used for dimensions and alignment validation, not exact fill labels.",
            "design_count":len(entries),"samples":[r[3] for r in rows],"sampled_training_pixels":len(y),
            "resubstitution_macro_f1_not_generalization":float(f1_score(y,forest.predict(x),average="macro")),
            "leave_one_design_out":folds,
            "limitations":["Only one design contains tatami; its held-out fold cannot learn tatami. No independent tatami generalization estimate.","Pixel counts are correlated; only three independent designs.","No learning of satin rails, direction, sequencing, underlay or pull compensation.","No physical sew-out validation. Model is experimental and opt-in."],
            "export_max_probability_error":float(np.max(np.abs(exported-expected)))}
    model["metadata"]={"design_count":len(entries),"version":"three-designs-v1","experimental":True,
                       "scope":report["model_scope"],"default_enabled":False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.report.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(model,separators=(',',':')))
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
