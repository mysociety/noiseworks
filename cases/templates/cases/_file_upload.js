const pond = FilePond.create(document.querySelector('input[type="file"]'));
const remainingStorageBytes = {{ remaining_file_storage_bytes }};
const submitButton = document.querySelector('input[type="submit"]');
const filesTooBigPrompt = document.querySelector('div[name="files-too-big-prompt"]');

pond.setOptions({
    {% if not can_upload_files %}
        disabled: true,
    {% endif %}
    storeAsFile: true,  // Store as hidden elements posted along with form.
});
document.addEventListener('FilePond:updatefiles', function() {
    let totalSize = 0;
    for (const file of pond.getFiles()) {
        totalSize += file.fileSize;
    }
    if (submitButton) {
        submitButton.disabled = totalSize > remainingStorageBytes;
    }
    if (filesTooBigPrompt) {
        filesTooBigPrompt.hidden = totalSize <= remainingStorageBytes;
    }
});

