from app.services.after_sales_document_events import parse_legacy_status_event


def test_re_sent_date_becomes_latest_event():
    events = parse_legacy_status_event("Darwing re-sent date:7.10", "drawing")
    assert events == [{
        "event_type": "resent",
        "label": "已重发",
        "date_text": "7.10",
        "raw_text": "Darwing re-sent date:7.10",
    }]


def test_estimated_sample_date_is_not_treated_as_approval():
    events = parse_legacy_status_event("Estimated Ready Date for Samples: 9.10", "sample")
    assert events[0]["event_type"] == "estimated"
    assert events[0]["label"] == "预计完成"
    assert events[0]["date_text"] == "9.10"


def test_approval_text_becomes_passed_event():
    events = parse_legacy_status_event("Drawing approval date :6.22", "drawing")
    assert events[0]["event_type"] == "approved"
    assert events[0]["label"] == "已通过"
