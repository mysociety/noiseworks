from http import HTTPStatus

import pytest

from ..models import Action, ActionType

pytestmark = pytest.mark.django_db


def test_log_visit(admin_client, case_1):
    response = admin_client.get(f"/cases/{case_1.id}/log-visit")
    assert response.status_code == HTTPStatus.OK

    prompt_responses_and_labels = [
        ("first_impressions", "Bad", "First impressions"),
        ("sound_from_parked", "bwaah", "Sound from parked location"),
        (
            "complainants_property_arrival_time",
            "1pm",
            "Complainant's property arrival time",
        ),
        ("went_inside", "Yes", "Entered complainant's property"),
        (
            "distance_from_complainants_property",
            "1cm",
            "Distance from complainant's property",
        ),
        ("room_affected", "Pantry", "Room affected"),
        ("doors_and_windows", "Completely open", "Doors and windows open"),
        (
            "sound_at_complainants_property",
            "BWAAAH",
            "Sound at complainant's property",
        ),
        ("time_spent_listening", "An age", "Time spent listening"),
        (
            "not_statutory_nuisance_reasoning",
            "Because",
            "Reasoning if not statutory nuisance",
        ),
        ("time_complainants_property_left", "2pm", "Time complainant's property left"),
        ("additional_notes", "BWAAAAH", "Additional notes"),
    ]
    payload = {
        field_name: response for field_name, response, _ in prompt_responses_and_labels
    }
    response = admin_client.post(f"/cases/{case_1.id}/log-visit", payload, follow=True)
    assert response.status_code == HTTPStatus.OK

    action = Action.objects.get(case=case_1)
    assert action.type == ActionType.visit

    expected_notes = ""
    for _, response, label in prompt_responses_and_labels:
        expected_notes += f"{label}:\n{response}\n\n"

    assert action.notes == expected_notes


def test_logged_visit_only_includes_notes_for_entered_fields(admin_client, case_1):

    response = admin_client.post(
        f"/cases/{case_1.id}/log-visit",
        {
            "went_inside": "No",
        },
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    action = Action.objects.get(case=case_1)
    assert action.notes == "Entered complainant's property:\nNo\n\n"
