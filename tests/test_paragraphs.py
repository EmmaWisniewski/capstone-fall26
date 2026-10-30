"""paragraphs.py: law HTML to paragraphs (DESIGN §7.2, §11.1)."""

import copy
import functools
import json

import pytest

from ma_approps import schemas
from ma_approps.paragraphs import key, normalize, paragraphs

SAMPLE_LAWS = ("2023-28", "2023-77", "2024-140", "2025-3", "2021-35", "2023-15")


@functools.cache
def _load(path, law_key):
    return paragraphs(law_key, json.loads(path.read_text("utf-8"))["ChapterText"])


def load(samples_dir, law_key):
    year, chapter = law_key.split("-")
    return copy.deepcopy(_load(samples_dir / "sessionlaws" / year / f"{chapter}.json", law_key))


def texts(html):
    return [p["text"] for p in paragraphs("2099-1", html)]


# -- small HTML cases ---------------------------------------------------------


def test_keys_and_indexes():
    ps = paragraphs("2099-1", "<p>a</p><p> </p><p>b</p>")
    assert [tuple(p) for p in ps] == [schemas.PARAGRAPH_KEYS] * 2
    assert [p["para_idx"] for p in ps] == [0, 1]  # empty paragraphs are dropped


def test_block_tags_br_and_hr_are_boundaries():
    html = "<div><p>one</p></div><h3>TWO.</h3><center>three</center>four<br />five<hr />six"
    assert texts(html) == ["one", "TWO.", "three", "four", "five", "six"]


def test_text_split_across_spans_is_joined():
    assert texts("<p><span>0930-</span><span>0100</span> For it..... $6,<b>077</b>,671</p>") == [
        "0930-0100 For it..... $6,077,671"
    ]


def test_normalization():
    assert normalize("1108‑5200&nbsp;x") == "1108-5200&nbsp;x"  # entities are the parser's job
    assert texts("<p>1108–5200  For  the\n plan</p>") == ["1108-5200 For the plan"]
    assert texts("<p>fiscal years 2023–2024 and 10–20</p>") == [
        "fiscal years 2023-2024 and 10–20"
    ]
    assert texts("<p>costs… $5</p>") == ["costs... $5"]  # NFKC


def test_smart_quotes_kept_in_text_but_not_in_key():
    (text,) = texts("<p>striking out the figure “$9,310,231”</p>")
    assert "“" in text
    assert key(text) == 'striking out the figure "$9,310,231"'


def test_struck_bold_and_links():
    html = (
        '<p><strong>Governor reduced the following item, see <a href="/Bills/193/H4055">'
        "House, No. 4055</a></strong><br />2210-0106 For it.... "
        '<span style="text-decoration: line-through;">$4,025,451</span> <s>$9</s> '
        '<strong style="x">$2,888,473</strong></p>'
    )
    note, item = paragraphs("2099-1", html)
    assert note["bold"] == ["Governor reduced the following item, see House, No. 4055"]
    assert note["links"] == ["/Bills/193/H4055"]
    assert item["struck"] == ["$4,025,451", "$9"]
    assert item["bold"] == ["$2,888,473"]
    assert item["text"] == "2210-0106 For it.... $4,025,451 $9 $2,888,473"
    assert item["raw_html"].startswith("2210-0106")


def test_bold_style_and_classes():
    html = '<p class="MsoNormal x"><span style="font-weight: bold">B</span></p>'
    (p,) = paragraphs("2099-1", html)
    assert p["bold"] == ["B"] and p["classes"] == ["MsoNormal", "x"]


def test_table_row_is_one_paragraph():
    html = "<table><tr><td><p>ABINGTON</p></td><td><p>$1</p></td></tr><tr><td>B</td></tr></table>"
    assert texts(html) == ["ABINGTON | $1", "B"]


def test_raw_html_is_the_source_slice():
    html = '<p style="a">x &amp; y</p>\n<p>z</p>'
    ps = paragraphs("2099-1", html)
    assert [p["raw_html"] for p in ps] == ['<p style="a">x &amp; y</p>', "<p>z</p>"]
    assert ps[0]["text"] == "x & y"


# -- samples ------------------------------------------------------------------


@pytest.mark.parametrize("law_key", SAMPLE_LAWS)
def test_samples_are_deterministic_and_clean(samples_dir, law_key):
    ps = load(samples_dir, law_key)
    year, chapter = law_key.split("-")
    html = json.loads((samples_dir / "sessionlaws" / year / f"{chapter}.json").read_text("utf-8"))
    assert ps and ps == paragraphs(law_key, html["ChapterText"])  # same input, same output
    assert [p["para_idx"] for p in ps] == list(range(len(ps)))
    for p in ps:
        assert p["law_key"] == law_key
        assert p["text"] == p["text"].strip() and "  " not in p["text"] and "\xa0" not in p["text"]


def test_supplemental_item_2025_3(samples_dir):
    ps = load(samples_dir, "2025-3")
    i = next(i for i, p in enumerate(ps) if p["text"] == "SECTION 2.")
    assert [p["text"] for p in ps[i + 1 : i + 4]] == [
        "EXECUTIVE OFFICE FOR ADMINISTRATION AND FINANCE",
        "Group Insurance Commission",
        "1108-5200 Group Insurance Premium and Plan Costs "
        + "." * 85
        + " $240,000,000.",
    ]


def test_gaa_header_then_item_2023_28(samples_dir):
    ps = load(samples_dir, "2023-28")
    i = next(i for i, p in enumerate(ps) if p["text"].startswith("0930-0100 "))
    assert ps[i - 1]["text"] == "OFFICE OF THE CHILD ADVOCATE."
    assert ps[i]["text"].endswith("$6,077,671")


def test_gaa_veto_markup_2023_28(samples_dir):
    ps = load(samples_dir, "2023-28")
    i = next(i for i, p in enumerate(ps) if p["text"].startswith("2210-0106 "))
    assert ps[i - 1]["text"].startswith("Governor reduced the following item")
    assert ps[i - 1]["links"] == ["/Bills/193/H4055"]
    assert ps[i]["struck"][-1] == "$4,025,451"
    assert ps[i]["text"].endswith("$4,025,451 $2,888,473")


def test_gaa_veto_markup_2024_140(samples_dir):
    # §11.4: the only annotated reduction in the FY2025 GAA
    ps = load(samples_dir, "2024-140")
    item = next(p for p in ps if p["text"].startswith("1108-5200 "))
    assert item["struck"] == ["$2,169,893,912"]
    assert item["text"].endswith("$2,169,893,912 $2,163,893,912")
    assert sum("$2,169,893,912" in p["struck"] for p in ps) == 1
