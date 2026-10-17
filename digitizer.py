"""Experimental geometric satin and staggered tatami, in millimetres.

Connected color components are editable objects, not Wilcom EMB objects.
"""
import math

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.morphology import skeletonize

RESOLUTION = 0.2  # mm per pixel, independent of stitch density


def inside(mask, point):
    x, y = np.floor(point).astype(int)
    return 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1] and bool(mask[y, x])


def covered(mask, a, b):
    """Never sew a connector across a hole or outside the color region."""
    steps = max(2, int(np.linalg.norm(np.asarray(b) - a) * 3) + 1)
    pts = np.linspace(a, b, steps)
    xs, ys = np.floor(pts).astype(int).T
    valid = (xs >= 0) & (xs < mask.shape[1]) & (ys >= 0) & (ys < mask.shape[0])
    return bool(valid.all() and mask[ys, xs].all())


def split_and_connect(mask, paths, max_connector):
    output = []
    for points in paths:
        current = []
        for point in points:
            if not inside(mask, point):
                if len(current) >= 2:
                    output.append(current)
                current = []
                continue
            if current and not covered(mask, current[-1], point):
                if len(current) >= 2:
                    output.append(current)
                current = []
            current.append(point)
        if len(current) >= 2:
            output.append(current)
    joined = []
    for points in output:
        if (joined and np.linalg.norm(np.asarray(joined[-1][-1]) - points[0]) <= max_connector
                and covered(mask, joined[-1][-1], points[0])):
            joined[-1].extend(points)
        else:
            joined.append(points)
    return joined


def skeleton_chains(skeleton):
    nodes = set(map(tuple, np.argwhere(skeleton)))
    graph = {}
    for y, x in sorted(nodes):
        adjacent = []
        for dy, dx in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
            neighbor = (y + dy, x + dx)
            if neighbor not in nodes:
                continue
            # Remove diagonal shortcuts around a connected right angle.
            if dx and dy and ((y, x + dx) in nodes or (y + dy, x) in nodes):
                continue
            adjacent.append(neighbor)
        graph[(y,x)] = adjacent
    visited = set()
    starts = sorted(graph, key=lambda node: (len(graph[node]) == 2, node))
    chains = []
    for start in starts:
        for neighbor in graph[start]:
            edge = frozenset((start, neighbor))
            if edge in visited:
                continue
            chain = [start, neighbor]
            visited.add(edge)
            prev, current = start, neighbor
            while len(graph[current]) == 2:
                nxt = next(n for n in graph[current] if n != prev)
                edge = frozenset((current, nxt))
                if edge in visited:
                    break
                visited.add(edge)
                chain.append(nxt)
                prev, current = current, nxt
            chains.append(np.array([(x + .5, y + .5) for y, x in chain]))
    return chains


def satin_paths(mask, skeleton, spacing_px):
    paths = []
    for chain in skeleton_chains(skeleton):
        distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(chain, axis=0), axis=1))]
        if distance[-1] < 1:
            continue
        positions = np.linspace(0, distance[-1], max(2, math.ceil(distance[-1] / (spacing_px / 2)) + 1))
        def point_at(t):
            return np.array([np.interp(t, distance, chain[:, i]) for i in (0, 1)])
        points = []
        for i, t in enumerate(positions):
            center = point_at(t)
            tangent = point_at(min(distance[-1], t + 3)) - point_at(max(0, t - 3))
            norm = np.linalg.norm(tangent)
            if norm == 0:
                continue
            normal = np.array([-tangent[1], tangent[0]]) / norm
            direction = normal if i % 2 else -normal
            endpoint = center
            # A single satin span must not exceed 8 mm. Broad regions use tatami.
            for length in np.arange(.25, 8 / RESOLUTION + .25, .25):
                candidate = center + direction * length
                if not inside(mask, candidate):
                    break
                # Keep needle points just inside the rail, away from pixel-edge
                # rounding that could otherwise place a point in the background.
                endpoint = center + direction * max(0, length - .15)
            points.append(endpoint.tolist())
        paths.append(points)
    return split_and_connect(mask, paths, spacing_px)


def tatami_paths(mask, spacing_px, stitch_px, angle):
    rotated = np.asarray(Image.fromarray(mask).rotate(angle, expand=True, resample=Image.Resampling.NEAREST))
    rh, rw = rotated.shape
    h, w = mask.shape
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    def original(x, y):
        x, y = x - rw / 2, y - rh / 2
        return [c*x - s*y + w/2, s*x + c*y + h/2]
    paths = []
    for row_number, y in enumerate(np.arange(.5, rh, spacing_px)):
        indices = np.flatnonzero(rotated[int(y)])
        if not len(indices):
            continue
        groups = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
        if row_number % 2:
            groups = groups[::-1]
        for group in groups:
            left, right = float(group[0]) + .1, float(group[-1]) + .9
            # Alternate the penetration grid, rather than aligning all short stitches.
            phase = (row_number % 4) * stitch_px / 4
            inner = np.arange(math.floor((left-phase)/stitch_px)*stitch_px+phase, right, stitch_px)
            xs = [left, *inner[inner > left + .2].tolist(), right]
            if row_number % 2:
                xs.reverse()
            paths.append([original(x, y) for x in xs])
    return split_and_connect(mask, paths, spacing_px * 1.5)


def objects_for_color(color_mask, label, spacing, stitch_length, angle, satin_width, overrides):
    labels, count = ndimage.label(color_mask, structure=np.ones((3,3)))
    if count > 500:
        raise ValueError("Ảnh có quá nhiều vùng rời (>500). Hãy dùng logo sạch, ít nhiễu hơn.")
    for component, bounds in enumerate(ndimage.find_objects(labels), 1):
        if bounds is None:
            continue
        local = labels[bounds] == component
        if np.count_nonzero(local) < 3:
            continue
        mask = np.pad(local, 2)
        skeleton = skeletonize(mask)
        widths = 2 * ndimage.distance_transform_edt(mask)[skeleton] * RESOLUTION
        width = float(np.percentile(widths, 95)) if len(widths) else 0
        suggested = "satin" if width <= satin_width and np.count_nonzero(skeleton) >= 2 else "tatami"
        object_id = f"{label}-{component}"
        requested = overrides.get(object_id, "auto")
        kind = suggested if requested == "auto" else requested
        notes = []
        if kind == "satin" and width > 8:
            raise ValueError(f"Vùng {object_id} quá rộng cho satin (>8 mm). Hãy chọn tatami.")
        if kind == "satin":
            paths = satin_paths(mask, skeleton, spacing / RESOLUTION)
            if not paths:
                kind = "tatami"
                notes.append("Vùng quá nhỏ để dựng cột satin; đã dùng tatami.")
        if kind == "tatami":
            paths = tatami_paths(mask, spacing / RESOLUTION, stitch_length / RESOLUTION, angle)
        if not paths:
            continue
        offset = np.array([bounds[1].start - 2, bounds[0].start - 2])
        converted = [np.round((np.asarray(p) + offset) * RESOLUTION, 3).tolist() for p in paths]
        yield {"id": object_id, "type": kind, "suggested_type": suggested,
               "selection": requested, "width_mm": round(width, 2), "paths": converted,
               "notes": notes}
