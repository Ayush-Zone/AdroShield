from pathlib import Path
import shutil
import uuid

from flask import Flask, request, render_template_string, send_from_directory
from werkzeug.utils import secure_filename

from photo_integrity import PhotoIntegrityDetector
from document_tampering import DocumentTamperingDetector


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
}

ALLOWED_DOCUMENT_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | {
    ".pdf",
}

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024


# ============================================================
# LOAD DETECTORS ONCE
# ============================================================

print("=" * 70)
print("Loading Photo Integrity Detector...")
print("=" * 70)

photo_detector = PhotoIntegrityDetector()

print("Photo Integrity Detector ready.")

print("=" * 70)
print("Loading Document Tampering Detector...")
print("=" * 70)

document_detector = DocumentTamperingDetector()

print("Document Tampering Detector ready.")

print("=" * 70)


# ============================================================
# HELPERS
# ============================================================

def allowed_image(filename):
    return Path(filename).suffix.lower() in ALLOWED_IMAGE_EXTENSIONS


def allowed_document(filename):
    return Path(filename).suffix.lower() in ALLOWED_DOCUMENT_EXTENSIONS


def clean_value(value):
    """
    Convert detector output values into values safe for HTML.
    """
    if value is None:
        return ""

    if isinstance(value, float):
        return round(value, 6)

    if isinstance(value, dict):
        return {
            str(k): clean_value(v)
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [clean_value(v) for v in value]

    if isinstance(value, tuple):
        return [clean_value(v) for v in value]

    return value


def percent(value):
    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return str(value)


def risk_value(value):
    try:
        number = float(value)

        if number <= 1:
            number *= 100

        return f"{number:.2f}%"
    except Exception:
        return str(value)


def save_uploaded_file(file, folder):
    original_name = secure_filename(file.filename)

    unique_name = (
        uuid.uuid4().hex[:10]
        + "_"
        + original_name
    )

    destination = folder / unique_name
    file.save(destination)

    return destination


def copy_annotation_files(result, job_output_dir):
    """
    Copy detector-generated annotated files into our output directory
    and return web-accessible relative paths.
    """

    web_files = []

    for annotated_file in result.get("annotated_files", []):

        if not annotated_file:
            continue

        source = Path(annotated_file)

        if not source.exists():
            continue

        destination = job_output_dir / source.name

        try:
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
        except Exception:
            try:
                shutil.copy2(source, destination)
            except Exception:
                continue

        web_files.append(
            "/output/"
            + job_output_dir.name
            + "/"
            + destination.name
        )

    return web_files


# ============================================================
# HTML
# ============================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>

<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Media Integrity Analyzer</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #ffffff;
    color: #171717;
    font-family:
        Inter,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Roboto,
        Arial,
        sans-serif;
}

.container {
    width: min(1180px, calc(100% - 40px));
    margin: 0 auto;
}

header {
    padding: 42px 0 28px;
    border-bottom: 1px solid #eeeeee;
}

.brand {
    font-size: 25px;
    font-weight: 700;
    letter-spacing: -0.6px;
}

.subtitle {
    margin-top: 7px;
    color: #777777;
    font-size: 14px;
}

.detector-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 22px;
    margin: 30px 0 50px;
}

.detector-card {
    border: 1px solid #e7e7e7;
    border-radius: 16px;
    padding: 25px;
    background: #ffffff;
    box-shadow: 0 4px 18px rgba(0,0,0,0.035);
}

.detector-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: #f3f3f3;
    color: #444444;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 15px;
}

.detector-card h2 {
    margin: 0;
    font-size: 21px;
    letter-spacing: -0.35px;
}

.detector-description {
    margin: 9px 0 22px;
    color: #777777;
    line-height: 1.55;
    font-size: 14px;
}

.upload-box {
    border: 1px dashed #cfcfcf;
    border-radius: 12px;
    padding: 23px;
    background: #fafafa;
}

input[type="file"] {
    width: 100%;
    font-size: 13px;
}

