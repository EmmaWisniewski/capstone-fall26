"""review/review_queue.csv (DESIGN §7.12, §14): every row that needs a person, on small tables."""

from ma_approps import export, schemas

LAWS = [
    {"law_key": "2024-140", "role": "in_scope", "law_type": "gaa", "primary_fy": "2025"},
    {"law_key": "2025-9", "role": "in_scope", "law_type": "supplemental", "primary_fy": ""},
    {"law_key": "2024-139", "role": "in_scope", "law_type": "bond", "primary_fy": ""},
    {"law_key": "2019-142", "role": "reference_only", "law_type": "other", "primary_fy": ""},
]


def action(rid, **kw):
    row = {
        "record_id": rid,
        "law_key": "2024-140",
        "section": "2",
        "line_item": "1000-0001",
        "target_law_key": kw.get("law_key", "2024-140"),
        "fiscal_year": "2025",
        "funding_action": "ORIG",
        "amount_kind": "appropriation",
        "amount": "100",
        "counts_toward_total": "true",
        "flags": "",
        "section_type": "approp_main",
    }
    row.update(kw)
    return row


def cthru(line_item="1000-0001", **kw):
    row = {
        "fiscal_year": "2025",
        "line_item": line_item,
        "original_enacted": "",
        "supplemental": "",
        "retained_revenue_ceiling": "",
    }
    row.update(kw)
    return row


def exported(*rids, area="Education"):
    return [{"Record ID": rid, "Policy area": area} for rid in rids]


def queue(actions, files=None, cthru_rows=(), limits=(), amendments=(), problems=()):
    files = files if files is not None else exported(*(a["record_id"] for a in actions))
    return export.review_queue(
        files, actions, list(cthru_rows), LAWS, list(limits), list(amendments), list(problems)
    )


def reasons(rows):
    return [(q["record_id"], q["reason"]) for q in rows]


def test_nothing_to_review_gives_an_empty_queue():
    assert queue([action("A")], cthru_rows=[cthru(original_enacted="100")]) == []


def test_row_without_policy_area_after_corrections():
    files = exported("A", area="Not classified") + exported("B")
    actions = [action("A"), action("B", line_item="1000-0002")]
    rows = [cthru(original_enacted="100"), cthru("1000-0002", original_enacted="100")]
    assert reasons(queue(actions, files, rows)) == [("A", "policy_area")]


def test_cthru_difference_names_our_row_or_is_blank_when_we_have_none():
    actions = [action("A")]
    rows = [cthru(original_enacted="150"), cthru("1000-0009", original_enacted="70")]
    out = queue(actions, cthru_rows=rows)
    assert reasons(out) == [("A", "cthru_mismatch"), ("", "cthru_mismatch")]
    assert out[0]["detail"] == "gaa: ours $100, CTHRU $150 (unexplained)"
    assert (out[1]["fiscal_year"], out[1]["line_item"]) == ("2025", "1000-0009")


def test_flagged_cthru_difference_is_already_explained():
    actions = [action("A", flags="cthru_mismatch")]
    assert queue(actions, cthru_rows=[cthru(original_enacted="150")]) == []


def test_unknown_fund_comes_first_and_other_problems_last():
    problems = [
        {
            "record_id": "A",
            "law_key": "2024-140",
            "section": "2",
            "line_item": "1000-0001",
            "problem": "fund not in config/funds.csv: Education Fund",
        },
        {
            "record_id": "",
            "law_key": "2024-140",
            "section": "",
            "line_item": "1599-9817",
            "problem": "CTHRU has money but no item was read",
        },
        {
            "record_id": "OUTSIDE",
            "law_key": "2026-1",
            "section": "2",
            "line_item": "",
            "problem": "a row outside the files",
        },
    ]
    out = queue([action("A")], cthru_rows=[cthru(original_enacted="100")], problems=problems)
    assert reasons(out) == [("A", "unknown_fund"), ("", "combine_problem")]
    assert [q["priority"] for q in out] == [1, 3]


def test_amendment_to_confirm_but_not_in_reference_only_laws():
    actions = [
        action("A"),
        action(
            "B",
            law_key="2025-9",
            section="7",
            funding_action="INC",
            amount_kind="delta",
            amount="0",
        ),
    ]
    amend = {
        "law_key": "2025-9",
        "section": "7",
        "target_item": "1000-0001",
        "check": "in_item_text",
        "review": "true",
        "note": "",
    }
    old = dict(amend, law_key="2019-142")
    ok = dict(amend, section="8", review="false")
    out = queue(actions, cthru_rows=[cthru(original_enacted="100")], amendments=[amend, old, ok])
    assert reasons(out) == [("B", "amendment_check")]
    assert out[0]["detail"] == "§7 changes 1000-0001: in_item_text"


