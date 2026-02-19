"""Flask service exposing the altex pipeline as an HTTP API.

Routes
------
    GET  /                  — serve the frontend
    POST /api/tag           — upload .tex + .pdf, run pipeline, return summary
    GET  /api/download/<id> — download a tagged PDF
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

import pikepdf
from flask import Flask, jsonify, request, send_file

from altex.latex_parser import extract_title, parse
from altex.pdf_tagger import tag

app = Flask(__name__, static_folder="static", static_url_path="")

# Tagged PDFs are stored here until downloaded.
_RESULTS_DIR = Path(tempfile.mkdtemp(prefix="altex_"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/tag", methods=["POST"])
def api_tag():
    tex_file = request.files.get("tex")
    pdf_file = request.files.get("pdf")
    if not tex_file or not pdf_file:
        return jsonify(error="Both .tex and .pdf files are required."), 400

    lang = request.form.get("lang", "en")
    fix_encoding = request.form.get("fix_encoding") == "true"

    work = Path(tempfile.mkdtemp(prefix="altex_job_"))
    try:
        tex_path = work / tex_file.filename
        pdf_path = work / pdf_file.filename
        tex_file.save(tex_path)
        pdf_file.save(pdf_path)

        # Optional Ghostscript encoding fix.
        if fix_encoding:
            from altex.encoding_fixer import fix_encoding as gs_fix

            gs_out = work / "gs_encoded.pdf"
            gs_fix(pdf_path, gs_out)
            pdf_path = gs_out

        # Run the pipeline.
        tree = parse(tex_path)
        title = extract_title(tex_path) or tex_path.stem
        result_id = uuid.uuid4().hex[:12]
        out_path = _RESULTS_DIR / f"{result_id}.pdf"
        tag(pdf_path, tree, out_path, lang=lang, title=title)

        summary = _summarize(out_path, tree)
        summary["id"] = result_id
        summary["download_url"] = f"/api/download/{result_id}"
        return jsonify(summary)

    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        shutil.rmtree(work, ignore_errors=True)


@app.route("/api/download/<result_id>")
def api_download(result_id: str):
    path = _RESULTS_DIR / f"{result_id}.pdf"
    if not path.is_file():
        return jsonify(error="Result not found or expired."), 404
    return send_file(path, mimetype="application/pdf", as_attachment=True,
                     download_name="tagged.pdf")


# ---------------------------------------------------------------------------
# Summary extraction
# ---------------------------------------------------------------------------


def _summarize(pdf_path: Path, tree) -> dict:
    """Build an accessibility summary from the tagged PDF."""
    pdf = pikepdf.open(pdf_path)

    elements: dict[str, int] = {}
    alt_count = 0

    def walk(elem):
        nonlocal alt_count
        if not isinstance(elem, pikepdf.Dictionary):
            return
        if "/S" in elem:
            s = str(elem["/S"]).lstrip("/")
            elements[s] = elements.get(s, 0) + 1
        if "/Alt" in elem:
            alt_count += 1
        kids = elem.get("/K")
        if isinstance(kids, pikepdf.Array):
            for i in range(len(kids)):
                walk(kids[i])

    walk(pdf.Root["/StructTreeRoot"]["/K"])
    elements.pop("Document", None)

    ops = pikepdf.parse_content_stream(pdf.pages[0])
    bdc_count = sum(1 for op in ops if str(op.operator) == "BDC")

    with pdf.open_metadata() as meta:
        title = meta.get("dc:title", pdf_path.stem)

    return {
        "title": title,
        "lang": str(pdf.Root.get("/Lang", "")),
        "pages": len(pdf.pages),
        "elements": elements,
        "alt_count": alt_count,
        "bdc_markers_page1": bdc_count,
        "marked": True,
    }
