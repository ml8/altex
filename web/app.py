"""Flask service exposing the altex pipeline as an HTTP API.

Routes
------
    GET  /                  — serve the frontend
    GET  /healthz           — health check for K8s probes
    POST /api/tag           — upload .tex + .pdf, run pipeline, return summary
    GET  /api/download/<id> — download a tagged PDF (local storage mode only)

Storage modes (ALTEX_STORAGE env var):
    local  — (default) store tagged PDF on filesystem, return download URL
    inline — return PDF as base64 in the JSON response (stateless, for K8s)

The /api/tag endpoint returns a JSON summary that includes:
- Structure element counts and alt-text coverage
- verapdf PDF/UA-1 validation results (before and after tagging)
- Rules fixed by altex and any remaining failures
"""

from __future__ import annotations

import base64
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pikepdf
from flask import Flask, jsonify, request, send_file

from altex.latex_parser import extract_title, parse
from altex.pdf_tagger import tag
from altex.verapdf import validate as validate_pdfua

app = Flask(__name__, static_folder="static", static_url_path="")

# Storage mode: "local" (filesystem + download URL) or "inline" (base64).
_STORAGE = os.environ.get("ALTEX_STORAGE", "local")

# Tagged PDFs are stored here in "local" mode until downloaded.
_RESULTS_DIR = Path(tempfile.mkdtemp(prefix="altex_")) if _STORAGE == "local" else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/healthz")
def healthz():
    """Health check for Kubernetes liveness/readiness probes."""
    return jsonify(status="ok")


@app.route("/api/tag", methods=["POST"])
def api_tag():
    tex_file = request.files.get("tex")
    pdf_file = request.files.get("pdf")
    if not tex_file or not pdf_file:
        return jsonify(error="Both .tex and .pdf files are required."), 400

    lang = request.form.get("lang", "en")
    # Fix encoding is on by default (matches CLI behavior).
    fix_encoding = request.form.get("fix_encoding", "true") != "false"
    math_speech = request.form.get("math_speech", "none")
    embed_alt = request.form.get("embed_alt") == "true"

    work = Path(tempfile.mkdtemp(prefix="altex_job_"))
    try:
        tex_path = work / tex_file.filename
        pdf_path = work / pdf_file.filename
        tex_file.save(tex_path)
        pdf_file.save(pdf_path)

        # Run verapdf on the ORIGINAL PDF (before tagging).
        validation_before = validate_pdfua(pdf_path)

        # Optional Ghostscript encoding fix (on by default).
        if fix_encoding:
            try:
                from altex.encoding_fixer import fix_encoding as gs_fix
                gs_out = work / "gs_encoded.pdf"
                gs_fix(pdf_path, gs_out)
                pdf_path = gs_out
            except Exception:
                pass  # Graceful fallback if gs not available.

        # Run the pipeline.
        tree = parse(tex_path)
        title = extract_title(tex_path) or tex_path.stem

        # Generate alt HTML from raw tree (before speech conversion).
        alt_html = None
        if embed_alt:
            from altex.alt_document import generate_alt_html
            alt_html = generate_alt_html(tree, title)

        # Optional math-to-speech conversion.
        if math_speech != "none":
            from altex.math_speech import latex_to_speech
            from altex.models import Tag

            formula_nodes = tree.collect_by_tag(Tag.FORMULA)
            if formula_nodes:
                speeches = latex_to_speech(
                    [n.text for n in formula_nodes], engine=math_speech
                )
                for node, speech in zip(formula_nodes, speeches):
                    node.text = speech

        # Write tagged PDF.
        out_path = work / "tagged.pdf"
        tag(pdf_path, tree, out_path, lang=lang, title=title)

        # Embed alternative HTML.
        if alt_html:
            from altex.alt_document import embed_alt_document
            embed_alt_document(out_path, alt_html, out_path)

        # Run verapdf on the TAGGED PDF (after tagging).
        validation_after = validate_pdfua(out_path)

        summary = _summarize(out_path, tree)
        summary["validation_before"] = validation_before
        summary["validation_after"] = validation_after

        if _STORAGE == "inline":
            # Stateless: return PDF as base64 in JSON response.
            pdf_bytes = out_path.read_bytes()
            summary["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")
            summary["storage"] = "inline"
        else:
            # Local: store on filesystem, return download URL.
            result_id = uuid.uuid4().hex[:12]
            final_path = _RESULTS_DIR / f"{result_id}.pdf"
            shutil.copy2(out_path, final_path)
            summary["id"] = result_id
            summary["download_url"] = f"/api/download/{result_id}"
            summary["storage"] = "local"

        return jsonify(summary)

    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        shutil.rmtree(work, ignore_errors=True)


@app.route("/api/download/<result_id>")
def api_download(result_id: str):
    """Download a tagged PDF (local storage mode only)."""
    if _STORAGE != "local" or _RESULTS_DIR is None:
        return jsonify(error="Download not available in inline storage mode."), 404
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

    has_alt_doc = "accessible_alt.html" in pdf.attachments

    return {
        "title": title,
        "lang": str(pdf.Root.get("/Lang", "")),
        "pages": len(pdf.pages),
        "elements": elements,
        "alt_count": alt_count,
        "bdc_markers_page1": bdc_count,
        "marked": True,
        "alt_document": has_alt_doc,
    }


# ---------------------------------------------------------------------------
# verapdf validation
# ---------------------------------------------------------------------------

