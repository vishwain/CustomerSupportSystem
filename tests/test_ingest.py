"""Ingest tests: A2 (four channels) and the FR-02 bad-input fixtures, FR-03 field isolation."""

import json

import pytest

from src.ingest import (
    CHANNELS,
    DROPPED_FIELDS,
    MALFORMED,
    MAX_TEXT_CHARS,
    InputFileError,
    load,
    normalise,
    one_per_channel,
)


def raw(**over):
    base = {
        "ticket_id": "T-1",
        "channel": "email",
        "subject": "Key stopped working",
        "body": "Our API key returns 401 since this morning.",
        "received_at": "2026-03-02T08:32:00Z",
        "customer_id": "CUST-1215",
        "customer_name": "Test Person",
        "customer_tier": "business",
        "customer_region": "asia_pacific",
        "language_fluency": "fluent",
        "labels": {"intent": "api_key_issue"},
        "history": {"csat_rating": 4},
    }
    base.update(over)
    return base


@pytest.mark.parametrize("channel", CHANNELS)
def test_each_channel_gives_same_shape(channel):
    r = normalise(raw(channel=channel), 0)
    assert r.ok and r.channel == channel
    assert set(r.model_view()) == {"ticket_id", "channel", "subject", "body", "received_at", "text"}


def test_one_per_channel_from_dev_file():
    picked = one_per_channel(load("data/development_tickets.json"))
    assert [r.channel for r in picked] == list(CHANNELS)


def test_original_text_kept_and_clean_text_built():
    r = normalise(raw(subject="  Hi  ", body="Body\r\nline"), 0)
    assert r.subject == "  Hi  " and r.body == "Body\r\nline"
    assert r.text == "Hi\n\nBody\nline"


def test_private_and_label_fields_never_reach_model_view():
    r = normalise(raw(), 0)
    view = json.dumps(r.model_view())
    for value in ("CUST-1215", "Test Person", "business", "asia_pacific", "fluent", "api_key_issue"):
        assert value not in view
    assert r.held_for_validate == {"customer_id": "CUST-1215", "customer_name": "Test Person"}
    assert not any(f in r.to_dict() for f in DROPPED_FIELDS)
    assert "Test Person" not in json.dumps(r.to_dict())  # name masked in printed view


# FR-02 fixtures -------------------------------------------------------------

@pytest.mark.parametrize("body", ["", "   \n\t "])
def test_empty_or_whitespace_body_escalates(body):
    r = normalise(raw(body=body), 3)
    assert r.ingest_error == MALFORMED and r.flags["empty_body"]


def test_missing_subject_is_empty_string():
    r = normalise({k: v for k, v in raw().items() if k != "subject"}, 0)
    assert r.ok and r.subject == "" and r.flags["missing_subject"]


def test_missing_channel_and_ticket_id_defaulted():
    r = normalise({k: v for k, v in raw().items() if k not in ("channel", "ticket_id")}, 6)
    assert r.ok and r.channel == "unknown" and r.ticket_id == "ROW-0007"
    assert r.flags["missing_channel"] and r.flags["missing_ticket_id"]


def test_unknown_channel_value_kept_in_metadata():
    r = normalise(raw(channel="SMS"), 0)
    assert r.channel == "unknown" and r.metadata["channel_original"] == "SMS"


def test_channel_case_and_spaces_normalised():
    assert normalise(raw(channel=" Email "), 0).channel == "email"


def test_accented_and_non_latin_text_kept():
    body = "Café déploiement échoue. 部署失败了 Ошибка"
    r = normalise(raw(body=body), 0)
    assert r.ok and body in r.text and r.flags["non_ascii"]


def test_control_characters_removed_from_text_only():
    r = normalise(raw(body="bad\x00 chars\x07 here​"), 0)
    assert r.ok and "\x00" not in r.text and "\x07" not in r.text and "​" not in r.text
    assert r.body == "bad\x00 chars\x07 here​"
    assert r.flags["control_chars_removed"]


def test_long_body_truncated_with_flag():
    r = normalise(raw(body="x" * 10_000), 0)
    assert r.ok and len(r.text) == MAX_TEXT_CHARS and r.flags["truncated"]


def test_non_object_record_is_malformed_not_crash():
    r = normalise(["not", "a", "dict"], 4)
    assert r.ingest_error == MALFORMED and r.ticket_id == "ROW-0005"


def test_bad_timestamp_flagged_not_rejected():
    r = normalise(raw(received_at="yesterday"), 0)
    assert r.ok and r.flags["bad_received_at"]


def test_jsonl_invalid_line_becomes_malformed_record(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(raw()) + "\n{not json\n" + json.dumps(raw(ticket_id="T-2")) + "\n", encoding="utf-8")
    recs = load(p)
    assert [r.ticket_id for r in recs] == ["T-1", "ROW-0002", "T-2"]
    assert recs[1].ingest_error == MALFORMED


def test_unreadable_file_raises_input_file_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(InputFileError):
        load(p)
    with pytest.raises(InputFileError):
        load(tmp_path / "missing.json")
