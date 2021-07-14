# NoiseWorks

Repository to hold code for noise case management software.

This repository houses a Django project, running against a PostgreSQL database.

## Local Development

### Code dependencies

This repository is using poetry for python package management. There is an
installer for it (though they're switching to a new one, which sounds better),
but there are also hundreds of open issues for it. It may be fine.

I installed poetry by installing pipx – https://pypa.github.io/pipx/ – and then
installed poetry using that – `pipx install poetry`. For stable poetry, this
may apparently have an issue with respect to multiple python versions, but it is
unclear. In the master poetry docs, the warning has been removed. We are not
really bothered about multiple python versions for this project.

Anyway, once you have poetry installed, `script/setup` will install the dependencies.

### Running

Private settings are read from environment variables, which can be listed in a local .env file.

* `poetry run script/server` to run migrate and the dev server

### Tests

* `script/test` or `script/test --coverage` to run the tests (100% coverage at present).

Tests are written with pytest; the current examples should show uses of test
client, fixtures, request mocking, settings override, and so on.

### Contributing

* `black` is run for code tidying: `poetry run black .`

* Static files are handled by django-compressor with django-libsass. SCSS files
  are automatically compiled and dealt with.
