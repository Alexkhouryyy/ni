"""Knowledge graph: entities + relations stored in the shared SQLite memory DB.

Entities have kinds (person, project, place, concept, tool, file, event, org) and
arbitrary JSON properties. Relations are typed directed edges between entities.

Fuzzy entity matching: if a name embedding is close to an existing entity's
embedding (cosine ≥ 0.85) of the same kind, we merge into that entity instead of
creating a duplicate.
"""
import json
import time
from typing import Optional

import numpy as np

from agent import longterm

VALID_KINDS = {"person", "project", "place", "concept", "tool", "file", "event", "org"}
_FUZZY_THRESHOLD = 0.85


def _norm_kind(kind: str) -> str:
    k = (kind or "concept").lower().strip()
    return k if k in VALID_KINDS else "concept"


def _find_by_embedding(name: str, kind: str) -> Optional[int]:
    """Return existing entity id if name is fuzzy-close to one of the same kind."""
    vec = longterm._embed(name)
    if vec is None:
        return None
    qvec = np.frombuffer(vec, dtype=np.float32)
    with longterm._conn() as c:
        rows = c.execute(
            "SELECT id, name, embedding FROM entities WHERE kind = ?",
            (kind,),
        ).fetchall()
    best_id, best_score = None, 0.0
    for rid, _rname, blob in rows:
        if blob is None:
            continue
        ev = np.frombuffer(blob, dtype=np.float32)
        score = float(np.dot(qvec, ev))
        if score > best_score:
            best_id, best_score = rid, score
    return best_id if best_score >= _FUZZY_THRESHOLD else None


def upsert_entity(name: str, kind: str = "concept", properties: Optional[dict] = None, importance: int = 5) -> dict:
    """Create or update an entity. Returns the resulting entity row."""
    name = (name or "").strip()
    if not name:
        return {"error": "empty name"}
    kind = _norm_kind(kind)
    properties = properties or {}
    now = time.time()

    # Exact-name lookup first
    with longterm._conn() as c:
        row = c.execute(
            "SELECT id, properties_json FROM entities WHERE name = ? AND kind = ?",
            (name, kind),
        ).fetchone()

    if row is None:
        fuzzy_id = _find_by_embedding(name, kind)
        if fuzzy_id is not None:
            with longterm._conn() as c:
                row = c.execute(
                    "SELECT id, properties_json FROM entities WHERE id = ?",
                    (fuzzy_id,),
                ).fetchone()

    if row is not None:
        ent_id, props_json = row
        existing = {}
        try:
            existing = json.loads(props_json or "{}")
        except Exception:
            pass
        existing.update(properties)
        with longterm._conn() as c:
            c.execute(
                "UPDATE entities SET properties_json = ?, last_seen = ?, importance = MAX(importance, ?) WHERE id = ?",
                (json.dumps(existing), now, importance, ent_id),
            )
        return _get(ent_id)

    embedding = longterm._embed(name)
    with longterm._conn() as c:
        c.execute(
            """INSERT INTO entities (name, kind, properties_json, embedding, created_at, last_seen, importance)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, kind, json.dumps(properties), embedding, now, now, importance),
        )
        new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return _get(new_id)


def relate(from_name: str, to_name: str, kind: str, properties: Optional[dict] = None,
           from_kind: str = "concept", to_kind: str = "concept", confidence: float = 1.0) -> dict:
    """Create a typed directed edge. Both entities are upserted if missing."""
    a = upsert_entity(from_name, kind=from_kind)
    b = upsert_entity(to_name, kind=to_kind)
    if "error" in a or "error" in b:
        return {"error": "could not resolve entities"}
    with longterm._conn() as c:
        c.execute(
            """INSERT INTO relations (from_id, to_id, kind, properties_json, ts, confidence)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (a["id"], b["id"], kind, json.dumps(properties or {}), time.time(), float(confidence)),
        )
        rid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": rid, "from": a, "to": b, "kind": kind, "confidence": confidence}


