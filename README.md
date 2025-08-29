# django-cla

A Django-based web application to handle Contributor License Agreement (CLA) requests, supporting
both individual (ICLA) and corporate (CCLA) workflows.

## Features

* **Individual CLA (ICLA)**
* **Corporate CLA (CCLA)**
* **Docuseal integration**: Uses Docuseal templates for both ICLA and CCLA.
* **Cloudflare Turnstile**: Bot protection on ICLA signing requests.
* **Webhooks**: Endpoints to receive Docuseal submission completions for both ICLA and CCLA.
* **Admin UI**: Manage and review CLA records via Django’s admin interface.

## Getting Started

### Prerequisites

* **Python** 3.11 or higher
* **Django** 5.2+
* **uv** ([installation instructions](https://docs.astral.sh/uv/getting-started/installation/))

### Installation

```bash
git clone https://github.com/quarckster/django-cla.git
cd django-cla

# Install production dependencies
uv sync --locked --no-dev
```

Copy or create a [Dynaconf](https://www.dynaconf.com/) settings file (e.g., `.secrets.toml`) with the following secrets:

```
SECRET_KEY
CCLA_WEBHOOK_SECRET_SLUG
ICLA_WEBHOOK_SECRET_SLUG
CLOUDFLARE_TURNSTILE_SECRET_KEY
DOCUSEAL_KEY
DOCUSEAL_CCLA_TEMPLATE_ID
DOCUSEAL_ICLA_TEMPLATE_ID
NOTIFICATIONS_SENDER_EMAIL
NOTIFICATIONS_RECIPIENT_EMAIL
ADMIN_SITE_HEADER
ADMIN_SITE_TITLE
ADMIN_SITE_INDEX_TITLE
```

### Running the Development Server

Use the helper script to apply migrations and start the application:

```sh
./run.sh
```

This runs migrations and launches Gunicorn on `0.0.0.0:8080`. For a pure Django workflow, you can also use:

```sh
./manage.py migrate
./manage.py runserver
```

### Running Tests

```sh
./pytest.sh
```

Dev dependencies include `pytest-django`, `pytest-mock`, and `pudb` for debugging.

## Container

Build and run using the provided `Containerfile`:

```sh
podman build -t django-cla-app .
podman run -e SECRET_KEY=... \
           -e CCLA_WEBHOOK_SECRET_SLUG=... \
           -e ICLA_WEBHOOK_SECRET_SLUG=... \
           -e CLOUDFLARE_TURNSTILE_SECRET_KEY=... \
           -e DOCUSEAL_KEY=... \
           -e DOCUSEAL_CCLA_TEMPLATE_ID=... \
           -e DOCUSEAL_ICLA_TEMPLATE_ID=... \
           -e NOTIFICATIONS_SENDER_EMAIL=... \
           -e NOTIFICATIONS_RECIPIENT_EMAIL=... \
           -p 8080:8080 \
           django-cla-app
```

The container installs dependencies via `uv sync --locked --no-dev` and starts the app with Gunicorn.

## CLA Handling Workflow

### Individual CLA (ICLA)

1. **Request**: Client calls `POST /icla/submit/` with `email`, optional `point_of_contact`, and a Turnstile token.
2. **Submission**: An `ICLA` record is created, and `create_docuseal_submission()` sends a Docuseal signing request.
3. **Webhook**: Docuseal posts to `POST /webhooks/icla/{ICLA_WEBHOOK_SECRET_SLUG}/` when signing completes.
4. **Processing**: The view updates the `ICLA` model with submitted data, downloads the signed PDF (`download_document()`), and marks it active (`is_active`). A notification email is sent.

### Corporate CLA (CCLA)

TBD

## API Endpoints

* `GET  /csrf/` - Returns a CSRF token for client requests.
* `POST /icla/submit/` - Initiate an ICLA signing request.
* `GET  /icla/{email}/status/` - Check if an ICLA is active.
* `POST /webhooks/icla/{slug}/` - Handle completed ICLA submissions.
* `POST /webhooks/ccla/{slug}/` - Handle completed CCLA submissions.
* `GET  /media/{cla_type}/{file_name}/` - Retrieve signed CLA PDFs (authentication required).

## License

This project is licensed under the Apache-2.0 License.
