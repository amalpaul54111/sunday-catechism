### Sunday Catechism

A frappe app to manage Sunday School Operations

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app sunday_catechism
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/sunday_catechism
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### Import records from a photo (OCR)

Photograph a form or a register/table and create records from it. Any doctype
you enable gets a **📷 Import from Photo** button on its list view: attach the
image and review the extracted fields before saving. One form creates one
record; a register table offers a bulk-create list. Low-confidence reads are
flagged for review — OCR is never 100%, so always check the data.

#### Configuring which doctypes get OCR

In **OCR Settings → Enabled DocTypes**, add each doctype you want OCR on (e.g.
`Student`). All OCR-eligible fields of that doctype are read automatically —
the field list is derived from the doctype's meta, skipping read-only/computed
fields (like `full_name`), Link fields (like `class`), checkboxes, and layout
fields. Add a field to the doctype later and it is picked up with no code change.

#### Choosing the engine

The engine is chosen in **OCR Settings** (run `bench --site <site> migrate`
first so the doctypes are created):

- **Ollama** (default, recommended) — a local vision model (`qwen2.5vl:3b`)
  that handles handwriting and table layouts and returns structured fields.
  Runs as a separate container. 100% local, no cloud.
- **Tesseract** — a lightweight classic OCR engine and the recommended
  fallback on Python 3.14. `pytesseract` is a pure-Python wrapper (no compiled
  wheel) so it installs anywhere; it needs the native binary:

  ```bash
  ./env/bin/pip install pytesseract
  brew install tesseract          # or: apt install tesseract-ocr
  ```

  Set the language in OCR Settings (`eng` by default; install the matching
  `tesseract-ocr-<lang>` data pack for others).
- **PaddleOCR** — another classic engine, slightly stronger than Tesseract on
  some layouts, but **paddlepaddle has no wheels for Python 3.14**. Only usable
  on older Python: `pip install paddlepaddle paddleocr`.

Tesseract and PaddleOCR have no layout understanding — they recognise text and
map it to fields by matching your field labels, flagging every guess for review
and always returning the full recognised text. Use Ollama for handwriting.

#### Setting up Ollama

This app ships a compose overlay that adds an `ollama` service. Merge it on top
of frappe_docker's `compose.yaml`:

```bash
docker compose \
  -f compose.yaml \
  -f apps/sunday_catechism/docs/compose.ollama.yaml \
  up -d
```

Then pull the model once (≈3 GB):

```bash
docker compose exec ollama ollama pull qwen2.5vl:3b
```

`OCR Settings → Ollama URL` defaults to `http://ollama:11434`. For a local dev
bench (not the compose stack), install Ollama on the host, run
`ollama pull qwen2.5vl:3b`, and set the URL to `http://host.docker.internal:11434`
(or `http://localhost:11434`).

On CPU expect ~20–40s per image. For better accuracy on messy handwriting,
change the model to `qwen2.5vl:7b` in OCR Settings (slower, more RAM). A GPU
opt-in is documented in `docs/compose.ollama.yaml`.

### License

mit
