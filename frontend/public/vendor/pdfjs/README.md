# PDF.js 5.6.205

Vendored browser build from the Codex bundled `pdfjs-dist` runtime (26.1015.12040).
Upstream: https://github.com/mozilla/pdf.js . License: Apache-2.0 (see LICENSE).

The application serves this module, worker, CMaps, standard fonts, ICC profiles and
WASM assets locally. Customer document bytes enter the worker from the authenticated
PPAP request client. No customer document is sent to an external preview service.

These assets are copied unchanged from pdfjs-dist. Upgrade all assets together.
