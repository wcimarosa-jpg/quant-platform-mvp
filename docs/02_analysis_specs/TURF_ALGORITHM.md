# TURF Algorithm Specification

## Purpose

TURF (Total Unduplicated Reach and Frequency) optimizes a product/feature
portfolio by finding the combination of N items that maximizes the number
of respondents "reached" (i.e., at least one item in the bundle is acceptable).

## Inputs

| Input | Type | Description |
|-------|------|-------------|
| acceptance_matrix | DataFrame (n × m, binary) | 1 = respondent accepts item, 0 = does not. Rows = respondents, columns = items. |
| portfolio_sizes | list[int] | e.g., [1, 2, 3, 4, 5] — portfolio sizes to evaluate. |
| optimization_metric | str | "reach" only for MVP. "frequency" optimization deferred to post-MVP. |

## Algorithm

### Greedy Incremental Reach (MVP)

For each portfolio size k:

1. Start with the single item that has the highest individual reach.
2. For k > 1, greedily add the item that produces the largest incremental
   reach (i.e., reaches the most respondents not already reached by items
   already in the portfolio).
3. **Tie-breaking:** When two items produce identical incremental reach,
   select the one with higher individual reach. If still tied, break by
   alphabetical item name (deterministic for reproducible tests).
4. Record the portfolio, reach count, reach %, and average frequency.

**Complexity:** O(k × m × n) per portfolio size — fast enough for m ≤ 100
items and n ≤ 10,000 respondents.

### Exhaustive Search (deferred)

For small item sets (m ≤ 20), exhaustive enumeration of all C(m, k)
combinations is feasible. Deferred to post-MVP if greedy results need
optimality guarantees.

## Outputs

Per portfolio size:

| Output | Type | Description |
|--------|------|-------------|
| items | list[str] | Item names in the optimal portfolio. |
| reach_count | int | Number of respondents reached by at least one item. |
| reach_pct | float | reach_count / total_respondents × 100. |
| avg_frequency | float | Mean number of accepted items per reached respondent. |

## Acceptance Threshold

The binary acceptance matrix is derived from a rating question. The threshold
is configurable (e.g., "top-2-box on a 5-point scale" → codes [4, 5] = 1,
else = 0).

## Integration

TURF runs as the second step after MaxDiff count-based scoring. The MaxDiff
item ranking informs which items to include in the TURF acceptance set, but
TURF uses the separate acceptance matrix (not MaxDiff utilities directly).
