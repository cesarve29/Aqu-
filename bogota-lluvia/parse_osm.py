"""Merge OSM tiles and export a compact JSON (local metres, origin = Torre Colpatria).
    python3 parse_osm.py OSM_DIR city.json
Data © OpenStreetMap contributors (ODbL)."""
import glob, json, math, sys
import xml.etree.ElementTree as ET

LAT0, LON0 = 4.6109936, -74.0702477
KX = 111320.0 * math.cos(math.radians(LAT0))
KY = 110574.0


def xy(lat, lon):
    return round((lon - LON0) * KX, 2), round((lat - LAT0) * KY, 2)


nodes, ways, rels = {}, {}, {}
for f in glob.glob(sys.argv[1] + "/tile_*.osm"):
    root = ET.parse(f).getroot()
    for n in root.iter("node"):
        nodes[n.get("id")] = (float(n.get("lat")), float(n.get("lon")))
    for w in root.iter("way"):
        ways[w.get("id")] = ([nd.get("ref") for nd in w.iter("nd")],
                             {t.get("k"): t.get("v") for t in w.iter("tag")})
    for r in root.iter("relation"):
        rels[r.get("id")] = ([(m.get("type"), m.get("ref"), m.get("role")) for m in r.iter("member")],
                             {t.get("k"): t.get("v") for t in r.iter("tag")})


def pts(refs):
    if not all(r in nodes for r in refs):
        return None
    return [xy(*nodes[r]) for r in refs]


out = {"buildings": [], "roads": [], "areas": []}
KEEP = ("building", "building:levels", "height", "min_height", "building:min_level", "name", "roof:shape",
        "building:part", "amenity", "historic", "building:colour", "building:material", "tourism")


def add_building(poly, tags, wid):
    if len(poly) < 4:
        return
    out["buildings"].append({"id": wid, "p": poly[:-1] if poly[0] == poly[-1] else poly,
                             "t": {k: v for k, v in tags.items() if k in KEEP}})


for wid, (refs, tags) in ways.items():
    p = pts(refs)
    if not p:
        continue
    if "building" in tags or "building:part" in tags:
        add_building(p, tags, wid)
    elif "highway" in tags:
        out["roads"].append({"id": wid, "p": p, "t": {k: tags[k] for k in
                             ("highway", "lanes", "name", "oneway", "busway", "bridge", "layer", "width") if k in tags}})
    elif any(k in tags for k in ("leisure", "landuse", "natural", "amenity", "place")) and refs[0] == refs[-1]:
        out["areas"].append({"id": wid, "p": p[:-1], "t": {k: tags[k] for k in
                             ("leisure", "landuse", "natural", "amenity", "name", "surface") if k in tags}})

# multipolygon buildings: use outer rings
for rid, (mem, tags) in rels.items():
    if tags.get("type") == "multipolygon" and "building" in tags:
        for typ, ref, role in mem:
            if typ == "way" and role == "outer" and ref in ways:
                p = pts(ways[ref][0])
                if p and ways[ref][0][0] == ways[ref][0][-1]:
                    add_building(p, tags, "r" + rid)

json.dump(out, open(sys.argv[2], "w"))
print({k: len(v) for k, v in out.items()}, "nodes", len(nodes))
