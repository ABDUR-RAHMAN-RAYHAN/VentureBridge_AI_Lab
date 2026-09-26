"""
K-Nearest Neighbors recommender: "startups similar to this one".

PROBLEM: Given a startup a visitor is looking at, recommend the K most
similar other (publicly visible) startups on the platform.

APPROACH: Instance-based learning (KNN). Each startup is represented as a
feature vector mixing categorical and numeric attributes:

    industry        (categorical)
    business_stage   (ordinal: Idea < MVP < Early Stage < Growth < Scaling)
    team_size        (numeric)
    founded_year     (numeric)

Because the features are mixed types, plain Euclidean distance doesn't
apply cleanly, so we use a Gower-style distance: each attribute
contributes a per-attribute distance normalized to [0, 1], and the overall
distance is the mean across attributes. This is a standard, citable
technique for KNN over mixed categorical/numeric data (Gower, 1971).

Numeric attributes (team_size, founded_year) are min-max normalized across
the current candidate pool before computing distances, since KNN is
scale-sensitive and comparing raw "team size" against raw "founded year"
without normalization would let whichever has a larger numeric range
dominate the distance.
"""
from models import STAGES

_STAGE_INDEX = {name: i for i, name in enumerate(STAGES)}


def _minmax_range(values):
    values = [v for v in values if v is not None]
    if not values:
        return 0, 1
    lo, hi = min(values), max(values)
    return lo, (hi - lo) or 1  # avoid divide-by-zero when all values are equal


def _gower_distance(a, b, team_size_range, founded_year_range):
    dists = []

    dists.append(0.0 if a["industry"] == b["industry"] else 1.0)

    stage_a = _STAGE_INDEX.get(a["stage"], 0)
    stage_b = _STAGE_INDEX.get(b["stage"], 0)
    dists.append(abs(stage_a - stage_b) / (len(STAGES) - 1))

    ts_lo, ts_rng = team_size_range
    ts_a = (a["team_size"] or 0) - ts_lo
    ts_b = (b["team_size"] or 0) - ts_lo
    dists.append(abs(ts_a - ts_b) / ts_rng)

    fy_lo, fy_rng = founded_year_range
    fy_a = (a["founded_year"] or fy_lo) - fy_lo
    fy_b = (b["founded_year"] or fy_lo) - fy_lo
    dists.append(abs(fy_a - fy_b) / fy_rng)

    return sum(dists) / len(dists)


def _to_feature_dict(startup):
    return {
        "id": startup.id,
        "industry": (startup.industry or "").strip().lower(),
        "stage": startup.stage,
        "team_size": startup.team_size,
        "founded_year": startup.founded_year,
    }


def find_similar_startups(target_startup, candidate_startups, k=3):
    """
    Returns up to `k` startups from `candidate_startups` most similar to
    `target_startup`, nearest first, using KNN with a Gower distance metric.
    `candidate_startups` should already exclude `target_startup` itself.
    """
    if not candidate_startups:
        return []

    target = _to_feature_dict(target_startup)
    pool = [_to_feature_dict(s) for s in candidate_startups]
    by_id = {s.id: s for s in candidate_startups}

    team_size_range = _minmax_range([f["team_size"] for f in pool + [target]])
    founded_year_range = _minmax_range([f["founded_year"] for f in pool + [target]])

    scored = []
    for feat in pool:
        d = _gower_distance(target, feat, team_size_range, founded_year_range)
        scored.append((d, feat["id"]))

    scored.sort(key=lambda pair: pair[0])
    top_k = scored[:k]
    return [(by_id[sid], round(1 - dist, 3)) for dist, sid in top_k]  # (startup, similarity_score)
