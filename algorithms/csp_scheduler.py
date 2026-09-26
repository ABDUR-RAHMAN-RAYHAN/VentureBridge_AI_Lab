"""
Constraint Satisfaction Problem (CSP) solver for milestone scheduling.

PROBLEM: A founder needs to split a total funding amount into N milestone
payments. This is a genuine CSP:

  Variables:    m_1, m_2, ..., m_N  (the dollar amount of each milestone)
  Domains:      each m_i is an integer number of dollars in
                [min_amount, max_amount], where min/max are derived from
                min_fraction/max_fraction of the total (e.g. no single
                milestone should be under 10% or over 50% of the raise)
  Constraints:  (1) sum(m_1..m_N) == total_amount   [a global constraint]
                (2) min_amount <= m_i <= max_amount  [unary constraints]

APPROACH: Backtracking search with forward checking. Before assigning a
value to m_i, we compute the *feasible interval* for m_i given what's left
to allocate and how many variables remain — this is constraint propagation:
it prunes the domain of m_i down to only values that could still lead to a
complete, consistent solution, rather than naively trying every value in
[min_amount, max_amount] and discovering failure later. If the interval is
empty, we backtrack immediately (no candidate could work).

Candidates within the pruned interval are shuffled so repeated calls can
surface different valid schedules rather than one deterministic split.
"""
import random


def _feasible_interval(remaining_amount, remaining_vars, min_amount, max_amount):
    """
    Forward-checking step: given how much money is left to allocate and how
    many milestone variables remain (including the one we're about to
    assign), compute the interval of values the NEXT variable could take
    such that the rest could still be completed within [min_amount, max_amount]
    each.
    """
    lower = max(min_amount, remaining_amount - (remaining_vars - 1) * max_amount)
    upper = min(max_amount, remaining_amount - (remaining_vars - 1) * min_amount)
    return lower, upper


def _backtrack(remaining_amount, remaining_vars, min_amount, max_amount, step, rng):
    if remaining_vars == 0:
        return [] if remaining_amount == 0 else None

    lower, upper = _feasible_interval(remaining_amount, remaining_vars, min_amount, max_amount)
    if lower > upper:
        return None  # domain wipeout -> backtrack

    candidates = list(range(int(lower), int(upper) + 1, step))
    if not candidates:
        candidates = [int(round(lower))]
    rng.shuffle(candidates)  # randomized variable-ordering for schedule variety

    for value in candidates:
        rest = _backtrack(remaining_amount - value, remaining_vars - 1, min_amount, max_amount, step, rng)
        if rest is not None:
            return [value] + rest
    return None  # every candidate failed -> backtrack to caller


def solve_milestone_schedule(total_amount, num_milestones, min_fraction=0.10, max_fraction=0.50, seed=None):
    """
    Returns a list of `num_milestones` integer dollar amounts that sum
    exactly to `total_amount`, each within [min_fraction, max_fraction] of
    the total, or None if the constraints are unsatisfiable for this input
    (e.g. min_fraction * num_milestones > 1.0).

    Tries a few decreasing rounding granularities (step) so the result
    tends to be "nice" ($50/$100 multiples) when possible, falling back to
    exact whole-dollar amounts if a rounder solution doesn't exist.
    """
    total_amount = int(round(total_amount))
    min_amount = int(round(total_amount * min_fraction))
    max_amount = int(round(total_amount * max_fraction))

    if min_amount * num_milestones > total_amount or max_amount * num_milestones < total_amount:
        return None  # constraints are mathematically unsatisfiable

    rng = random.Random(seed)
    for step in (100, 50, 25, 10, 1):
        result = _backtrack(total_amount, num_milestones, min_amount, max_amount, step, rng)
        if result is not None:
            return result
    return None
