"""The shared core of combine (workstream A; DESIGN §5, §7.6–§7.8, §9.6, §10)."""

import random

import pytest

from ma_approps import combine, read_bonds, schemas
from ma_approps.context import Context

FUNDS = [
    {"fund_name": "General Fund", "fund_number": "0010", "is_federal": "false", "notes": ""},
    {
        "fund_name": "Intragovernmental Service Fund",
        "fund_number": "0015",
        "is_federal": "false",
        "notes": "",
    },
    {
        "fund_name": "Federal COVID-19 Response Fund",
        "fund_number": "0007",
        "is_federal": "true",
        "notes": "",
    },
]
LAWS = [
    {"law_key": "2023-28", "role": "in_scope"},
    {"law_key": "2023-77", "role": "in_scope"},
    {"law_key": "2020-227", "role": "reference_only"},
]


def row(**kw):
    r = dict.fromkeys(schemas.columns("funding_actions"), "")
    r.update(
        law_key="2023-28",
        section="2",
        line_item="0930-0100",
        target_law_key="2023-28",
        event_date="2023-08-09",
        calendar_year=2023,
        fiscal_year=2024,
        fy_rule="stated",
        section_type="approp_main",
        funding_action="ORIG",
        amount_kind="appropriation",
        amount=1000,
        amount_source="law_text",
    )
    r.update(kw)
    return r


# -- Record IDs ---------------------------------------------------------------------------------


def test_ids_follow_law_section_and_position_whatever_the_input_order():
    rows = [
        row(
            law_key="2023-77",
            section="178",
            line_item="2330-0100",
            funding_action="INC",
            source_para_start="900",
        ),
        row(section="2", line_item="0930-0101", source_para_start="20"),
        row(section="2", line_item="0930-0100", source_para_start="10"),
        row(section="2B", line_item="0930-0100", source_para_start="5"),
        row(
            section="10",
            line_item="",
            funding_action="PURP",
            amount_kind="none",
            source_para_start="30",
        ),
    ]
    expected = [
        "2023-028-S2-0930-0100-ORIG-1",
        "2023-028-S2-0930-0101-ORIG-1",
        "2023-028-S2B-0930-0100-ORIG-1",
        "2023-028-S10-NOITEM-PURP-1",
        "2023-077-S178-2330-0100-INC-1",
    ]
    for seed in range(5):
        shuffled = [dict(r) for r in rows]
        random.Random(seed).shuffle(shuffled)
        assert [r["record_id"] for r in combine.assign_ids(shuffled)] == expected


def test_repeats_of_one_prefix_are_numbered_in_builder_order():
    rows = [row(amount=5, source_para_start="10"), row(amount=7, source_para_start="10")]
    ids = [(r["record_id"], r["amount"]) for r in combine.assign_ids(rows)]
    assert ids == [("2023-028-S2-0930-0100-ORIG-1", 5), ("2023-028-S2-0930-0100-ORIG-2", 7)]


# -- Counting rules (§10) -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kw", "counted"),
    [
        ({}, True),  # GAA original appropriation
        ({"funding_action": "NEW", "section_type": "approp_new"}, True),
        ({"funding_action": "RED", "amount_kind": "delta", "amount": -50}, True),
        ({"amount_kind": "retained_revenue_ceiling", "flags": "retained_revenue"}, True),
        ({"section_type": "isf"}, False),  # §2B chargebacks duplicate §2 spending
        ({"section_type": "federal_grants", "flags": "federal"}, False),
        ({"section_type": "trust_transfer", "flags": "trust_transfer"}, False),
        ({"funding_action": "INT", "section_type": "interim", "amount_kind": "interim"}, False),
        (
            {
                "funding_action": "CAP",
                "section_type": "capital",
                "amount_kind": "bond_authorization",
            },
            False,
        ),
        ({"funding_action": "XFER", "section_type": "outside", "amount_kind": "transfer"}, False),
        ({"funding_action": "PAC", "amount_kind": "prior_appropriation_continued"}, False),
        ({"funding_action": "PURP", "amount_kind": "none", "amount": ""}, False),
        ({"funding_action": "REAUTH", "amount_kind": "none"}, False),
        ({"flags": "fund_transfer_chain"}, True),  # a marker only (Q24)
        (
            {"funding_action": "XFER", "amount_kind": "transfer", "flags": "fund_transfer_chain"},
            False,
        ),
        ({"federal_share": 1.0, "flags": "federal"}, False),  # wholly federal
        ({"federal_share": 0.4, "flags": "federal;federal_mixed"}, True),  # partly federal
    ],
)
def test_counts_toward_total(kw, counted):
    assert combine.counts_toward_total(row(**kw)) is counted