.file-note {
    margin-top: 9px;
    color: #999999;
    font-size: 12px;
}

.analyze-button {
    width: 100%;
    margin-top: 18px;
    border: 0;
    border-radius: 10px;
    padding: 13px 18px;
    background: #111111;
    color: #ffffff;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: 0.15s ease;
}

.analyze-button:hover {
    background: #303030;
}

.analyze-button:disabled {
    opacity: 0.55;
    cursor: wait;
}

.results {
    margin-bottom: 60px;
}

.results-title {
    font-size: 22px;
    margin-bottom: 18px;
    letter-spacing: -0.3px;
}

.result-card {
    border: 1px solid #e8e8e8;
    border-radius: 15px;
    margin-bottom: 18px;
    overflow: hidden;
}

.result-header {
    padding: 18px 20px;
    background: #fafafa;
    border-bottom: 1px solid #eeeeee;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
}

.result-filename {
    font-weight: 650;
    word-break: break-all;
}

.badge {
    display: inline-flex;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
}

.badge-real {
    background: #edf8f0;
    color: #21733a;
}

.badge-ai {
    background: #fff0f0;
    color: #b52d2d;
}

.badge-safe {
    background: #edf8f0;
    color: #21733a;
}

.badge-risk {
    background: #fff0f0;
    color: #b52d2d;
}

.result-body {
    padding: 20px;
}

.metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
}

.metric {
    border: 1px solid #eeeeee;
    border-radius: 10px;
    padding: 13px;
}

.metric-label {
    color: #888888;
    font-size: 11px;
    margin-bottom: 6px;
}

.metric-value {
    font-size: 17px;
    font-weight: 700;
}

.flags {
    margin-top: 20px;
}

.flag {
    border: 1px solid #eeeeee;
    border-radius: 10px;
    padding: 14px;
    margin-top: 9px;
}

.flag-top {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 7px;
}

.severity {
    font-size: 10px;
    text-transform: uppercase;
    font-weight: 800;
    padding: 4px 7px;
    border-radius: 5px;
    background: #f3f3f3;
}

.flag-field {
    font-weight: 650;
    font-size: 13px;
}

.flag-details {
    color: #777777;
    font-size: 12px;
    line-height: 1.55;
}

.annotation-section {
    margin-top: 22px;
}

.annotation-section h3 {
    font-size: 14px;
    margin-bottom: 12px;
}

.annotation-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.annotation-image {
    width: 100%;
    display: block;
    border: 1px solid #e7e7e7;
    border-radius: 10px;
    background: #f8f8f8;
}

.empty {
    padding: 22px;
    border: 1px dashed #dddddd;
    border-radius: 12px;
    color: #888888;
    text-align: center;
}

.error {
    border: 1px solid #f0d0d0;
    background: #fff7f7;
    color: #a32c2c;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 15px;
}

footer {
    border-top: 1px solid #eeeeee;
    padding: 25px 0 35px;
    color: #999999;
    font-size: 12px;
}

@media (max-width: 800px) {

    .detector-grid {
        grid-template-columns: 1fr;
    }

    .metrics {
        grid-template-columns: repeat(2, 1fr);
    }

    .annotation-grid {
        grid-template-columns: 1fr;
    }

    .result-header {
        align-items: flex-start;
        flex-direction: column;
    }
}

</style>

</head>

<body>

<div class="container">

<header>
    <div class="brand">Media Integrity Analyzer</div>
    <div class="subtitle">
        Deepfake detection and document tampering analysis
    </div>
</header>


