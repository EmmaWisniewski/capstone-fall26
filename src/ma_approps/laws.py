"""Stage 1 `laws`: find spending laws and download their text (DESIGN §6, §7.1).

Stub. Owner: workstream A (Law list and bond bills). Scans /api/SessionLaws/{year} full text for
appropriation language, appends new candidates to config/law_list.csv with role=tbd (never
overwriting human decisions), and caches each listed law's JSON in data/raw/sessionlaws/.
Throttle to ~1 request/second and skip unchanged files. Note: in /api/SessionLaws/{year} lists,
the Year field is the approval year; the Acts volume is the year requested.
"""

from ma_approps.context import Context

IMPLEMENTED = False


def run(ctx: Context) -> int:
    raise NotImplementedError
