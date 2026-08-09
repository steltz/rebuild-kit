from app.services.slug import slugify


def test_lowercases_and_hyphenates_spaces():
    assert slugify("New high priority thing") == "new-high-priority-thing"


def test_collapses_runs_of_non_alphanumeric():
    assert slugify("fix db!") == "fix-db"
    assert slugify("   ---   ") == ""


def test_known_collision_pair_matches():
    # docs/features/draft/tickets-create.md: "Fix DB" and "fix db!" must collide -- this is
    # PB-003 itself, reproduced as-is (uniqueness enforcement is WO-005, blocked on OQ-001).
    assert slugify("Fix DB") == slugify("fix db!") == "fix-db"


def test_symbols_only_title_yields_empty_slug():
    # P9 audit finding (docs/features/draft/tickets-create.md): NOT NULL doesn't reject "".
    assert slugify("!!!") == ""


def test_truncates_to_64_chars():
    title = "a" * 100
    result = slugify(title)
    assert len(result) == 64
    assert result == "a" * 64


def test_strips_leading_and_trailing_hyphens_after_collapse():
    assert slugify("  Fix DB  ") == "fix-db"