<div class="detector-grid">


    <!-- ================================================= -->
    <!-- DEEPFAKE DETECTOR -->
    <!-- ================================================= -->

    <section class="detector-card">

        <div class="detector-number">1</div>

        <h2>Deepfake / AI Image Detection</h2>

        <div class="detector-description">
            Analyze one or more images for AI-generated or manipulated
            visual content using the photo integrity detector.
        </div>

        <form
            method="POST"
            action="/analyze/deepfake"
            enctype="multipart/form-data"
            onsubmit="startLoading(this)"
        >

            <div class="upload-box">

                <input
                    type="file"
                    name="files"
                    multiple
                    accept="image/*"
                    required
                >

                <div class="file-note">
                    JPG, JPEG, PNG, WEBP, BMP or TIFF
                </div>

            </div>

            <button
                class="analyze-button"
                type="submit"
            >
                Analyze Images
            </button>

        </form>

    </section>


    <!-- ================================================= -->
    <!-- DOCUMENT TAMPERING DETECTOR -->
    <!-- ================================================= -->

    <section class="detector-card">

        <div class="detector-number">2</div>

        <h2>Document Tampering Detection</h2>

        <div class="detector-description">
            Analyze documents and images for suspicious modifications,
            generate findings and display detector-generated annotations.
        </div>

        <form
            method="POST"
            action="/analyze/document"
            enctype="multipart/form-data"
            onsubmit="startLoading(this)"
        >

            <div class="upload-box">

                <input
                    type="file"
                    name="files"
                    multiple
                    accept=".pdf,.jpg,.jpeg,.png,.bmp,.tiff,.tif"
                    required
                >

                <div class="file-note">
                    PDF, JPG, JPEG, PNG, BMP, TIFF or TIF
                </div>

            </div>

            <button
                class="analyze-button"
                type="submit"
            >
                Analyze Documents
            </button>

        </form>

    </section>

</div>


{% if errors %}

<div class="results">

    <div class="results-title">Errors</div>

    {% for error in errors %}
        <div class="error">
            {{ error }}
        </div>
    {% endfor %}

</div>

{% endif %}


{% if deepfake_results %}

<div class="results">

    <div class="results-title">
        Deepfake Analysis Results
    </div>


    {% for item in deepfake_results %}

    <div class="result-card">

        <div class="result-header">

            <div class="result-filename">
                {{ item.filename }}
            </div>

            {% if item.decision|lower in ["real", "authentic", "original"] %}

                <div class="badge badge-real">
                    {{ item.decision }}
                </div>

            {% else %}

                <div class="badge badge-ai">
                    {{ item.decision }}
                </div>

            {% endif %}

        </div>


        <div class="result-body">

            <div class="metrics">

                <div class="metric">
                    <div class="metric-label">
                        Average AI Score
                    </div>

                    <div class="metric-value">
                        {{ item.average_ai_score }}
                    </div>
                </div>


                <div class="metric">
                    <div class="metric-label">
                        Maximum AI Score
                    </div>

                    <div class="metric-value">
                        {{ item.maximum_ai_score }}
                    </div>
                </div>


                <div class="metric">
                    <div class="metric-label">
                        Top 10% Average
                    </div>

                    <div class="metric-value">
                        {{ item.top_10_average }}
                    </div>
                </div>


                <div class="metric">
                    <div class="metric-label">
                        Suspicious Tiles
                    </div>

                    <div class="metric-value">
                        {{ item.suspicious_tile_count }}
                    </div>
                </div>

            </div>


            {% if item.top_regions %}

            <div class="flags">

                <strong style="font-size:14px;">
                    Top Suspicious Regions
                </strong>

                {% for region in item.top_regions %}

                <div class="flag">

                    <div class="flag-top">

                        <span class="severity">
                            AI {{ region.score }}
                        </span>

                        <span class="flag-field">
                            X={{ region.x }},
                            Y={{ region.y }}
                        </span>

                    </div>

                </div>

                {% endfor %}

            </div>

            {% endif %}

        </div>

    </div>

    {% endfor %}

</div>

{% endif %}


{% if document_results %}

