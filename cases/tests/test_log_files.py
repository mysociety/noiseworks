from http import HTTPStatus
import tempfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from humanize import naturalsize
from pytest_django.asserts import assertContains, assertNotContains

from .conftest import add_time_to_log_payload
from ..models import (
    Action,
    ActionFile,
    CaseSettingsSingleton,
)

pytestmark = pytest.mark.django_db
TEMPDIR = tempfile.TemporaryDirectory().name


@pytest.fixture(autouse=True)
def use_temporary_media_root(settings):
    settings.MEDIA_ROOT = TEMPDIR


def test_log_files_happy_path(admin_client, case_1, action_types):
    filenames = ["test_file.txt", "another_one.txt"]
    response = admin_client.post(
        f"/cases/{case_1.id}/log",
        add_time_to_log_payload(
            {
                "notes": "notes",
                "type": action_types[0].id,
                "files": [
                    SimpleUploadedFile(
                        name=fn, content=fn.encode(), content_type="text/plain"
                    )
                    for fn in filenames
                ],
            }
        ),
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    action = Action.objects.get(case=case_1)
    action_files = ActionFile.objects.filter(action=action).all()

    filename_to_action_file = {}
    for fn in filenames:
        for action_file in action_files:
            if action_file.original_name == fn:
                filename_to_action_file[fn] = action_file

    for fn in filenames:
        if fn not in filename_to_action_file.keys():  # pragma: no cover
            pytest.fail(f"Couldn't find an ActionFile for {fn}")

    case_detail_response = admin_client.get(f"/cases/{case_1.id}")
    assert response.status_code == HTTPStatus.OK

    for fn, action_file in filename_to_action_file.items():
        action_file_url = action_file.get_absolute_url()
        assertContains(case_detail_response, 'href="%s"' % action_file_url)

        response = admin_client.get(action_file_url)
        assert response.status_code == HTTPStatus.OK
        assert response.getvalue() == fn.encode()


def test_non_staff_cant_access_logged_files(
    admin_client, client, case_1, action_types, normal_user
):
    response = admin_client.post(
        f"/cases/{case_1.id}/log",
        add_time_to_log_payload(
            {
                "notes": "notes",
                "type": action_types[0].id,
                "files": [
                    SimpleUploadedFile("test.txt", b"test", content_type="text/plain")
                ],
            }
        ),
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    action = Action.objects.get(case=case_1)
    action_file = ActionFile.objects.get(action=action)

    client.force_login(normal_user)

    response = client.get(action_file.get_absolute_url())
    assert response.status_code != HTTPStatus.OK


def test_delete_logged_file_happy_path(client, logged_action_1, staff_user_1):
    action_file = ActionFile.objects.create(
        action=logged_action_1,
        created_by=staff_user_1,
        file=SimpleUploadedFile("test.txt", b"test", content_type="text/plain"),
    )
    client.force_login(staff_user_1)

    response = client.get(f"{action_file.get_absolute_url()}/delete")
    assert response.status_code == HTTPStatus.OK

    response = client.post(f"{action_file.get_absolute_url()}/delete", follow=True)
    assert response.status_code == HTTPStatus.OK
    assert ActionFile.objects.filter(action=logged_action_1).count() == 0


def test_delete_logged_fails_for_non_logging_staff(
    client, logged_action_1, staff_user_1, staff_user_2
):
    action_file = ActionFile.objects.create(
        action=logged_action_1,
        created_by=staff_user_1,
        file=SimpleUploadedFile("test.txt", b"test", content_type="text/plain"),
    )
    client.force_login(staff_user_2)
    response = client.post(f"{action_file.get_absolute_url()}/delete", follow=True)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert ActionFile.objects.filter(action=logged_action_1).count() == 1


def test_cant_log_very_long_filenames(admin_client, case_1, action_types):
    content = b"some content"

    def _file(name):
        return SimpleUploadedFile(name, content, content_type="text/plain")

    response = admin_client.post(
        f"/cases/{case_1.id}/log",
        add_time_to_log_payload({
            "notes": "notes",
            "type": action_types[0].id,
            "files": [ _file("x" * 129) ],
        }),
        follow=True,
    )
    assert response.status_code == HTTPStatus.OK
    assertContains(response, "too long, please rename")


def test_cant_log_files_bigger_than_remaining_space(admin_client, case_1, action_types):
    content = b"some content"
    file_size = len(content)

    def _file(name):
        return SimpleUploadedFile(name, content, content_type="text/plain")

    def _attempt_file_upload_and_check(max_bytes, files, success_expected):
        CaseSettingsSingleton.instance.max_file_storage_mb = float(max_bytes) / (
            1000 * 1000
        )
        CaseSettingsSingleton.instance.save()

        case_action_files_before = ActionFile.objects.filter(
            action__case=case_1
        ).count()

        response = admin_client.post(
            f"/cases/{case_1.id}/log",
            add_time_to_log_payload(
                {
                    "notes": "notes",
                    "type": action_types[0].id,
                    "files": files,
                }
            ),
            follow=True,
        )
        assert response.status_code == HTTPStatus.OK
        case_action_files_after = ActionFile.objects.filter(action__case=case_1).count()

        remaining_space = naturalsize(case_1.file_storage_remaining_bytes)
        upload_failure_message = (
            f"There is only {remaining_space} left for attachments on this case. "
            "You can store files to the Google Drive and link to them in action notes instead."
        )

        if success_expected:
            assertNotContains(response, upload_failure_message)
            assert case_action_files_before + len(files) == case_action_files_after
        else:
            assertContains(response, upload_failure_message)
            assert case_action_files_before == case_action_files_after

    _attempt_file_upload_and_check(file_size - 1, [_file("too big single")], False)
    _attempt_file_upload_and_check(file_size, [_file("just right single")], True)
    _attempt_file_upload_and_check(
        (file_size * 2) - 1, [_file("too big second single")], False
    )
    _attempt_file_upload_and_check(
        file_size * 2, [_file("just right second single")], True
    )
    _attempt_file_upload_and_check(
        file_size * 3, [_file("too big multi 1"), _file("too big multi 2")], False
    )
    _attempt_file_upload_and_check(
        file_size * 4, [_file("just right multi 1"), _file("just right multi 2")], True
    )

    ActionFile.objects.filter(action__case=case_1)[0].delete()
    _attempt_file_upload_and_check(
        file_size * 4, [_file("just right single post delete")], True
    )
