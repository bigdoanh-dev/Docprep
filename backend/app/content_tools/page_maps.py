"""Printed page numbers of the scanned sources, tied to the exact source file (sha256).

An image index is the 1-based position of a page image in the Word file (`Loc.image_indices`). Each
profile maps a run of images to the page number printed on them: body pages by a constant offset,
front matter to lower-case roman numerals. Images outside every run (cover, blank pages before the
body) have no printed number and stay unmapped.

Checked 28/11/2026 by OCR of the header and footer band of every image: every body image where a
number was read agrees with the offset (ngodoc 218/221 images, dtch 211/217). The images where none
was read were checked by eye: ngodoc 54, 147, 149 carry 47, 140, 142; dtch 33, 83, 123, 143, 161
and 193 are blank pages between chapters. dtch front matter reads iii..xv on images 4..16.
"""
from collections.abc import Iterable

PAGE_MAPS = {
    # Hướng dẫn chẩn đoán và xử trí ngộ độc (ngodoc): page 1 is image 8, page 221 is image 228.
    "78b02a87b28348ebe09a4a68905553379d851be4afbcbd3d520f4eb4f295412a": {
        "version": "ngodoc-pages-v1",
        "body": {"first_image": 8, "last_image": 228, "offset": 7},
    },
    # Dịch tễ học cơ bản (dtch): page 1 is image 18, page 217 is image 234; Mục lục iii..xv.
    "51e184938defd0dfad9f02929068f34938ea2a087109aab725bed197f67af449": {
        "version": "dtch-pages-v1",
        "body": {"first_image": 18, "last_image": 234, "offset": 17},
        "roman": {"first_image": 4, "last_image": 16, "offset": 1},
    },
}


def roman(number: int) -> str:
    out = ""
    for value, digits in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
                          (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while number >= value:
            out, number = out + digits, number - value
    return out


def printed_page(profile: dict, image: int) -> str | None:
    body = profile["body"]
    if body["first_image"] <= image <= body["last_image"]:
        return str(image - body["offset"])
    front = profile.get("roman")
    if front and front["first_image"] <= image <= front["last_image"]:
        return roman(image - front["offset"])
    return None


def printed_pages(source_sha256: str | None, images: Iterable[int] | None) -> list[str] | None:
    """Printed pages for page images, in image order; None when the source has no verified profile."""
    profile = PAGE_MAPS.get(source_sha256 or "")
    if not profile or not images:
        return None
    pages = [p for p in dict.fromkeys(printed_page(profile, i) for i in images) if p]
    return pages or None


def version(source_sha256: str | None) -> str | None:
    profile = PAGE_MAPS.get(source_sha256 or "")
    return profile["version"] if profile else None