<div class="results">

    <div class="results-title">
        Document Tampering Results
    </div>


    {% for item in document_results %}

    <div class="result-card">

        <div class="result-header">

            <div class="result-filename">
                {{ item.filename }}
            </div>

            {% if item.is_safe %}

                <div class="badge badge-safe">
                    {{ item.verdict }}
                </div>

            {% else %}

                <div class="badge badge-risk">
                    {{ item.verdict }}
                </div>

            {% endif %}

        </div>


        <div class="result-body">

            <div class="metrics">

                <div class="metric">
                    <div class="metric-label">
                        Risk Score
                    </div>

                    <div class="metric-value">
                        {{ item.risk_score }}
                    </div>
                </div>


                <div class="metric">
                    <div class="metric-label">
                        Flags
                    </div>

                    <div class="metric-value">
                        {{ item.flag_count }}
                    </div>
                </div>

            </div>


            {% if item.flags %}

            <div class="flags">

                <strong style="font-size:14px;">
                    Suspicious Findings
                </strong>


                {% for flag in item.flags %}

                <div class="flag">

                    <div class="flag-top">

                        <span class="severity">
                            {{ flag.severity }}
                        </span>

                        <span class="flag-field">
                            {{ flag.field }}
                        </span>

                    </div>


                    <div class="flag-details">

                        <strong>Page:</strong>
                        {{ flag.page }}

                        {% if flag.check %}
                        &nbsp; · &nbsp;
                        <strong>Check:</strong>
                        {{ flag.check }}
                        {% endif %}

                        <br>

                        <strong>Reason:</strong>
                        {{ flag.reason }}

                        {% if flag.bbox %}
                        <br>
                        <strong>Bounding Box:</strong>
                        {{ flag.bbox }}
                        {% endif %}

                    </div>

                </div>

                {% endfor %}

            </div>

            {% else %}

            <div class="empty" style="margin-top:20px;">
                No suspicious findings detected.
            </div>

            {% endif %}


            {% if item.annotations %}

            <div class="annotation-section">

                <h3>
                    Annotated Images
                </h3>

                <div class="annotation-grid">

                    {% for image in item.annotations %}

                        <a href="{{ image }}" target="_blank">

                            <img
                                class="annotation-image"
                                src="{{ image }}"
                                alt="Annotated document"
                            >

                        </a>

                    {% endfor %}

                </div>

            </div>

            {% endif %}

        </div>

    </div>

    {% endfor %}

</div>

{% endif %}


<footer>
    Media Integrity Analyzer
</footer>

</div>


<script>

function startLoading(form) {

    const button = form.querySelector(".analyze-button");

    if (button) {
        button.disabled = true;
        button.innerText = "Analyzing...";
    }

}

</script>

