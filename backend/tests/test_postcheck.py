from app.chat.postcheck import Claim, Evidence, check_tier1, numbers_in

P = {
    "p1": "Một xã có 2.000 dân; 50 người mắc. Tỷ lệ hiện mắc là 2,5%.",
    "p2": "Vắc xin được tiêm trong vòng 24 giờ đầu sau sinh.",
}


def test_numbers_vietnamese_formats():  # Review Focus 2
    assert numbers_in("2.000 dân, 2,5%") == {"2000", "2.5"}
    assert numbers_in("2000 dân, 2.5%") == {"2000", "2.5"}
    assert numbers_in("trong 24 giờ, mũi 1") == {"24", "1"}
    assert numbers_in("không có số") == set()


def test_keeps_supported_claim():
    out = check_tier1([Claim("Tỷ lệ hiện mắc là 2,5%.", ["p1"])], [Evidence("p1", "Tỷ lệ hiện mắc là 2,5%")], P)
    assert out == [Claim("Tỷ lệ hiện mắc là 2,5%.", ["p1"])]


def test_number_written_in_another_format_still_matches():  # Review Focus 2
    out = check_tier1([Claim("Xã có 2000 dân, tỷ lệ 2.5%.", ["p1"])], [Evidence("p1", "Một xã có 2.000 dân")], P)
    assert len(out) == 1


def test_quote_match_ignores_case_and_whitespace():
    out = check_tier1([Claim("Tiêm trong 24 giờ đầu.", ["p2"])], [Evidence("p2", "tiêm trong  vòng 24 GIỜ\nđầu")], P)
    assert len(out) == 1


def test_drops_claim_citing_unknown_passage():
    assert check_tier1([Claim("A", ["p9"])], [Evidence("p9", "A")], P) == []


def test_drops_claim_whose_only_quote_is_not_in_the_passage():
    assert check_tier1([Claim("Tiêm trong 24 giờ.", ["p2"])], [Evidence("p2", "không có trong đoạn")], P) == []


def test_drops_claim_with_number_absent_from_cited_passage():
    ev = [Evidence("p1", "Tỷ lệ hiện mắc là 2,5%")]
    assert check_tier1([Claim("Tỷ lệ là 3%.", ["p1"])], ev, P) == []
    assert check_tier1([Claim("Tiêm trong 24 giờ.", ["p1"])], ev, P) == []  # 24 is in p2, not in the cited p1


def test_drops_claim_without_citation():
    assert check_tier1([Claim("Không trích dẫn.", [])], [Evidence("p1", "Tỷ lệ hiện mắc là 2,5%")], P) == []


def test_keeps_good_claims_and_drops_bad_ones_together():
    claims = [Claim("Tiêm trong vòng 24 giờ.", ["p2"]), Claim("Tỷ lệ là 3%.", ["p1"])]
    ev = [Evidence("p2", "trong vòng 24 giờ đầu sau sinh"), Evidence("p1", "Tỷ lệ hiện mắc là 2,5%")]
    assert check_tier1(claims, ev, P) == [claims[0]]


def test_quote_must_be_a_real_excerpt_not_a_stray_word():  # final review, Important 4
    assert check_tier1([Claim("Bệnh lao luôn gây tử vong.", ["p1"])], [Evidence("p1", "Một")], P) == []
    assert check_tier1([Claim("Xã có 50 người mắc.", ["p1"])], [Evidence("p1", "a")], P) == []


def test_every_cited_passage_needs_its_own_quote():  # final review, Important 4
    ev = [Evidence("p1", "Tỷ lệ hiện mắc là 2,5%")]
    assert check_tier1([Claim("Tỷ lệ là 2,5%, tiêm trong 24 giờ.", ["p1", "p2"])], ev, P) == []
    both = ev + [Evidence("p2", "trong vòng 24 giờ đầu")]
    assert len(check_tier1([Claim("Tỷ lệ là 2,5%, tiêm trong 24 giờ.", ["p1", "p2"])], both, P)) == 1


def test_quote_match_ignores_dash_and_quote_typography():
    passages = {"p": "Nghiên cứu bệnh–chứng dùng “tỷ suất chênh” để đo sự kết hợp."}
    ev = [Evidence("p", 'Nghiên cứu bệnh-chứng dùng "tỷ suất chênh"')]
    assert len(check_tier1([Claim("Bệnh–chứng dùng tỷ suất chênh.", ["p"])], ev, passages)) == 1
