"""Stage 6 `assemble`: build funding_actions.csv, fund_splits.csv, running_amounts.csv (DESIGN §5,
§7.6–§7.8).

Stub. Owner: everyone (Putting it together), coordinated by E. GAA rows come from
cthru_accounts.csv; everything else from items_raw, bond_items_raw, amendments_raw and the
manual_rows escape hatch. C owns the running-amounts logic; E owns the CTHRU comparison that sets
veto_status. Use schemas.record_id_prefix / assign_record_ids.
"""

from ma_approps.context import Context

IMPLEMENTED = False


def run(ctx: Context) -> int:
    raise NotImplementedError