def query_entity(name: str, hops: int = 1) -> dict:
    """Look up an entity by exact or fuzzy name; return entity + neighbours within N hops."""
    with longterm._conn() as c:
        row = c.execute(
            "SELECT id FROM entities WHERE LOWER(name) = LOWER(?) ORDER BY importance DESC LIMIT 1",
            (name,),
        ).fetchone()
    ent_id = row[0] if row else None
    if ent_id is None:
        # try fuzzy across all kinds
        for k in VALID_KINDS:
            fid = _find_by_embedding(name, k)
            if fid is not None:
                ent_id = fid
                break
    if ent_id is None:
        return {"error": f"no entity matching {name!r}"}

    visited = {ent_id}
    frontier = {ent_id}
    edges: list[dict] = []
    for _ in range(max(0, hops)):
        next_frontier = set()
        with longterm._conn() as c:
            rows = c.execute(
                f"SELECT id, from_id, to_id, kind, confidence FROM relations "
                f"WHERE from_id IN ({','.join('?'*len(frontier))}) OR to_id IN ({','.join('?'*len(frontier))})",
                tuple(frontier) + tuple(frontier),
            ).fetchall()
        for rid, fr, to, k, conf in rows:
            edges.append({"id": rid, "from_id": fr, "to_id": to, "kind": k, "confidence": conf})
            for n in (fr, to):
                if n not in visited:
                    next_frontier.add(n)
                    visited.add(n)
        frontier = next_frontier
        if not frontier:
            break

    nodes = [_get(nid) for nid in visited]
    return {"root": _get(ent_id), "nodes": nodes, "edges": edges}


def query_by_kind(kind: str, limit: int = 20) -> list[dict]:
    kind = _norm_kind(kind)
    with longterm._conn() as c:
        rows = c.execute(
            "SELECT id FROM entities WHERE kind = ? ORDER BY importance DESC, last_seen DESC LIMIT ?",
            (kind, limit),
        ).fetchall()
    return [_get(r[0]) for r in rows]


def subgraph(entity_names: Optional[list] = None, limit_nodes: int = 100) -> dict:
    """Return nodes + edges for visualisation. If names omitted, returns top-importance slice."""
    with longterm._conn() as c:
        if entity_names:
            placeholders = ",".join("?" * len(entity_names))
            rows = c.execute(
                f"SELECT id FROM entities WHERE LOWER(name) IN ({placeholders})",
                tuple(n.lower() for n in entity_names),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id FROM entities ORDER BY importance DESC, last_seen DESC LIMIT ?",
                (limit_nodes,),
            ).fetchall()
        ids = [r[0] for r in rows]
        if not ids:
            return {"nodes": [], "edges": []}
        ph = ",".join("?" * len(ids))
        edges = c.execute(
            f"SELECT id, from_id, to_id, kind, confidence FROM relations "
            f"WHERE from_id IN ({ph}) AND to_id IN ({ph})",
            tuple(ids) + tuple(ids),
        ).fetchall()
    return {
        "nodes": [_get(i) for i in ids],
        "edges": [{"id": e[0], "from_id": e[1], "to_id": e[2], "kind": e[3], "confidence": e[4]} for e in edges],
    }


def _get(ent_id: int) -> dict:
    with longterm._conn() as c:
        r = c.execute(
            "SELECT id, name, kind, properties_json, created_at, last_seen, importance FROM entities WHERE id = ?",
            (ent_id,),
        ).fetchone()
    if r is None:
        return {"error": f"entity {ent_id} not found"}
    try:
        props = json.loads(r[3] or "{}")
    except Exception:
        props = {}
    return {
        "id": r[0], "name": r[1], "kind": r[2], "properties": props,
        "created_at": r[4], "last_seen": r[5], "importance": r[6],
    }


def delete_entity(ent_id: int) -> str:
    with longterm._conn() as c:
        c.execute("DELETE FROM relations WHERE from_id = ? OR to_id = ?", (ent_id, ent_id))
        c.execute("DELETE FROM entities WHERE id = ?", (ent_id,))
    return f"Deleted entity #{ent_id} and its relations."
