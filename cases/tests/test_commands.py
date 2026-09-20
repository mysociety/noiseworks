import re
import tempfile
from unittest.mock import mock_open

import pytest
from botocore.stub import Stubber
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management import CommandError, call_command

from cases.management.commands.export_data import client
from cases.models import ActionType
from cobrands.interface import AddressDetail, LocationDetail
from cobrands.testing import TestCobrand

from ..models import Action, ActionFile, Case, Notification, User


@pytest.fixture
def call_params(db, capsys, monkeypatch):
    uprns = "1\n2\n3\n4"
    monkeypatch.setattr("builtins.open", lambda x: mock_open(read_data=uprns)())
    return {"uprns": "uprns.csv", "fixed": True}


class TestCobrandWithLookupData(TestCobrand):
    def address_detail_for_uprn(self, uprn):
        if uprn in ["1", "2", "3"]:
            return AddressDetail(
                uprn="10001",
                point=None,
                label="Address",
                ward_gss="GSS1",
                in_an_estate=True,
            )
        return None

    def location_detail_for_point(self, point):
        return LocationDetail(
            point=point,
            description="point description",
            ward_gss="GSS1",
            in_an_estate=False,
        )

    def example_uprns(self):
        return ["1", "2", "3"]


pytestmark = pytest.mark.cobrand.with_args(TestCobrandWithLookupData)


@pytest.fixture
def case(db):
    return Case.objects.create(kind="diy", ward="GSS1")


@pytest.fixture
def action(db, case):
    return Action.objects.create(case=case)


@pytest.fixture
def action_file_without_file(db, action):
    return ActionFile.objects.create(action=action)


@pytest.fixture
def action_types(db):
    ActionType.objects.create(
        name="Case closed",
        common=False,
        visibility="staff",
    )
    ActionType.objects.create(
        name="Contacted complainant",
        common=True,
        visibility="public",
    )
    ActionType.objects.create(
        name="Edit case",
        common=False,
        visibility="internal",
    )
    ActionType.objects.create(
        name="Action 1",
        common=True,
        visibility="public",
    )
    ActionType.objects.create(
        name="Action 2",
        common=False,
        visibility="internal",
    )


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


def test_random_command_with_uprn_file(db, call_params, action_types):
    # Calling without commit does still save some things to the database at present
    call_command("add_random_cases", number=12, **call_params)


def test_random_command_with_cobrand_example_uprns(db, action_types):
    # Calling without commit does still save soGme things to the database at present
    call_command("add_random_cases", number=12)


def test_random_command_commit(db, call_params, action_types):
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


def test_close_cases_command(call_params, case, action_types):
    case2 = Case.objects.create(kind="diy", ward="GSS1")
    case3 = Case.objects.create(kind="diy", ward="GSS1")
    case4 = Case.objects.create(kind="diy", ward="GSS1")
    case3.merge_into(case4)
    case3.save()
    Case.objects.filter(id__in=(case.id, case2.id, case4.id)).update(
        where="business", modified="2021-01-01T12:00:00Z"
    )
    call_command("close_cases", days=28, verbosity=0)
    case.refresh_from_db()
    assert not case.closed
    call_command("close_cases", days=28, commit=True)
    case.refresh_from_db()
    assert case.closed
    case2.refresh_from_db()
    assert case2.closed
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
