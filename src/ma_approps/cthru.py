"""Stage 2 `cthru`: Comptroller CTHRU budget data to data/interim/cthru_accounts.csv (DESIGN §3.4,
§7.5).

Stub. Owner: workstream E (Annual budgets and checks). One aggregated query per fiscal year
against Socrata dataset kv7m-35wn, saved as a dated snapshot in data/raw/cthru/. Always aggregate
by fiscal year x account. CTHRU covers budgeted funds only: no bond-funded capital, no §2D
federal grants, and §2B ISF accounts show $0.
"""

from ma_approps.context import Context

IMPLEMENTED = False


def run(ctx: Context) -> int:
    raise NotImplementedError
