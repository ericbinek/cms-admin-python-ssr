# schema.org aligned CMS Admin (Python)

[![Tests](https://github.com/ericbinek/cms-admin-python-ssr/actions/workflows/test.yml/badge.svg)](https://github.com/ericbinek/cms-admin-python-ssr/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)
![Status](https://img.shields.io/badge/status-work_in_progress-orange.svg)
![Build in public](https://img.shields.io/badge/build-in_public-ff69b4.svg)
![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)
![Python 3.14](https://img.shields.io/badge/Python-3.14-blue.svg)

A server rendered admin interface for a schema.org aligned CMS, written in plain Python 3.14.

There is no `requirements.txt` and no virtual environment to manage. It serves semantic HTML from `http.server`, with no template engine and no build step.

It is login protected and offers full create, edit, and delete management for 14 schema.org entity types such as BlogPosting, Person, and Organization. It is a stateless proxy: the browser holds an HttpOnly session cookie, the server translates it into a bearer token for the CMS API, and the API stays the authority for authentication and permissions. State changing forms carry a CSRF synchronizer token.

A conformance test suite defines the markup and behavior.

## Status: work in progress (v0.3.0)

This is an ongoing build-in-public project, shared only for community and communication purposes. Do not deploy it in production. Do not rely on its interfaces or data format remaining stable.

## No virtualenv

Modern Python usually pushes you into a virtual environment before you can `pip install` anything (PEP 668). Here there is nothing to install, so there is no venv to create. The whole thing is the standard library: `http.server`, `json`, `unittest`. Run it with the system `python3`.

## Requirements

- Python 3.14 or newer

## Installation

```sh
git clone https://github.com/ericbinek/cms-admin-python-ssr.git
cd cms-admin-python-ssr
cp .env.example .env
```

## Running

```sh
python3 -m app
```

The server listens on `PORT` (default 5004).

## Usage

Open http://localhost:5004/ in a browser and sign in. Accounts live in the CMS API; there is no self-registration.
Each entity has a list view at `/<plural>`, a detail view at `/<plural>/:id`, and create/edit/delete flows.

Configure the upstream API via the `API_BASE_URL` environment variable. Set `COOKIE_SECURE=true` when serving over HTTPS.

## Entities

- `BlogPosting`
- `Person`
- `Organization`
- `WebPage`
- `ImageObject`
- `VideoObject`
- `AudioObject`
- `CategoryCode`
- `CategoryCodeSet`
- `DefinedTerm`
- `DefinedTermSet`
- `Comment`
- `WebSite`
- `SiteNavigationElement`

## Testing

```sh
python3 -m unittest discover tests
```

## Contributing

Contributions are welcome. This is a build-in-public project, so issues, questions, and ideas count as much as pull requests. If you send code, keep it on the standard library with no new dependencies, use type hints, and keep the conformance suite green, since the tests are the contract. Run them with `python3 -m unittest discover tests`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guidelines.

## License

MIT. See [LICENSE](LICENSE).
