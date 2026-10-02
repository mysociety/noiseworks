# Thanks to and adapted from
# https://github.com/atschwarz/formtools-wizard-multiple-fileupload/blob/master/multi_file_upload/storage.py

from django.core.files.uploadedfile import UploadedFile
from django.utils.datastructures import MultiValueDict
from formtools.wizard.storage.exceptions import NoFileStorageConfigured
from formtools.wizard.storage.session import SessionStorage


class MultiFileSessionStorage(SessionStorage):
    storage_name = "{}.{}".format(__name__, "MultiFileSessionStorage")

    def reset(self):
        # Store unused temporary file names in order to delete them
        # at the end of the response cycle through a callback attached in
        # `update_response`.
        wizard_files = self.data[self.step_files_key]
        for step_files in wizard_files.values():
            for file_list in step_files.values():
                for step_file in file_list:
                    self._tmp_files.append(step_file["tmp_name"])
        self.init_data()

    def get_step_files(self, step):
        wizard_files = self.data[self.step_files_key].get(step, {})

        if wizard_files and not self.file_storage:
            raise NoFileStorageConfigured(
                "You need to define 'file_storage' in your "
                "wizard view in order to handle file uploads."
            )

        files = {}
        for field in wizard_files.keys():
            uploaded_file_list = []

            for field_dict in wizard_files.get(field, []):
                field_dict = field_dict.copy()
                tmp_name = field_dict.pop("tmp_name")
                if (step, field, field_dict["name"]) not in self._files:
                    self._files[(step, field, field_dict["name"])] = UploadedFile(
                        file=self.file_storage.open(tmp_name), **field_dict
                    )
                uploaded_file_list.append(
                    self._files[(step, field, field_dict["name"])]
                )
            files[field] = uploaded_file_list
        return MultiValueDict(files) or None

    def set_step_files(self, step, files):
        if files and not self.file_storage:
            raise NoFileStorageConfigured(
                "You need to define 'file_storage' in your "
                "wizard view in order to handle file uploads."
            )

        if step not in self.data[self.step_files_key]:
            self.data[self.step_files_key][step] = {}

        for field in (files or {}).keys():
            self.data[self.step_files_key][step][field] = []
            for field_file in files.getlist(field):
                tmp_filename = self.file_storage.save(field_file.name, field_file)
                file_dict = {
                    "tmp_name": tmp_filename,
                    "name": field_file.name,
                    "content_type": field_file.content_type,
                    "size": field_file.size,
                    "charset": field_file.charset,
                }
                self.data[self.step_files_key][step][field].append(file_dict)
