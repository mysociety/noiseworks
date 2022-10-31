import re
import tempfile
from unittest.mock import mock_open

import pytest
from botocore.stub import Stubber
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management import CommandError, call_command


from cases.management.commands.export_data import client

from ..models import Action, ActionFile, Case, Notification, User
from .conftest import ADDRESS


@pytest.fixture
def call_params(db, capsys, monkeypatch):
    call_command("loaddata", "action_types_hackney")
    uprns = "1\n2\n3\n4"
    monkeypatch.setattr("builtins.open", lambda x: mock_open(read_data=uprns)())
    return {"uprns": "uprns.csv", "fixed": True}


@pytest.fixture
def mock_things(requests_mock):
    requests_mock.get(
        re.compile("uprn=[1-3]"),
        json={"data": {"address": [ADDRESS]}},
    )
    requests_mock.get(
        re.compile("uprn=4"),
        json={"data": {"address": []}},
    )
    requests_mock.get(
        re.compile("mapit.mysociety.org"),
        json={
            "2508": {"type": "LBO"},
            "144397": {"type": "LBW", "codes": {"gss": "E05009385"}},
        },
    )
    requests_mock.get(re.compile("greenspaces/ows"), json={"features": []})
    requests_mock.get(re.compile("transport/ows"), json={"features": []})
    requests_mock.get(re.compile("housing/ows"), json={"features": []})


@pytest.fixture
def case(db):
    return Case.objects.create(kind="diy", ward="E05009373")


@pytest.fixture
def action(db, case):
    return Action.objects.create(case=case)


@pytest.fixture
def action_file_without_file(db, action):
    return ActionFile.objects.create(action=action)


@pytest.fixture
def temp_dir_path():
    with tempfile.TemporaryDirectory() as path:
        yield path


@pytest.fixture
def use_temp_dir_media_root(temp_dir_path, settings):
    settings.MEDIA_ROOT = temp_dir_path


@pytest.fixture
def staff_user(db):
    return User.objects.create(is_staff=True, username="staffuser")


@pytest.fixture
def s3_stub():
    with Stubber(client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


def test_random_command_bad_input(db, monkeypatch):
    with pytest.raises(CommandError):
        call_command("add_random_cases")
    monkeypatch.setattr("builtins.open", lambda x: mock_open(read_data="")())
    with pytest.raises(CommandError):
        call_command("add_random_cases", uprns="uprns.csv")


def test_random_command_no_mapit(requests_mock, mock_things, db, call_params):
    requests_mock.get(
        re.compile("mapit.mysociety.org"),
        json={"error": "There was an error"},
    )
    with pytest.raises(Exception) as excinfo:
        call_command("add_random_cases", number=1, **call_params)
    assert "Error calling MapIt" == str(excinfo.value)


def test_random_command(mock_things, db, call_params):
    # Calling without commit does still save some things to the database at present
    call_command("add_random_cases", number=12, **call_params)


def test_random_command_commit(mock_things, db, call_params):
    # 71 is enough for the fixed random seed to return all possible values
    call_command("add_random_cases", number=71, commit=True, **call_params)


def test_export_data_file_command(case, db, tmpdir):
    with pytest.raises(CommandError):
        call_command("export_data")
    call_command("export_data", dir=tmpdir, verbosity=3)


def test_export_data_s3_command(case, db, s3_stub):
    for i in range(6):
        s3_stub.add_response(
            "create_multipart_upload", service_response={"UploadId": "UploadId"}
        )
        s3_stub.add_response("upload_part", service_response={"ETag": "ETag"})
        s3_stub.add_response("complete_multipart_upload", service_response={})
    call_command("export_data", s3=True, verbosity=2)


def test_close_cases_command_bad_input(case):
    with pytest.raises(CommandError) as excinfo:
        call_command("close_cases")
    assert "Please specify a number of days" == str(excinfo.value)


def test_close_cases_command(call_params, case):
    case2 = Case.objects.create(kind="diy", ward="E05009373")
    case3 = Case.objects.create(kind="diy", ward="E05009373")
    case4 = Case.objects.create(kind="diy", ward="E05009373")
    case3.merge_into(case4)
    case3.save()
    for c in (case, case2, case3, case4):
        c.created = "2021-01-01T12:00:00Z"
        c.save()
    call_command("close_cases", days=28, verbosity=0)
    case.refresh_from_db()
    assert not case.closed
    call_command("close_cases", days=28, commit=True)
    case.refresh_from_db()
    assert case.closed
    case3.refresh_from_db()
    assert not case3.closed
    case4.refresh_from_db()
    assert not case4.closed


def test_delete_local_orphaned_files_command_bad_input():
    with pytest.raises(CommandError) as excinfo:
        call_command("delete_local_orphaned_files")
    assert "Please specify a path" == str(excinfo.value)


def test_delete_local_orphaned_files_command(
    use_temp_dir_media_root, action_file_without_file, temp_dir_path
):
    storage = FileSystemStorage(location=temp_dir_path)
    storage.save("orphan.txt", ContentFile("content"))
    action_file_without_file.file.save("not_orphan.txt", ContentFile("content"))

    assert storage.exists("orphan.txt")
    assert storage.exists("not_orphan.txt")

    call_command("delete_local_orphaned_files", path=temp_dir_path)

    assert not storage.exists("orphan.txt")
    assert storage.exists("not_orphan.txt")


def test_delete_old_notifications_command_bad_input(case):
    with pytest.raises(CommandError) as excinfo:
        call_command("delete_old_notifications")
    assert "Please specify a number of days" == str(excinfo.value)


def test_delete_old_notifications_command(case, staff_user):
    old = Notification.objects.create(
        case=case,
        recipient=staff_user,
        message="old",
        time="2021-01-01T12:00:00Z",
    )
    recent = Notification.objects.create(
        case=case,
        recipient=staff_user,
        message="recent",
    )
    call_command("delete_old_notifications", days=28)
    all_ = Notification.objects.all()
    assert recent in all_
    assert old not in all_