def test_operating_total_leaves_out_federal_shares_and_uncounted_rows():
    rows = [
        row(amount=1000, counts_toward_total="true"),
        row(amount=1000, federal_share=0.4, counts_toward_total="true"),
        row(amount=999, counts_toward_total="false"),
        row(amount="", counts_toward_total="true"),
    ]
    assert combine.operating_total(rows) == 1000 + 600


# -- Fund splits (§5.6, §7.8) -------------------------------------------------------------------


def test_a_printed_split_sets_the_main_fund_and_federal_share():
    r = row(fund_splits_raw="General Fund:60;Federal COVID-19 Response Fund:40")
    rows, splits, problems = combine.combine_rows({"test": [r]}, LAWS, FUNDS)
    assert problems == []
    assert [(s["fund_name"], s["fund_number"], s["share"], s["is_federal"]) for s in splits] == [
        ("General Fund", "0010", 0.6, "false"),
        ("Federal COVID-19 Response Fund", "0007", 0.4, "true"),
    ]
    r = rows[0]
    assert (r["fund_primary"], r["federal_share"], r["flags"]) == (
        "General Fund",
        0.4,
        "federal;federal_mixed",
    )
    assert r["counts_toward_total"] == "true"
    assert "fund_splits_raw" not in r  # helper keys aren't written


def test_one_cthru_fund_is_the_whole_row():
    rows, splits, problems = combine.combine_rows(
        {"test": [row(amount_source="cthru", fund_numbers="0007")]}, LAWS, FUNDS
    )
    assert [(s["fund_name"], s["share"]) for s in splits] == [
        ("Federal COVID-19 Response Fund", 1.0)
    ]
    assert (rows[0]["federal_share"], rows[0]["counts_toward_total"]) == (1.0, "false")
    assert problems == []


def test_several_cthru_funds_without_a_printed_split_leave_shares_empty():
    rows, splits, problems = combine.combine_rows(
        {"test": [row(amount_source="cthru", fund_numbers="0010;0007")]}, LAWS, FUNDS
    )
    assert [(s["fund_number"], s["share"]) for s in splits] == [("0010", ""), ("0007", "")]
    assert (rows[0]["fund_primary"], rows[0]["federal_share"]) == ("", "")
    assert [p["problem"] for p in problems] == [
        "several CTHRU funds and no printed split: 0010;0007"
    ]


def test_the_section_fund_is_the_default_and_unknown_funds_are_reported():
    rows, splits, problems = combine.combine_rows(
        {
            "test": [
                row(section_fund_default="General Fund"),
                row(line_item="0930-0101", section_fund_default="Mystery Trust Fund"),
            ]
        },
        LAWS,
        FUNDS,
    )
    assert [(s["fund_name"], s["is_federal"]) for s in splits] == [
        ("General Fund", "false"),
        ("Mystery Trust Fund", "false"),
    ]
    assert [p["problem"] for p in problems] == ["fund not in config/funds.csv: Mystery Trust Fund"]
    assert rows[1]["fund_primary"] == "Mystery Trust Fund"


def test_a_bond_rows_federal_share_from_its_borrowing_limit_is_kept():
    r = row(
        funding_action="CAP",
        section_type="capital",
        amount_kind="bond_authorization",
        federal_share=0.8,
        flags="federal;federal_mixed",
    )
    rows, splits, _ = combine.combine_rows({"bonds": [r]}, LAWS, FUNDS)
    assert splits == []
    assert (rows[0]["federal_share"], rows[0]["flags"]) == (0.8, "federal;federal_mixed")


# -- Scope, manual rows, running amounts --------------------------------------------------------


def test_reference_only_laws_are_left_out_and_reported():
    rows, _, problems = combine.combine_rows(
        {"annual": [row(), row(law_key="2020-227", target_law_key="2020-227")]}, LAWS, FUNDS
    )
    assert [r["law_key"] for r in rows] == ["2023-28"]
    assert [p["problem"] for p in problems] == ["annual: the law isn't in scope, row left out"]


def test_manual_rows_are_marked_manual():
    manual = row(amount_source="law_text", flags="multi_year")
    manual.update(record_id=None, source_quote="…", entered_by="Emma", entered_on="2026-11-10")
    del manual["record_id"]
    [r] = combine.manual_rows([manual])
    assert (r["amount_source"], r["flags"]) == ("manual", "multi_year;manual_row")
    assert list(r) == schemas.columns("funding_actions")


