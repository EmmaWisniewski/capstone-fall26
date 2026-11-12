"""The capital file (workstream A; DESIGN §7.13, Q5, Q11, Q16)."""

import pytest

from ma_approps import combine, export, read_bonds, schemas
from ma_approps.context import Context


@pytest.fixture(scope="module")
def capital(tmp_path_factory, request):
    root = request.config.rootpath
    out = tmp_path_factory.mktemp("capital")
    ctx = Context(
        root=root,
        raw_dir=root / "tests" / "samples",
        interim_dir=out / "interim",
        output_dir=out / "output",
        reports_dir=out / "reports",
        offline=True,
    )
    assert read_bonds.run(ctx) == 0
    assert combine.run(ctx) == 0
    path = export.write_capital_file(ctx)
    header, rows = schemas.read_csv(path)
    return path, header, {(r["Line item"], r["Section"]): r for r in rows}


def test_name_and_columns(capital):
    path, header, rows = capital
    assert path.name == "ma_capital_authorizations_cy2021_2025.csv"
    assert header == list(schemas.CAPITAL_EXPORT_COLUMNS)
    assert len(header) == 31
    assert len(rows) == 16  # every item of the two bond samples


def test_an_item_under_a_limit_its_items_exceed(capital):
    r = capital[2][("1790-3014", "2A")]
    assert (r["Law citation"], r["Enactment date"], r["Fiscal year"]) == (
        "2024 Acts, ch. 139",
        "07/29/2024",  # approved July 29, 2024: FY2025
        "2025",
    )
    assert (r["Funding action"], r["Appropriation/change ($)"]) == (
        "Capital authorization",
        "750,000,000",
    )
    assert (
        r["Borrowing limit section"],
        r["Borrowing limit ($)"],
        r["Total of items under this limit ($)"],
        r["Identified federal share ($)"],
        r["Federal split"],
    ) == ("4", "1,055,000,000", "1,455,000,000", "", "Unknown")
    assert r["Limit difference note"] == (
        "covered by §4: items exceed the borrowing limit by $400,000,000"
    )


def test_placeholders_until_labels_exist(capital):
    r = capital[2][("1790-3014", "2A")]
    assert (
        r["Program / purpose"],
        r["Policy area"],
        r["Previously funded?"],
        r["One-time or recurring funding"],
        r["New funding appropriation or re-appropriation of existing funding?"],
        r["Human review status"],
        r["Source or calculation for total"],
    ) == (
        "",
        "Not classified",
        "Unknown",
        "One-time",
        "Pending",
        "Not human reviewed",
        "Total not yet checked.",
    )


def test_items_that_add_up_get_no_note(capital):
    rows = capital[2]
    chapter_90 = [r for r in rows.values() if r["Law citation"] == "2025 Acts, ch. 17"]
    assert chapter_90 and all(r["Limit difference note"] == "" for r in chapter_90)
    assert all(r["Federal split"] == "None" for r in chapter_90)


LAW = {"law_key": "2020-383", "acts_year": "2020", "chapter": "383", "law_name": "Transportation"}


def cap_row(**kw):
    r = dict.fromkeys(schemas.columns("funding_actions"), "")
    r.update(
        record_id="2020-383-S2-6121-2114-CAP-1",
        law_key="2020-383",
        section="2",
        line_item="6121-2114",
        target_law_key="2020-383",
        event_date="2021-01-15",
        calendar_year="2021",
        fiscal_year="2021",
        funding_action="CAP",
        amount="4400000000",
        veto_status="none",
        agency_header_raw="Massachusetts Department of Transportation.",
    )
    r.update(kw)
    return r


def limit(**kw):
    lim = {
        "law_key": "2020-383",
        "section": "32",
        "covers_sections": "2",
        "covers_items": "6121-2114",
        "authorized": "880000000",
        "items_total": "4400000000",
        "federal_share": "3520000000",
        "federal_split": "identified",
        "bond_name": "",
        "max_term_years": "40",
        "payable_by": "2061-06-30",
        "paying_fund": "General Fund",
        "available_through": "",
    }
    lim.update(kw)
    return lim


def test_an_identified_federal_share_is_shown_and_named_in_the_note():
    [r] = export.capital_rows([cap_row()], [limit()], [LAW])
    assert (r["Identified federal share ($)"], r["Federal split"]) == (
        "3,520,000,000",
        "Identified",
    )
    assert r["Limit difference note"] == (
        "covered by §32: items exceed the borrowing limit by $3,520,000,000 "
        "(the identified federal share)"
    )
    assert (r["Final payable date"], r["Agency / office"]) == (
        "06/30/2061",
        "Massachusetts Department of Transportation",
    )


def test_items_below_their_limit_and_labels_replace_placeholders():
    labels = [
        {
            "record_id": "2020-383-S2-6121-2114-CAP-1",
            "agency_office": "Highway Division",
            "program_purpose": "Bridges",
            "policy_area": "Transportation",
            "previously_funded": "No",
            "one_time_or_recurring": "One-time",
            "new_or_reapprop": "New",
        }
    ]
    lim = limit(authorized="5000000000", federal_split="none", federal_share="")
    [r] = export.capital_rows([cap_row()], [lim], [LAW], labels)
    assert r["Limit difference note"] == (
        "covered by §32: items are $600,000,000 less than the borrowing limit"
    )
    assert (
        r["Agency / office"],
        r["Policy area"],
        r["New funding appropriation or re-appropriation of existing funding?"],
    ) == ("Highway Division", "Transportation", "New")


def test_only_capital_rows_go_in():
    other = cap_row(record_id="2023-028-S2-0930-0100-ORIG-1", funding_action="ORIG")
    assert export.capital_rows([other], [], [LAW]) == []


def test_a_later_change_to_a_bond_item_takes_the_items_limit():
    # 2021-25 §3 raises 2020-383 item 6121-2118; 2021-25's own limit (§11) covers only its §2
    original = cap_row(
        record_id="2020-383-S2-6121-2118-CAP-1", line_item="6121-2118", amount="70000000"
    )
    change = cap_row(
        record_id="2021-025-S3-6121-2118-CAP-1",
        law_key="2021-25",
        section="3",
        line_item="6121-2118",
        target_law_key="2020-383",
        amount="25000000",
    )
    limits = [
        limit(
            section="33",
            covers_items="",
            authorized="95000000",
            items_total="95000000",
            federal_split="none",
            federal_share="",
        ),
        limit(
            law_key="2021-25",
            section="11",
            covers_sections="2",
            covers_items="",
            authorized="200000000",
            items_total="200000000",
            federal_split="none",
            federal_share="",
        ),
    ]
    laws = [
        LAW,
        {
            "law_key": "2021-25",
            "acts_year": "2021",
            "chapter": "25",
            "law_name": "Chapter 90 (2021)",
        },
    ]
    rows = export.capital_rows([original, change], limits, laws)
    assert [(r["Record ID"], r["Borrowing limit section"]) for r in rows] == [
        ("2020-383-S2-6121-2118-CAP-1", "33"),
        ("2021-025-S3-6121-2118-CAP-1", "33"),
    ]
