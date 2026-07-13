"""Small, dependency-free CIF 1.1 lexical and block parser for mmCIF ingest.

The molecular parser only needs data names, scalar values, and loops.  This
module deliberately stops at that structural layer: dictionary validation and
``_atom_site`` semantics live in :mod:`pdb_mmcif`.

Unlike ``shlex``, CIF quoting has no backslash escapes, quoted ``.`` and ``?``
are ordinary strings, control words are special only when unquoted, and a
semicolon in column one opens a multiline text value.  Preserving those facts
is required before molecular identity can be interpreted without silent loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


_INLINE_WHITESPACE = " \t"
_MAX_CIF_LINE_LENGTH = 2048
_MAX_CIF_LINE_COUNT = 250_000
_MAX_CIF_NAME_LENGTH = 75
MAX_CIF_TOKEN_COUNT = 2_000_000


class CifSyntaxError(ValueError):
    """Stable lexical or block-structure error raised before mmCIF semantics."""

    def __init__(self, code: str, message: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(message)
        self.line_number = None if line_number is None else int(line_number)
        location = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"cif:{self.code}{location}: {self.detail}")


@dataclass(frozen=True)
class CifToken:
    value: str
    line_number: int
    column_number: int
    quoted: bool = False
    multiline: bool = False


@dataclass(frozen=True)
class CifLoop:
    tags: tuple[str, ...]
    tag_tokens: tuple[CifToken, ...]
    rows: tuple[tuple[CifToken, ...], ...]
    line_number: int

    @property
    def categories(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_category_for_tag(tag) for tag in self.tags))


@dataclass(frozen=True)
class CifBlock:
    name: str
    scalar_values: Mapping[str, CifToken]
    loops: tuple[CifLoop, ...]
    category_order: tuple[str, ...]
    token_count: int

    @property
    def categories(self) -> tuple[str, ...]:
        return self.category_order


def _category_for_tag(tag: str) -> str:
    normalized = tag.lower()
    if "." in normalized:
        return normalized.split(".", 1)[0]
    return normalized


def _is_tag(token: CifToken) -> bool:
    return not token.quoted and len(token.value) > 1 and token.value.startswith("_")


def _is_control(token: CifToken, value: str) -> bool:
    return not token.quoted and token.value.lower() == value


def _is_data_header(token: CifToken) -> bool:
    return not token.quoted and token.value.lower().startswith("data_")


def _starts_structural_item(token: CifToken) -> bool:
    if token.quoted:
        return False
    lower = token.value.lower()
    return (
        _is_tag(token)
        or lower in {"loop_", "stop_", "global_"}
        or lower.startswith(("data_", "save_"))
    )


def tokenize_cif(text: str) -> tuple[CifToken, ...]:
    """Tokenize CIF 1.1 text while retaining quote and source-location state."""

    if type(text) is not str:
        raise TypeError("CIF text must be a string")
    line_separator_count = text.count("\n") + text.count("\r")
    if line_separator_count + 1 > _MAX_CIF_LINE_COUNT:
        raise CifSyntaxError(
            "too_many_lines",
            f"CIF input may contain at most {_MAX_CIF_LINE_COUNT} physical lines",
        )
    for offset, character in enumerate(text):
        codepoint = ord(character)
        if character not in {"\t", "\n", "\r"} and not 0x20 <= codepoint <= 0x7E:
            line_number = text.count("\n", 0, offset) + 1
            raise CifSyntaxError(
                "invalid_character",
                f"character U+{codepoint:04X} is outside the CIF 1.1 character set",
                line_number=line_number,
            )
    lines = text.splitlines()
    for line_index, line in enumerate(lines):
        if len(line) > _MAX_CIF_LINE_LENGTH:
            raise CifSyntaxError(
                "line_too_long",
                f"CIF 1.1 lines may contain at most {_MAX_CIF_LINE_LENGTH} characters",
                line_number=line_index + 1,
            )
    tokens: list[CifToken] = []

    def append_token(token: CifToken) -> None:
        if len(tokens) >= MAX_CIF_TOKEN_COUNT:
            raise CifSyntaxError(
                "too_many_tokens",
                f"CIF input may contain at most {MAX_CIF_TOKEN_COUNT} tokens",
                line_number=token.line_number,
            )
        tokens.append(token)

    line_index = 0
    while line_index < len(lines):
        line = lines[line_index]
        line_number = line_index + 1
        if line.startswith(";"):
            fragments = [line[1:]]
            opening_line = line_number
            line_index += 1
            while line_index < len(lines) and not lines[line_index].startswith(";"):
                fragments.append(lines[line_index])
                line_index += 1
            if line_index >= len(lines):
                raise CifSyntaxError(
                    "unterminated_multiline_value",
                    "semicolon-delimited text value is not closed",
                    line_number=opening_line,
                )
            closing_tail = lines[line_index][1:]
            tail_without_space = closing_tail.lstrip(_INLINE_WHITESPACE)
            valid_comment_tail = (
                len(tail_without_space) < len(closing_tail)
                and tail_without_space.startswith("#")
            )
            if closing_tail.strip() and not valid_comment_tail:
                raise CifSyntaxError(
                    "invalid_multiline_delimiter",
                    "closing semicolon delimiter must occupy its own line",
                    line_number=line_index + 1,
                )
            append_token(
                CifToken(
                    value="\n".join(fragments),
                    line_number=opening_line,
                    column_number=1,
                    quoted=True,
                    multiline=True,
                )
            )
            line_index += 1
            continue

        cursor = 0
        while cursor < len(line):
            while cursor < len(line) and line[cursor] in _INLINE_WHITESPACE:
                cursor += 1
            if cursor >= len(line) or line[cursor] == "#":
                break
            start = cursor
            quote = line[cursor] if line[cursor] in {"'", '"'} else ""
            if quote:
                cursor += 1
                characters: list[str] = []
                while cursor < len(line):
                    character = line[cursor]
                    if character == quote and (
                        cursor + 1 == len(line)
                        or line[cursor + 1] in _INLINE_WHITESPACE
                    ):
                        cursor += 1
                        break
                    characters.append(character)
                    cursor += 1
                else:
                    raise CifSyntaxError(
                        "unterminated_quoted_value",
                        "single- or double-quoted value is not closed on its line",
                        line_number=line_number,
                    )
                append_token(
                    CifToken(
                        value="".join(characters),
                        line_number=line_number,
                        column_number=start + 1,
                        quoted=True,
                    )
                )
                continue

            while cursor < len(line) and line[cursor] not in _INLINE_WHITESPACE:
                cursor += 1
            value = line[start:cursor]
            if value[0] in {"$", "[", "]"}:
                raise CifSyntaxError(
                    "invalid_unquoted_value",
                    f"unquoted value may not begin with {value[0]!r} in CIF 1.1",
                    line_number=line_number,
                )
            append_token(
                CifToken(
                    value=value,
                    line_number=line_number,
                    column_number=start + 1,
                )
            )
        line_index += 1
    return tuple(tokens)


def parse_cif_block(text: str) -> CifBlock:
    """Parse exactly one named CIF data block into scalar items and loops."""

    tokens = tokenize_cif(text)
    if not tokens or not _is_data_header(tokens[0]) or len(tokens[0].value) <= 5:
        raise CifSyntaxError("missing_data_block", "one named data_ block is required")
    block_name = tokens[0].value[5:]
    if len(block_name) > _MAX_CIF_NAME_LENGTH:
        raise CifSyntaxError(
            "data_block_name_too_long",
            f"data block code may contain at most {_MAX_CIF_NAME_LENGTH} characters",
            line_number=tokens[0].line_number,
        )
    cursor = 1
    scalar_values: dict[str, CifToken] = {}
    loops: list[CifLoop] = []
    seen_tags: set[str] = set()
    category_order: dict[str, None] = {}

    while cursor < len(tokens):
        token = tokens[cursor]
        if _is_data_header(token):
            raise CifSyntaxError(
                "multiple_data_blocks",
                "exactly one data_ block is supported per input",
                line_number=token.line_number,
            )
        if not token.quoted and token.value.lower().startswith("save_"):
            raise CifSyntaxError(
                "unsupported_save_frame",
                "save frames are not supported in molecular coordinate input",
                line_number=token.line_number,
            )
        if _is_control(token, "global_"):
            raise CifSyntaxError(
                "unsupported_global_block",
                "global blocks are not supported",
                line_number=token.line_number,
            )
        if _is_control(token, "stop_"):
            raise CifSyntaxError(
                "unsupported_stop",
                "stop_ is reserved but not part of the CIF 1.1 single-level loop grammar",
                line_number=token.line_number,
            )
        if _is_control(token, "loop_"):
            loop_line = token.line_number
            cursor += 1
            header_tokens: list[CifToken] = []
            while cursor < len(tokens) and _is_tag(tokens[cursor]):
                header_tokens.append(tokens[cursor])
                cursor += 1
            if not header_tokens:
                raise CifSyntaxError(
                    "missing_loop_headers",
                    "loop_ must be followed by one or more data names",
                    line_number=loop_line,
                )
            tags = tuple(header.value.lower() for header in header_tokens)
            overlong_header = next(
                (header for header in header_tokens if len(header.value) > _MAX_CIF_NAME_LENGTH),
                None,
            )
            if overlong_header is not None:
                raise CifSyntaxError(
                    "data_name_too_long",
                    f"data names may contain at most {_MAX_CIF_NAME_LENGTH} characters",
                    line_number=overlong_header.line_number,
                )
            if len(set(tags)) != len(tags):
                raise CifSyntaxError(
                    "duplicate_loop_header",
                    "loop data names must be unique",
                    line_number=header_tokens[0].line_number,
                )
            duplicate = next((tag for tag in tags if tag in seen_tags), None)
            if duplicate is not None:
                raise CifSyntaxError(
                    "duplicate_data_name",
                    f"data name {duplicate!r} occurs more than once in the block",
                    line_number=header_tokens[0].line_number,
                )

            values: list[CifToken] = []
            while cursor < len(tokens):
                candidate = tokens[cursor]
                if _starts_structural_item(candidate):
                    if len(values) % len(tags):
                        raise CifSyntaxError(
                            "malformed_loop_rows",
                            "loop value count does not match its header count",
                            line_number=candidate.line_number,
                        )
                    break
                values.append(candidate)
                cursor += 1
            if not values:
                raise CifSyntaxError(
                    "empty_loop",
                    "loop_ must contain at least one row",
                    line_number=loop_line,
                )
            if len(values) % len(tags):
                raise CifSyntaxError(
                    "malformed_loop_rows",
                    "loop value count does not match its header count",
                    line_number=values[-1].line_number,
                )
            rows = tuple(
                tuple(values[offset : offset + len(tags)])
                for offset in range(0, len(values), len(tags))
            )
            loops.append(
                CifLoop(
                    tags=tags,
                    tag_tokens=tuple(header_tokens),
                    rows=rows,
                    line_number=loop_line,
                )
            )
            for category in loops[-1].categories:
                category_order.setdefault(category, None)
            seen_tags.update(tags)
            if cursor < len(tokens) and _is_control(tokens[cursor], "stop_"):
                raise CifSyntaxError(
                    "unsupported_stop",
                    "stop_ is reserved but not part of the CIF 1.1 single-level loop grammar",
                    line_number=tokens[cursor].line_number,
                )
            continue

        if _is_tag(token):
            tag = token.value.lower()
            if len(token.value) > _MAX_CIF_NAME_LENGTH:
                raise CifSyntaxError(
                    "data_name_too_long",
                    f"data names may contain at most {_MAX_CIF_NAME_LENGTH} characters",
                    line_number=token.line_number,
                )
            if tag in seen_tags:
                raise CifSyntaxError(
                    "duplicate_data_name",
                    f"data name {tag!r} occurs more than once in the block",
                    line_number=token.line_number,
                )
            cursor += 1
            if cursor >= len(tokens) or _starts_structural_item(tokens[cursor]):
                raise CifSyntaxError(
                    "missing_scalar_value",
                    f"data name {tag!r} is missing its value",
                    line_number=token.line_number,
                )
            scalar_values[tag] = tokens[cursor]
            category_order.setdefault(_category_for_tag(tag), None)
            seen_tags.add(tag)
            cursor += 1
            continue

        raise CifSyntaxError(
            "unexpected_value",
            f"value {token.value!r} is not associated with a data name or loop",
            line_number=token.line_number,
        )

    return CifBlock(
        name=block_name,
        scalar_values=MappingProxyType(dict(scalar_values)),
        loops=tuple(loops),
        category_order=tuple(category_order),
        token_count=len(tokens),
    )


__all__ = [
    "CifBlock",
    "CifLoop",
    "CifSyntaxError",
    "CifToken",
    "parse_cif_block",
    "tokenize_cif",
]
