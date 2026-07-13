from __future__ import annotations

import pytest

import betelgeuze_engine_v2.molecular.mmcif_syntax as mmcif_syntax
from betelgeuze_engine_v2.molecular.mmcif_syntax import (
    CifSyntaxError,
    parse_cif_block,
    tokenize_cif,
)


def test_cif_lexer_preserves_quote_state_literals_and_comments() -> None:
    tokens = tokenize_cif(
        "data_x # ignored\n"
        "_entry.id 'data_not_control'\n"
        "_test.dot '.'\n"
        "_test.question \"?\"\n"
        "_test.prime \"O5'\"\n"
        "_test.hash 'C#1' # ignored\n"
        r"_test.backslash 'C:\ligand\atom'" "\n"
    )
    assert [token.value for token in tokens] == [
        "data_x",
        "_entry.id",
        "data_not_control",
        "_test.dot",
        ".",
        "_test.question",
        "?",
        "_test.prime",
        "O5'",
        "_test.hash",
        "C#1",
        "_test.backslash",
        r"C:\ligand\atom",
    ]
    assert tokens[2].quoted is True
    assert tokens[4].quoted is True
    assert tokens[6].quoted is True
    assert tokens[-1].quoted is True


def test_cif_quote_only_closes_before_whitespace_or_end_of_line() -> None:
    tokens = tokenize_cif(
        "_test.embedded 'a'#b'\n"
        "_test.comment 'a' # actual comment\n"
    )
    assert [token.value for token in tokens] == [
        "_test.embedded",
        "a'#b",
        "_test.comment",
        "a",
    ]


def test_cif_lexer_supports_semicolon_multiline_values() -> None:
    block = parse_cif_block(
        "data_x\n"
        "_entry.details\n"
        ";first line\n"
        "second line # literal\n"
        ";\n"
        "_entry.id X\n"
    )
    details = block.scalar_values["_entry.details"]
    assert details.value == "first line\nsecond line # literal"
    assert details.quoted is True
    assert details.multiline is True


def test_cif_block_parses_multiple_categories_scalars_and_loops() -> None:
    block = parse_cif_block(
        "data_demo\n"
        "_entry.id demo\n"
        "loop_\n"
        "_entity.id\n"
        "_entity.type\n"
        "1 polymer\n"
        "2 non-polymer\n"
        "loop_\n"
        "_atom_site.id\n"
        "_atom_site.label_atom_id\n"
        "1 \"O5'\"\n"
    )
    assert block.name == "demo"
    assert block.scalar_values["_entry.id"].value == "demo"
    assert block.categories == ("_entry", "_entity", "_atom_site")
    assert block.loops[0].rows[1][1].value == "non-polymer"
    assert block.loops[1].rows[0][1].value == "O5'"


def test_cif_block_category_inventory_uses_source_first_appearance_order() -> None:
    block = parse_cif_block(
        "data_x\n"
        "loop_\n"
        "_first.id\n"
        "1\n"
        "_second.id 2\n"
        "loop_\n"
        "_first.name\n"
        "again\n"
    )
    assert block.categories == ("_first", "_second")


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("loop_\n_x.id\n1\n", "missing_data_block"),
        ("data_a\ndata_b\n", "multiple_data_blocks"),
        ("data_x\nloop_\n1\n", "missing_loop_headers"),
        ("data_x\nloop_\n_x.id\n_x.id\n1 2\n", "duplicate_loop_header"),
        ("data_x\n_x.id 1\n_x.id 2\n", "duplicate_data_name"),
        ("data_x\n_x.id\n_y.id 2\n", "missing_scalar_value"),
        ("data_x\nloop_\n_x.id\n_x.name\n1\n_y.id 2\n", "malformed_loop_rows"),
        ("data_x\nloop_\n_x.id\n", "empty_loop"),
        ("data_x\nstop_\n", "unsupported_stop"),
        ("data_x\nloop_\n_x.id\n1\nstop_\n", "unsupported_stop"),
        ("data_x\nvalue\n", "unexpected_value"),
        ("data_x\n_x.id 'open\n", "unterminated_quoted_value"),
        ("data_x\n_x.id 'closed'#not-a-comment\n", "unterminated_quoted_value"),
        ("data_x\n_x.id\n;open\n", "unterminated_multiline_value"),
        ("data_x\n_x.id\n;open\n; trailing\n", "invalid_multiline_delimiter"),
        ("data_x\n_x.id [reserved]\n", "invalid_unquoted_value"),
        ("data_x\n_x.id $frame\n", "invalid_unquoted_value"),
        ("data_x\nsave_frame\n", "unsupported_save_frame"),
        ("data_x\nglobal_\n", "unsupported_global_block"),
        ("data_x\n_x.id café\n", "invalid_character"),
        ("data_x\n_x.id 1\v_y.id 2\n", "invalid_character"),
        (f"data_x\n_x.id {'a' * 2049}\n", "line_too_long"),
        (f"data_x\n_x.id\n;open\n{'a' * 2049}\n;\n", "line_too_long"),
        (f"data_{'a' * 76}\n", "data_block_name_too_long"),
        (f"data_x\n_{'a' * 75} 1\n", "data_name_too_long"),
    ],
)
def test_cif_syntax_failure_corpus(text: str, code: str) -> None:
    with pytest.raises(CifSyntaxError) as exc_info:
        parse_cif_block(text)
    assert exc_info.value.code == code


def test_cif_syntax_rejects_wrong_argument_type() -> None:
    with pytest.raises(TypeError, match="CIF text must be a string"):
        tokenize_cif(b"data_x")


def test_cif_lexer_enforces_token_count_limit_before_block_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mmcif_syntax, "MAX_CIF_TOKEN_COUNT", 2)
    with pytest.raises(CifSyntaxError) as exc_info:
        tokenize_cif("data_x\n_x.id 1\n")
    assert exc_info.value.code == "too_many_tokens"


def test_cif_lexer_enforces_line_count_before_splitline_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mmcif_syntax, "_MAX_CIF_LINE_COUNT", 2)
    with pytest.raises(CifSyntaxError) as exc_info:
        tokenize_cif("data_x\n\n\n")
    assert exc_info.value.code == "too_many_lines"


def test_cif_multiline_closer_allows_whitespace_then_comment() -> None:
    block = parse_cif_block(
        "data_x\n"
        "_entry.details\n"
        ";first\n"
        "second\n"
        "; # closing delimiter comment\n"
    )
    assert block.scalar_values["_entry.details"].value == "first\nsecond"


def test_cif_multiline_value_with_commented_closer_works_inside_loop() -> None:
    block = parse_cif_block(
        "data_x\n"
        "loop_\n"
        "_test.id\n"
        "_test.details\n"
        "1\n"
        ";first\n"
        "second\n"
        "; # closing delimiter comment\n"
    )
    assert block.loops[0].rows[0][1].value == "first\nsecond"
