"""Stage 6 `combine`: build funding_actions.csv, fund_splits.csv, running_amounts.csv (DESIGN §5,
§7.6–§7.8).

Stub. Owner: everyone (Putting it together), coordinated by E. GAA rows come from
cthru_line_items.csv; everything else from items_raw, bond_items_raw, amendments_raw and the
manual_rows escape hatch. C owns the running-amounts logic; E owns the CTHRU comparison that sets
veto_status. Use schemas.record_id_prefix / assign_record_ids.

Where GAA amounts come from when CTHRU has none (Mario, 2026-11-04):
- Fee-revenue items ("may expend not more than $X", so items_raw.retained_revenue_ceiling is set)
  use the law's printed amount: amount_source = law_text, flag retained_revenue. CTHRU files these
  under retained_revenue_estimate, which cthru_line_items.csv doesn't keep (e.g. 4000-0320,
  $225M a year; about $285M a year in all).
- §2D federal grant items (section_type = federal_grants) are not in CTHRU at all (about 570 items,
  $5.3B in the FY2024 GAA; 540, $5.5B in FY2025), so a missing CTHRU row says nothing about them.
  Use the law's printed amount: amount_source = law_text, flag federal (Q1), counts_toward_total =
  false until Q1 is decided. CTHRU can't confirm vetoes here: veto_status = unknown, flag
  veto_unverified (a veto marked inline in the law text is still only a hint, §11.4).
- Any other GAA item in a section CTHRU covers (approp_main, surtax) with no CTHRU amount was
  vetoed to $0 (veto_status = vetoed); don't fall back to the printed amount. FY2025's law text
  doesn't mark its vetoes. Apply this only after the two cases above, never to §2D.
- CTHRU fund 0015 is §2B ISF chargebacks: counts_toward_total = false, even though CTHRU gives
  them non-zero fee-revenue caps ($632–704M a year).
"""

from ma_approps.context import Context

IMPLEMENTED = False


def run(ctx: Context) -> int:
    raise NotImplementedError
