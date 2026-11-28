from app.content.publication import derived_pages
from app.content_tools.model import Block, Loc
from app.content_tools.page_maps import PAGE_MAPS, printed_pages, roman
from app.content_tools.rechunk import apply_page_map

NGODOC = "78b02a87b28348ebe09a4a68905553379d851be4afbcbd3d520f4eb4f295412a"
DTCH = "51e184938defd0dfad9f02929068f34938ea2a087109aab725bed197f67af449"


def test_body_pages_follow_the_checked_offsets():
    # Spot checks read from the page images: ngodoc image 30 prints 23, dtch image 100 prints 83.
    assert printed_pages(NGODOC, [30]) == ["23"]
    assert printed_pages(NGODOC, [8]) == ["1"] and printed_pages(NGODOC, [228]) == ["221"]
    assert printed_pages(DTCH, [100]) == ["83"]
    assert printed_pages(DTCH, [18]) == ["1"] and printed_pages(DTCH, [234]) == ["217"]
    assert printed_pages(NGODOC, [31, 32, 31]) == ["24", "25"]


def test_front_matter_is_roman_or_unmapped():
    assert printed_pages(DTCH, [12]) == ["xi"] and printed_pages(DTCH, [4]) == ["iii"]
    assert printed_pages(DTCH, [1]) is None and printed_pages(DTCH, [17]) is None
    assert printed_pages(NGODOC, [3]) is None
    assert printed_pages(NGODOC, [7, 8]) == ["1"]
    assert [roman(n) for n in (3, 4, 9, 14, 15)] == ["iii", "iv", "ix", "xiv", "xv"]


def test_unknown_source_or_missing_images_stay_unverified():
    assert printed_pages("0" * 64, [30]) is None
    assert printed_pages(None, [30]) is None
    assert printed_pages(NGODOC, None) is None and printed_pages(NGODOC, []) is None
    assert all(p["version"] for p in PAGE_MAPS.values())


def test_release_export_derives_pages_only_for_page_cited_chunks_without_them():
    row = {"citation_mode": "page", "source_sha256": NGODOC, "location": {"image_indices": [30]}}
    assert derived_pages(row) == {"printed_pages": ["23"], "version": "ngodoc-pages-v1"}
    assert derived_pages({**row, "citation_mode": "section"}) is None
    assert derived_pages({**row, "location": {"image_indices": [30], "printed_pages": ["99"]}}) is None
    assert derived_pages({**row, "source_sha256": None}) is None
    assert derived_pages({**row, "location": {"image_indices": [2]}}) is None


def test_rechunk_sets_pages_only_for_a_checked_source_file():
    def block(images):
        return Block(kind="para", text="x", loc=Loc(section_path=["A"], anchor="a", image_indices=images),
                     needs_review=["ocr_requires_review", "printed_page_unverified"])
    mapped, cover = apply_page_map([block([30, 31]), block([2])], NGODOC)
    assert mapped.loc.printed_pages == ["23", "24"] and mapped.needs_review == ["ocr_requires_review"]
    assert cover.loc.printed_pages is None and "printed_page_unverified" in cover.needs_review
    (other,) = apply_page_map([block([30])], "f" * 64)
    assert other.loc.printed_pages is None and "printed_page_unverified" in other.needs_review
