# NoiseWorks

Repository to hold code for noise case management software.

This repository houses a Django project, running against a PostgreSQL database.

## Local Development

### Natively

In summary, with more details below:

1. Install poetry
2. `script/setup` to install dependencies
3. `poetry run script/server` to run a server

#### Code dependencies

This repository is using poetry for python package management. There is an
installer for it (though they're switching to a new one, which sounds better),
but there are also hundreds of open issues for it. It may be fine.

I installed poetry by installing pipx – https://pypa.github.io/pipx/ – and then
installed poetry using that – `pipx install poetry`. For stable poetry, this
may apparently have an issue with respect to multiple python versions, but it is
unclear. In the master poetry docs, the warning has been removed. We are not
really bothered about multiple python versions for this project.

Anyway, once you have poetry installed, `script/setup` will install the dependencies.

#### Running

Private settings are read from environment variables, which can be listed in a local .env file.

* `poetry run script/server` to run migrate and the dev server

The first time you run `script/server`, you will be asked if you want to run
via Docker or natively. (Your choice is stored in `.env` as the `DEVENV`
variable.)

### Docker

1. Run `script/server`

The first time you do this, you will be asked if you want to run via Docker or
natively. (Your choice is stored in `.env` as the `DEVENV` variable.) Running
with Docker, `script/server` will remove stopped containers, remove the
`node_modules` volume (so it stays up to date with any changes) and runs
`docker-compose up` which creates database and web containers, with the web
container running migrate and the Django development server.

If there has been a change to a Python or Node package since your local Docker
image was last built, you’ll need to rebuild the image:

    docker-compose build
    script/server  # Outside docker

### Adding fake data

1. Get hold of a text file of UPRNs, one UPRN per line.

2. Ensure you have a `MAPIT_API_KEY` in your `.env` file.

3. Run `./manage.py loaddata action_types`

4. Run `./manage.py add_random_cases --uprns UPRN_FILE --number 100 --commit`

If you are running inside Docker you will want to enter a shell in the `web` container first:
`docker-compose exec web bash`

### Tests

* `script/test` or `script/test --coverage` to run the tests (100% coverage at present).

Tests are written with pytest; the current examples should show uses of test
client, fixtures, request mocking, settings override, and so on.

### Contributing

* `black` is run for code tidying: `poetry run black .`

* Static files are handled by django-compressor with django-libsass. SCSS files
  are automatically compiled and dealt with.