def test_bond_items_under_a_limit_that_does_not_add_up():
    actions = [
        action(
            "C1",
            law_key="2024-139",
            section="2",
            line_item="1790-0001",
            funding_action="CAP",
            amount_kind="bond_authorization",
            amount="60",
            fiscal_year="2024",
            section_type="capital",
        ),
        action(
            "C2",
            law_key="2024-139",
            section="2",
            line_item="1790-0002",
            funding_action="CAP",
            amount_kind="bond_authorization",
            amount="50",
            fiscal_year="2024",
            section_type="capital",
        ),
    ]
    limits = [
        {
            "law_key": "2024-139",
            "section": "4",
            "bond_name": "IT bonds",
            "authorized": "100",
            "covers_sections": "2",
            "covers_items": "",
            "items_total": "110",
            "federal_split": "none",
            "federal_share": "",
            "max_term_years": "",
            "payable_by": "",
            "paying_fund": "",
            "available_through": "",
        }
    ]
    out = queue(actions, limits=limits)
    assert reasons(out) == [("C1", "borrowing_limit"), ("C2", "borrowing_limit")]
    assert "gap of $10" in out[0]["detail"]


def test_queue_starts_with_the_leading_columns_of_the_file_format():
    leading = tuple(c.name for c in schemas.REVIEW_QUEUE_LEADING)
    assert export.QUEUE_COLUMNS[: len(leading)] == leading == ("record_id", "reason", "priority")


def test_a_run_writing_elsewhere_never_overwrites_the_real_queue(root, tmp_path):
    from ma_approps.context import Context

    assert Context(root=root).review_queue == root / "review" / "review_queue.csv"
    test_run = Context(root=root, output_dir=tmp_path / "output")
    assert test_run.review_queue == tmp_path / "output" / "review_queue.csv"


# -- review/queue_explanations.csv (§7.21, decided 2026-11-21) ---------------------------------


def line(rid, reason="cthru_mismatch", fy="2025", item="1000-0001", law="2024-140"):
    return {
        "record_id": rid,
        "reason": reason,
        "priority": 1,
        "law_key": law,
        "fiscal_year": fy,
        "line_item": item,
        "detail": "",
        "where_to_record": "",
    }


def explanation(rid, reason="cthru_mismatch", fy="2025", item="1000-0001", text="Why."):
    return {
        "record_id": rid,
        "reason": reason,
        "law_key": "2024-140",
        "fiscal_year": fy,
        "line_item": item,
        "explanation": text,
        "explained_by": "Emma",
        "date": "2026-11-21",
    }


def test_an_explained_line_leaves_the_queue_and_a_stale_one_is_reported():
    rows = [line("a"), line("b"), line("", item="2000-0002")]  # "" = money CTHRU has, no row
    remaining, explained, stale = export.explain(
        rows,
        [
            explanation("a"),
            explanation("", item="2000-0002"),
            explanation("gone"),  # its difference was fixed since: stale
            explanation("b", text="  "),  # no explanation written: doesn't count
        ],
    )
    assert [q["record_id"] for q in remaining] == ["b"]
    assert explained == 2
    assert [e["record_id"] for e in stale] == ["gone"]


def test_an_explanation_must_match_the_line_s_reason_and_year():
    rows = [line("a", reason="amendment_check", fy="2025")]
    remaining, explained, _ = export.explain(
        rows, [explanation("a", reason="cthru_mismatch"), explanation("a", fy="2024")]
    )
    assert (len(remaining), explained) == (1, 0)


def test_the_explanations_file_format_is_checked():
    header = schemas.columns("queue_explanations")
    good = explanation("a")
    bad = dict(explanation("a"), reason="not_a_reason", date="21/11/2026")
    assert schemas.validate_rows("queue_explanations", header, [good]) == []
    assert {p.column for p in schemas.validate_rows("queue_explanations", header, [bad])} == {
        "reason",
        "date",
    }


def test_the_reasons_match_the_queue_s():
    assert tuple(export.REASONS) == schemas.QUEUE_REASONS


def test_catalog_drift_goes_on_the_queue_without_a_record_id():
    drift = [{"fiscal_year": "2022", "line_item": "7061-9612", "detail": "CTHRU name changed"}]
    files = exported("A")
    rows = export.review_queue(files, [action("A")], [cthru(original_enacted="100")], LAWS, [], [],
                               [], drift)
    assert [(q["record_id"], q["reason"], q["line_item"], q["priority"]) for q in rows] == [
        ("", "catalog_drift", "7061-9612", 3)
    ]