def test_running_amounts_point_at_the_funding_action_that_made_them():
    rows = combine.assign_ids(
        [
            row(
                law_key="2023-77",
                section="178",
                line_item="2330-0100",
                target_law_key="2023-28",
                funding_action="INC",
                amount_kind="delta",
                amount=350_000,
            )
        ]
    )
    amounts = [
        {
            "law_key": "2023-77",
            "section": "178",
            "target_law_key": "2023-28",
            "target_section": "2",
            "target_item": "2330-0100",
            "amount_after": 9_660_231,
        },
        {
            "law_key": "2023-77",
            "section": "179",
            "target_law_key": "2023-28",
            "target_section": "2",
            "target_item": "2330-0100",
            "amount_after": 1,
        },  # no row yet
    ]
    assert combine.running_amounts(rows, amounts) == [
        {
            "target_law_key": "2023-28",
            "section": "2",
            "line_item": "2330-0100",
            "as_of_event": "2023-077-S178-2330-0100-INC-1",
            "amount_after": 9_660_231,
        }
    ]


# -- The stage on the samples -------------------------------------------------------------------


def test_the_stage_on_the_bond_samples(root, samples_dir, tmp_path):
    ctx = Context(
        root=root,
        raw_dir=samples_dir,
        interim_dir=tmp_path / "interim",
        reports_dir=tmp_path / "reports",
        offline=True,
    )
    assert read_bonds.run(ctx) == 0
    assert combine.run(ctx) == 0
    for table in ("funding_actions", "fund_splits", "running_amounts"):
        assert schemas.validate_file(table, ctx.interim_dir / f"{table}.csv") == []
    _, rows = schemas.read_csv(ctx.interim_dir / "funding_actions.csv")
    _, expected = schemas.read_csv(samples_dir / "expected" / "bond_items.csv")
    assert len(rows) == len(expected)
    assert len({r["record_id"] for r in rows}) == len(rows)
    assert {r["counts_toward_total"] for r in rows} == {"false"}
    assert combine.capital_total(rows) == 1_656_989_000 + 1_185_000_000


def test_a_reference_only_manual_row_is_left_out_quietly():
    # 1993-52 is kept by hand only to give item 4000-8200 its starting amount (issue #41)
    laws = [*LAWS, {"law_key": "1993-52", "role": "reference_only"}]
    manual = combine.manual_rows([row(law_key="1993-52", target_law_key="1993-52")])
    rows, _, problems = combine.combine_rows({combine.MANUAL_PIECE: manual}, laws, FUNDS)
    assert rows == [] and problems == []
    # any other piece's row from a law that isn't in scope is still reported
    _, _, problems = combine.combine_rows({"annual": manual}, laws, FUNDS)
    assert len(problems) == 1


# -- Q33 (2026-11-11) ---------------------------------------------------------------------------


def test_a_missing_input_is_reported(root, samples_dir, tmp_path, capsys):
    ctx = Context(
        root=root,
        raw_dir=samples_dir,
        interim_dir=tmp_path / "interim",
        reports_dir=tmp_path / "reports",
        offline=True,
    )
    assert read_bonds.run(ctx) == 0  # bond files only: no items_raw, amendments or CTHRU
    assert combine.missing_inputs(ctx) == ["items_raw", "amendments_raw", "cthru_line_items"]
    combine.run(ctx)
    out = capsys.readouterr().out
    assert "WARNING: items_raw.csv is missing (run the read_items stage first)" in out
    _, problems = schemas.read_csv(ctx.reports_dir / "combine_problems.csv")
    assert sum("is missing" in p["problem"] for p in problems) == 3


def test_two_changes_to_one_item_in_one_section_get_their_own_events():
    rows = combine.assign_ids(
        [
            row(
                law_key="2023-77",
                section="178",
                line_item="2330-0100",
                target_law_key="2023-28",
                funding_action="INC",
                amount_kind="delta",
                amount=100,
            ),
            row(
                law_key="2023-77",
                section="178",
                line_item="2330-0100",
                target_law_key="2023-28",
                funding_action="PURP",
                amount_kind="none",
                amount="",
            ),  # wording: not an event
            row(
                law_key="2023-77",
                section="178",
                line_item="2330-0100",
                target_law_key="2023-28",
                funding_action="INC",
                amount_kind="delta",
                amount=50,
            ),
        ]
    )
    amount = {
        "law_key": "2023-77",
        "section": "178",
        "target_law_key": "2023-28",
        "target_section": "2",
        "target_item": "2330-0100",
    }
    got = combine.running_amounts(
        rows, [dict(amount, amount_after=1100), dict(amount, amount_after=1150)]
    )
    assert [(a["as_of_event"], a["amount_after"]) for a in got] == [
        ("2023-077-S178-2330-0100-INC-1", 1100),
        ("2023-077-S178-2330-0100-INC-2", 1150),
    ]
