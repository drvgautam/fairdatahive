# Third-Party Notices

FairDataHive depends on open-source software. This file highlights components that affect redistribution or runtime behavior.

## Application dependencies

See `requirements.txt` and `frontend/package.json` for full dependency lists. Major components include:

- **FastAPI** — MIT License
- **SQLAlchemy** — MIT License
- **PostgreSQL / pgvector** — PostgreSQL License / open-source extensions
- **MinIO** — GNU AGPL v3 (server); client libraries used here have their own licenses
- **React / Vite** — MIT License
- **rdflib** — BSD-3-Clause
- **pyshacl** — Apache-2.0

## Semantic embedding model

Semantic search uses [sentence-transformers](https://github.com/UKPLab/sentence-transformers) (Apache-2.0) with the Hugging Face model **`multi-qa-mpnet-base-dot-v1`**.

- The model is **downloaded at runtime** on first use (not vendored in this repository).
- Review the model card and license on Hugging Face before production use:  
  https://huggingface.co/sentence-transformers/multi-qa-mpnet-base-dot-v1
- Cached weights are typically stored under `~/.cache/huggingface/` (excluded via `.gitignore`).

## Vocabulary and RDF IRIs

Default RDF namespace prefixes use `https://fairdatahive.io/vocab#`. Deployments may override `BASE_URL` and related configuration; the placeholder domain does not imply an external service dependency.

## DCAT and standards

DCAT 3, Dublin Core, and related W3C vocabularies are used as linked-data standards; see W3C license terms for specification documents.