</body>
</html>
"""


# ============================================================
# INDEX
# ============================================================

@app.route("/", methods=["GET"])
def index():

    return render_template_string(
        HTML,
        deepfake_results=None,
        document_results=None,
        errors=None,
    )


# ============================================================
# DEEPFAKE ANALYSIS
# ============================================================

@app.route("/analyze/deepfake", methods=["POST"])
def analyze_deepfake():

    files = request.files.getlist("files")

    results = []
    errors = []

    if not files or all(not f.filename for f in files):
        errors.append("Please select at least one image.")

        return render_template_string(
            HTML,
            deepfake_results=None,
            document_results=None,
            errors=errors,
        )

    for file in files:

        if not file.filename:
            continue

        if not allowed_image(file.filename):

            errors.append(
                f"{file.filename}: unsupported image format."
            )

            continue

        image_path = None

        try:

            image_path = save_uploaded_file(
                file,
                UPLOAD_DIR
            )

            result = photo_detector.analyze(
                str(image_path)
            )

            result = clean_value(result)

            results.append(
                {
                    "filename": file.filename,

                    "decision": result.get(
                        "decision",
                        "Unknown"
                    ),

                    "average_ai_score": percent(
                        result.get(
                            "average_ai_score",
                            0
                        )
                    ),

                    "maximum_ai_score": percent(
                        result.get(
                            "maximum_ai_score",
                            0
                        )
                    ),

                    "top_10_average": percent(
                        result.get(
                            "top_10_average",
                            0
                        )
                    ),

                    "suspicious_tile_count": result.get(
                        "suspicious_tile_count",
                        0
                    ),

                    "top_regions": [
                        {
                            "x": region.get("x", 0),
                            "y": region.get("y", 0),
                            "score": percent(
                                region.get(
                                    "score",
                                    0
                                )
                            ),
                        }
                        for region in result.get(
                            "top_suspicious_regions",
                            []
                        )
                    ],
                }
            )

        except Exception as error:

            errors.append(
                f"{file.filename}: {str(error)}"
            )

        finally:

            if image_path and image_path.exists():

                try:
                    image_path.unlink()
                except Exception:
                    pass

    return render_template_string(
        HTML,
        deepfake_results=results,
        document_results=None,
        errors=errors,
    )


# ============================================================
# DOCUMENT TAMPERING ANALYSIS
# ============================================================

@app.route("/analyze/document", methods=["POST"])
def analyze_document():

    files = request.files.getlist("files")

    results = []
    errors = []

    if not files or all(not f.filename for f in files):

        errors.append(
            "Please select at least one document."
        )

        return render_template_string(
            HTML,
            deepfake_results=None,
            document_results=None,
            errors=errors,
        )

    job_id = uuid.uuid4().hex

    job_output_dir = OUTPUT_DIR / job_id

    job_output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    for file in files:

        if not file.filename:
            continue

        if not allowed_document(file.filename):

            errors.append(
                f"{file.filename}: unsupported document format."
            )

            continue

        document_path = None

        try:

            document_path = save_uploaded_file(
                file,
                UPLOAD_DIR
            )

            result = document_detector.analyze(
                str(document_path),

                save_annotation=True,

                save_report=True,

                print_output=False,
            )

            result = clean_value(result)

            annotation_urls = copy_annotation_files(
                result,
                job_output_dir
            )

            flags = []

            for flag in result.get("flags", []):

                flags.append(
                    {
                        "severity": flag.get(
                            "severity",
                            ""
                        ),

                        "page": flag.get(
                            "page",
                            ""
                        ),

                        "field": flag.get(
                            "field",
                            ""
                        ),

                        "check": flag.get(
                            "check",
                            ""
                        ),

                        "reason": flag.get(
                            "reason",
                            ""
                        ),

                        "bbox": flag.get(
                            "bbox",
                            ""
                        ),
                    }
                )

            verdict = result.get(
                "verdict",
                "Unknown"
            )

            results.append(
                {
                    "filename": file.filename,

                    "verdict": verdict,

                    "risk_score": risk_value(
                        result.get(
                            "risk_score",
                            0
                        )
                    ),

                    "flag_count": len(flags),

                    "flags": flags,

                    "annotations": annotation_urls,

                    "is_safe": (
                        len(flags) == 0
                    ),
                }
            )

        except Exception as error:

            errors.append(
                f"{file.filename}: {str(error)}"
            )

        finally:

            if document_path and document_path.exists():

                try:
                    document_path.unlink()
                except Exception:
                    pass

    return render_template_string(
        HTML,
        deepfake_results=None,
        document_results=results,
        errors=errors,
    )


# ============================================================
# SERVE ANNOTATED OUTPUT FILES
# ============================================================

@app.route("/output/<job_id>/<filename>")
def serve_output(job_id, filename):

    safe_job_id = secure_filename(job_id)
    safe_filename = secure_filename(filename)

    directory = OUTPUT_DIR / safe_job_id

    return send_from_directory(
        directory,
        safe_filename
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def file_too_large(error):

    return render_template_string(
        HTML,
        deepfake_results=None,
        document_results=None,
        errors=[
            "The uploaded files are too large. Maximum total upload size is 200 MB."
        ],
    ), 413


@app.errorhandler(Exception)
def application_error(error):

    return render_template_string(
        HTML,
        deepfake_results=None,
        document_results=None,
        errors=[
            f"Application error: {str(error)}"
        ],
    ), 500


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("MEDIA INTEGRITY ANALYZER")
    print("=" * 70)
    print("Open: http://127.0.0.1:5000")
    print("=" * 70)
    print()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )