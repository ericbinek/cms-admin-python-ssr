# Roadmap

The goal is a CMS whose content is structured and schema.org-native, managed through a semantic, predictable admin interface over a strict API. The admin stays a thin, stateless proxy while the API remains the authority, which keeps the whole system a clean substrate for automation and LLM-driven workflows.

This is a work-in-progress project (v0.3.0). The roadmap is deliberately loose, will grow, and the order can change based on what proves useful. Nothing here is a promise.

## Recently shipped

- Login-protected, server-rendered create, edit, and delete management
- A stateless cookie-to-bearer proxy: the API stays the auth authority
- CSRF protection on state-changing forms with a synchronizer token
- Previous and next page navigation that preserves the active sort and filter
- Safe links: only http, https, mailto, and site-relative URLs become clickable, anything else renders as inert text
- Semantic, accessible markup with client and server side validation

## Planned

- More entity views as the vocabulary grows
- An accessibility pass over forms and tables

## Considering

- A framework-based variant of this server
- A configurable page size

Have a need or an idea? Open an issue. This is built in public and feedback shapes the order.
