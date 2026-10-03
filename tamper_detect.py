"""
Document Tampering Detector (PDF + images)

Pipeline
  1. Metadata checks      (PDF info/xref history, image EXIF)
  2. Font checks          (PDF text layer: mixed fonts inside a word, odd numeric fonts)
  3. OCR                  (pytesseract word boxes)
  4. Layout checks        (digit height outliers, low-confidence numbers)
  5. Pixel forensics      (Error Level Analysis per word box, image input only)
  6. Text-layer vs OCR    (hidden / overlaid text in PDFs)
  7. Rule checks          (invalid/future dates, bad amount formatting,
                           O/0 l/1 substitutions, totals that don't add up)

Every finding is a "flag": field text, reason, severity, location.
Output: console report, <file>_tamper_report.json, <file>_annotated.png

Install:  pip install pytesseract pillow numpy pymupdf
"""
import io
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
from PIL import ExifTags, Image, ImageChops, ImageDraw, ImageFont
from pytesseract import Output
import pytesseract

try:
    import pymupdf as fitz  # PyMuPDF (new name)
except ImportError:
    try:
        import fitz  # older PyMuPDF versions
    except ImportError:
        fitz = None

WIN_TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(WIN_TESS):
    pytesseract.pytesseract.tesseract_cmd = WIN_TESS

PDF_DPI = 200
SEV_WEIGHT = {"low": 1, "medium": 3, "high": 6}
EDIT_TOOLS = ["photoshop", "gimp", "canva", "illustrator", "paint", "pixlr", "snapseed",
              "picsart", "lightroom", "foxit phantom", "pdfescape", "sejda", "smallpdf",
              "ilovepdf", "pdf-xchange", "nitro", "acrobat pro", "inkscape", "affinity"]

flags = []


def flag(field, reason, severity="medium", bbox=None, page=1, check="rule"):
    flags.append({"page": page, "field": field, "reason": reason,
                  "severity": severity, "check": check, "bbox": bbox,
                  "marker": "yellow" if check == "font" else "red"})  # yellow = font change, red = suspicious text/value


# --------------------------------------------------------------------------- helpers
NUM_RE = re.compile(r"[$₹€£]?\d[\d,\.]*%?")
AMOUNT_RE = re.compile(r"(?<![\w.])(?:[$₹€£]|Rs\.?\s?)?(\d[\d,]*(?:\.\d+)?)(?![\w])")
MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
DATE_PATTERNS = [
    ("dmy", re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")),
    ("ymd", re.compile(r"\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b")),
    ("dMy", re.compile(rf"\b(\d{{1,2}})\s+({MONTHS})[a-z]*\.?,?\s+(\d{{2,4}})\b", re.I)),
]


def clean(t):
    """strip surrounding punctuation so '560037,' or '(18%)' are judged as numbers"""
    return t.strip(".,;:()[]|")


def is_numeric(t):
    return bool(NUM_RE.fullmatch(clean(t)))


def is_money(t):
    c = clean(t)
    return is_numeric(c) and ("," in c or "." in c) and len(c) >= 4


def to_float(s):
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def union_box(words):
    x1 = min(w["x"] for w in words)
    y1 = min(w["y"] for w in words)
    x2 = max(w["x"] + w["w"] for w in words)
    y2 = max(w["y"] + w["h"] for w in words)
    return [x1, y1, x2 - x1, y2 - y1]


def robust_z(values):
    v = np.asarray(values, dtype=float)
    med = np.median(v)
    mad = np.median(np.abs(v - med)) or 1e-6
    return 0.6745 * (v - med) / mad, med


def parse_pdf_date(s):
    m = re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", s or "")
    if not m:
        return None
    parts = [int(g) if g else d for g, d in zip(m.groups(), (0, 1, 1, 0, 0, 0))]
    try:
        return datetime(*parts)
    except ValueError:
        return None


# --------------------------------------------------------------------------- 1. metadata
def check_pdf_metadata(path, doc):
    meta = doc.metadata or {}
    producer = (meta.get("producer") or "") + " " + (meta.get("creator") or "")
    for tool in EDIT_TOOLS:
        if tool in producer.lower():
            flag("PDF metadata", f"Producer/Creator mentions an editing tool: '{producer.strip()}'",
                 "medium", check="metadata")
            break
    created, modified = parse_pdf_date(meta.get("creationDate")), parse_pdf_date(meta.get("modDate"))
    if created and modified and (modified - created).total_seconds() > 60:
        flag("PDF metadata", f"Modified ({modified}) well after creation ({created})",
             "medium", check="metadata")
    if not meta.get("creationDate") and not meta.get("producer"):
        flag("PDF metadata", "Metadata stripped (no creation date or producer)", "low", check="metadata")
    with open(path, "rb") as f:
        raw = f.read()
    eofs = raw.count(b"%%EOF")
    if eofs > 1:
        flag("PDF structure", f"{eofs} %%EOF markers: file was saved incrementally (edited after creation)",
             "medium", check="metadata")
    if re.search(rb"/Type\s*/Annot", raw) and re.search(rb"/Subtype\s*/(Redact|FreeText|Square)", raw):
        flag("PDF structure", "Contains redaction/free-text/shape annotations that can cover content",
             "medium", check="metadata")


def check_image_metadata(img):
    try:
        exif = img.getexif()
    except Exception:
        exif = None
    if not exif:
        if (img.format or "").upper() == "JPEG":
            flag("EXIF", "JPEG has no EXIF data (stripped or re-exported)", "low", check="metadata")
        return
    tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
    software = str(tags.get("Software", ""))
    for tool in EDIT_TOOLS:
        if tool in software.lower():
            flag("EXIF Software", f"Image saved by editing software: '{software}'", "high", check="metadata")
            break
    else:
        if software:
            flag("EXIF Software", f"Software tag present: '{software}'", "low", check="metadata")
    dt, orig = tags.get("DateTime"), tags.get("DateTimeOriginal")
    if dt and orig and dt != orig:
        flag("EXIF dates", f"DateTime ({dt}) differs from DateTimeOriginal ({orig}): modified after capture",
             "medium", check="metadata")


# --------------------------------------------------------------------------- 2. PDF fonts
def font_family(name):
    """'ABCDEF+TimesNewRomanPS-BoldMT' -> 'timesnewroman'; bold/italic/MT/PS suffixes are ignored"""
    n = re.sub(r"^[A-Z]{6}\+", "", name or "")
    prev = None
    while prev != n:
        prev = n
        n = re.sub(r"(?i)[-,_ ]?(bold|italic|oblique|black|semibold|demi|medium|light|regular|roman|mt|ps)$", "", n)
    return n.lower()


def check_pdf_fonts(page, pno, scale):
    d = page.get_text("dict")
    numeric_spans, all_spans = [], []
    for block in d["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            for a, b in zip(spans, spans[1:]):
                # glyphs of one word split across two fonts/sizes
                if (a["text"][-1] not in " \t" and b["text"][0] not in " \t"
                        and (font_family(a["font"]) != font_family(b["font"]) or abs(a["size"] - b["size"]) > 0.5)
                        and (a["text"][-1].isalnum() and b["text"][0].isalnum())
                        and (a["text"][-1].isdigit() or b["text"][0].isdigit())):
                    bb = [int(v * scale) for v in (min(a["bbox"][0], b["bbox"][0]), min(a["bbox"][1], b["bbox"][1]))]
                    bb += [int((max(a["bbox"][2], b["bbox"][2]) * scale)) - bb[0],
                           int((max(a["bbox"][3], b["bbox"][3]) * scale)) - bb[1]]
                    flag(a["text"][-3:] + b["text"][:3],
                         f"One word is rendered in two fonts ({a['font']} {a['size']:.1f}pt / "
                         f"{b['font']} {b['size']:.1f}pt)", "high", bb, pno, "font")
            for s in spans:
                all_spans.append(s)
                if is_numeric(s["text"].strip()):
                    numeric_spans.append(s)
    if len(numeric_spans) >= 5:
        combos = Counter(font_family(s["font"]) for s in numeric_spans)
        total = sum(combos.values())
        for s in numeric_spans:
            key = font_family(s["font"])
            if combos[key] / total <= 0.15:
                bb = [int(v * scale) for v in s["bbox"]]
                bb = [bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]]
                flag(s["text"].strip(),
                     f"Number uses font family '{s['font']}'; {100 * (1 - combos[key] / total):.0f}% "
                     f"of other numbers on the page use a different font family", "medium", bb, pno, "font")
    # any text (not just numbers) set in a font family that almost nothing else on the page uses
    weight = Counter()
    names = {}
    for sp in all_spans:
        fam = font_family(sp["font"])
        weight[fam] += sum(c.isalnum() for c in sp["text"])
        names.setdefault(fam, sp["font"])
    total_chars = sum(weight.values())
    if total_chars >= 40 and len(weight) > 1:
        dom, dom_n = weight.most_common(1)[0]
        if dom_n / total_chars >= 0.5:
            for sp in all_spans:
                txt = sp["text"].strip()
                fam = font_family(sp["font"])
                if (fam != dom and weight[fam] / total_chars <= 0.15
                        and sum(c.isalnum() for c in txt) >= 2 and not is_numeric(txt)):
                    bb = [int(v * scale) for v in sp["bbox"]]
                    bb = [bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]]
                    flag(txt, f"Text set in font '{sp['font']}' while {100 * dom_n / total_chars:.0f}% of the "
                              f"page uses the '{dom}' family (edited or inserted text)", "medium", bb, pno, "font")
    # context rule: judge each text span against the OTHER spans in its own row / column (leave-one-out),
    # so it works even when the page uses many fonts overall.
    found = {}

    def has_text(sp):
        return any(ch.isalnum() for ch in sp["text"])

    def check_group(spans, kind, min_others, frac):
        for sp in spans:
            txt = sp["text"].strip()
            if sum(ch.isalnum() for ch in txt) < 2 or is_numeric(txt):
                continue
            others = [o for o in spans if o is not sp and has_text(o)]
            if len(others) < min_others:
                continue
            fw = Counter(font_family(o["font"]) for o in others)
            ref, n = fw.most_common(1)[0]
            if n / len(others) >= frac and font_family(sp["font"]) != ref:
                found.setdefault(id(sp), (sp, f"the other text in the same {kind} uses the '{ref}' family"))

    def cy(sp):
        return (sp["bbox"][1] + sp["bbox"][3]) / 2

    rows = []
    for sp in sorted(all_spans, key=cy):
        h = sp["bbox"][3] - sp["bbox"][1]
        for r in rows:
            if abs(cy(sp) - r["cy"]) < 0.45 * max(h, r["h"]):
                r["spans"].append(sp)
                break
        else:
            rows.append({"cy": cy(sp), "h": h, "spans": [sp]})
    for r in rows:
        check_group(r["spans"], "row", 2, 0.7)
        texts = sorted([sp for sp in r["spans"] if sum(ch.isalnum() for ch in sp["text"]) >= 2
                        and not is_numeric(sp["text"].strip())], key=lambda t: t["bbox"][0])
        fams = {font_family(sp["font"]) for sp in texts}
        if len(fams) >= 3:  # three or more families on one line: flag everything after the first label
            for sp in texts[1:]:
                found.setdefault(id(sp), (sp, f"this line mixes {len(fams)} different font families"))
    cols = []
    for sp in sorted(all_spans, key=lambda t: t["bbox"][0]):
        for c_ in cols:
            if abs(sp["bbox"][0] - c_["x"]) <= 3:
                c_["spans"].append(sp)
                break
        else:
            cols.append({"x": sp["bbox"][0], "spans": [sp]})
    for c_ in cols:
        check_group(c_["spans"], "column", 3, 0.6)

    done = {tuple(f["bbox"]) for f in flags if f["page"] == pno and f["check"] == "font" and f["bbox"]}
    for sp, why in found.values():
        bb = [int(v * scale) for v in sp["bbox"]]
        bb = [bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]]
        if tuple(bb) in done:
            continue
        flag(sp["text"].strip(), f"Text set in '{sp['font']}' but {why} (edited or inserted text)",
             "medium", bb, pno, "font")
    if len(page.get_fonts()) > 6:
        flag("Fonts", f"{len(page.get_fonts())} distinct fonts embedded on one page", "low",
             page=pno, check="font")


# --------------------------------------------------------------------------- 3. OCR
def run_ocr(img):
    data = pytesseract.image_to_data(img, output_type=Output.DICT)
    words = []
    for i, t in enumerate(data["text"]):
        t = t.strip()
        if not t:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1
        words.append({"text": t, "conf": conf, "x": int(data["left"][i]), "y": int(data["top"][i]),
                      "w": int(data["width"][i]), "h": int(data["height"][i]),
                      "key": (data["block_num"][i], data["par_num"][i], data["line_num"][i])})
    # group by vertical centre (more robust than Tesseract's own line ids when fonts differ)
    out = []
    for w in sorted(words, key=lambda w: w["y"] + w["h"] / 2):
        cy = w["y"] + w["h"] / 2
        for ws in out:
            lcy = np.mean([v["y"] + v["h"] / 2 for v in ws])
            if abs(cy - lcy) < 0.6 * max(w["h"], max(v["h"] for v in ws)):
                ws.append(w)
                break
        else:
            out.append([w])
    for ws in out:
        ws.sort(key=lambda w: w["x"])
    out.sort(key=lambda ws: min(w["y"] for w in ws))
    return words, out


# --------------------------------------------------------------------------- 4. layout
def check_layout(words, pno):
    nums = [w for w in words if is_money(w["text"]) and w["conf"] >= 0]
    if len(nums) >= 8:
        z, med = robust_z([w["h"] for w in nums])
        for w, zi in zip(nums, z):
            if abs(zi) > 4 and abs(w["h"] - med) / med > 0.35:
                flag(w["text"], f"Digit height {w['h']}px vs typical {med:.0f}px for numbers on the page "
                                f"(pasted/retyped value?)", "low", [w["x"], w["y"], w["w"], w["h"]], pno, "layout")
    for w in nums:
        if 0 <= w["conf"] < 40:
            flag(w["text"], f"Low OCR confidence ({w['conf']:.0f}%) on a numeric field "
                            f"(blurred, overwritten or composited)", "low",
                 [w["x"], w["y"], w["w"], w["h"]], pno, "layout")


# --------------------------------------------------------------------------- 5. ELA
def check_ela(img, words, quality=90):
    rgb = img.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    diff = np.asarray(ImageChops.difference(rgb, Image.open(buf).convert("RGB")), dtype=np.float32).mean(axis=2)
    scored = []
    for w in words:
        if w["w"] < 4 or w["h"] < 4:
            continue
        patch = diff[w["y"]:w["y"] + w["h"], w["x"]:w["x"] + w["w"]]
        if patch.size:
            scored.append((w, float(patch.mean())))
    if len(scored) < 8:
        return
    z, med = robust_z([s for _, s in scored])
    fmt = (img.format or "").upper()
    sev = "high"
    for (w, s), zi in zip(scored, z):
        if zi > 5 and s > 2.5 * med:
            flag(w["text"], f"Error-level anomaly: compression error {s:.1f} vs median {med:.1f} "
                            f"(region likely edited/pasted after the original save)", sev,
                 [w["x"], w["y"], w["w"], w["h"]], 1, "ela")


# --------------------------------------------------------------------------- 6. text layer vs OCR
def check_text_layer(page, words, pno, scale):
    layer = [(w[4].strip(".,"), w) for w in page.get_text("words")]
    layer_nums = {t: w for t, w in layer if is_numeric(t) and len(t) >= 3}
    ocr_nums = {w["text"].strip(".,"): w for w in words
                if is_numeric(w["text"]) and len(w["text"]) >= 3 and w["conf"] >= 70}
    if not layer or not ocr_nums:
        return
    for t, w in layer_nums.items():
        if t not in ocr_nums:
            bb = [int(w[0] * scale), int(w[1] * scale), int((w[2] - w[0]) * scale), int((w[3] - w[1]) * scale)]
            flag(t, "Present in the PDF text layer but not visible on the rendered page "
                    "(hidden or covered text)", "high", bb, pno, "layer")
    for t, w in ocr_nums.items():
        if t not in layer_nums:
            flag(t, "Visible on the page but absent from the PDF text layer "
                    "(overlay image or text drawn as graphics)", "medium",
                 [w["x"], w["y"], w["w"], w["h"]], pno, "layer")


# --------------------------------------------------------------------------- 7. rules
def parse_date(kind, g):
    try:
        if kind == "ymd":
            return datetime(int(g[0]), int(g[1]), int(g[2]))
        mon = int(g[1]) if kind == "dmy" else MONTHS.split("|").index(g[1][:3].lower()) + 1
        y = int(g[2]) + (2000 if int(g[2]) < 100 else 0)
        for d, m in ([(int(g[0]), mon)] + ([(mon, int(g[0]))] if kind == "dmy" else [])):
            try:
                return datetime(y, m, d)
            except ValueError:
                continue
    except (ValueError, IndexError):
        pass
    return None


def check_rules(lines, pno):
    now = datetime.now()
    date_styles = Counter()
    decimals = []
    for ws in lines:
        text = " ".join(w["text"] for w in ws)
        box = union_box(ws)

        for kind, rx in DATE_PATTERNS:
            for m in rx.finditer(text):
                date_styles[(kind, m.group(0)[2:3] if kind == "dmy" else "")] += 1
                d = parse_date(kind, m.groups())
                if d is None:
                    flag(m.group(0), "Impossible calendar date (e.g. day 31 in a 30-day month)",
                         "high", box, pno, "rule")
                elif d > now:
                    flag(m.group(0), f"Date is in the future ({d:%d %b %Y})", "medium", box, pno, "rule")
                elif d.year < 1990:
                    flag(m.group(0), "Implausibly old date", "low", box, pno, "rule")

        for w in ws:
            t = clean(w["text"])
            wb = [w["x"], w["y"], w["w"], w["h"]]
            if re.fullmatch(r"[\dOolISBZ,\.]{3,}", t):
                digits = sum(c.isdigit() for c in t)
                subs = sum(c in "OolISBZ" for c in t)
                if digits and subs and digits / len(t) >= 0.5:
                    flag(t, "Letters mixed into a number (O/0, l/1, S/5 substitution), "
                            "typical of retyped or edited digits", "medium", wb, pno, "rule")
            if "," in t and is_numeric(t) and len(t) >= 5:
                core = t.lstrip("$₹€£").rstrip("%")
                if not (re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", core)
                        or re.fullmatch(r"\d{1,2}(,\d{2})+,\d{3}(\.\d+)?", core)):
                    flag(t, "Malformed thousands separators", "medium", wb, pno, "rule")
            if is_numeric(t) and "." in t:
                decimals.append((len(t.rstrip("%").split(".")[-1]), w))

    if len(decimals) >= 4:
        common = Counter(n for n, _ in decimals).most_common(1)[0][0]
        for n, w in decimals:
            if n != common and n <= 3:
                flag(w["text"], f"{n} decimal places while most amounts use {common}", "low",
                     [w["x"], w["y"], w["w"], w["h"]], pno, "rule")

    if len({k[0] for k in date_styles}) > 1:
        flag("Dates", f"Mixed date formats in one document: {sorted({k[0] for k in date_styles})}",
             "low", page=pno, check="rule")
    check_totals(lines, pno)


KW_RE = re.compile(r"grand|total|sub-?total|gst|cgst|sgst|igst|vat|tax|discount|net|balance", re.I)
SKIP_ROW = re.compile(r"phone|tel\b|mob|gstin|cin\b|@|pin\b|invoice\s*(no|date)|due\s*date|\bdate\b", re.I)


def wbox(w):
    return [w["x"], w["y"], w["w"], w["h"]]


def merge_split_labels(lines):
    """OCR sometimes splits a two-line label: 'Total' / 'Amount 1,20,000'. Re-join them."""
    out, i = [], 0
    while i < len(lines):
        ws = lines[i]
        toks = [clean(w["text"]) for w in ws]
        if (i + 1 < len(lines) and toks and len(toks) <= 2 and KW_RE.fullmatch(toks[0])
                and not any(is_numeric(t) for t in toks)):
            nxt = [clean(w["text"]).lower() for w in lines[i + 1]]
            if nxt and nxt[0] in ("amount", "due", "payable", "price"):
                out.append(ws + lines[i + 1])
                i += 2
                continue
        out.append(ws)
        i += 1
    return out


def check_totals(lines, pno):
    """Word-level arithmetic checks: qty x price = amount, items = subtotal, GST rate, subtotal+tax-discount = total."""
    lines = merge_split_labels(lines)
    alltext = " ".join(w["text"] for ws in lines for w in ws)
    has_qty = bool(re.search(r"\b(qty|quantity)\b", alltext, re.I))
    items, sub, tax, disc, total, tax_w, tax_rate = [], None, 0.0, 0.0, None, None, None
    for ws in lines:
        toks = [clean(w["text"]) for w in ws]
        k = next((i for i, t in enumerate(toks)
                  if KW_RE.fullmatch(t) and not any(is_money(x) for x in toks[:i])), None)
        if k is not None:
            seg = " ".join(toks[k:]).lower()
            vals = [(to_float(clean(w["text"])), w) for w in ws[k + 1:]
                    if is_numeric(w["text"]) and "%" not in w["text"]]
            vals = [(v, w) for v, w in vals if v is not None]
            if not vals:
                continue
            v, w = vals[-1]
            if re.match(r"sub-?\s*total", seg):
                sub = (v, w)
            elif re.match(r"(grand|total|net|balance)", seg):
                total = (v, w)
            elif re.match(r"(gst|cgst|sgst|igst|vat|tax)", seg):
                tax += v
                tax_w = w
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", seg)
                tax_rate = float(m.group(1)) if m and tax_rate is None else tax_rate
            elif re.match(r"discount", seg):
                disc += v
            continue
        if SKIP_ROW.search(" ".join(toks)) or (toks and toks[0].lower() in ("amount", "due", "payable")):
            continue
        nums = [(to_float(t), w, t) for t, w in zip(toks, ws)
                if is_numeric(t) and "%" not in t and to_float(t) is not None]
        money = [n for n in nums if is_money(n[2])]
        if not money:
            continue
        amt, aw, _ = money[-1]
        first_money = next(i for i, n in enumerate(nums) if is_money(n[2]))
        pre = [int(t) for t in toks[:ws.index(nums[first_money][1])] if re.fullmatch(r"\d{1,3}", t)]
        items.append((pre[-1] if pre else 1, amt))
        if has_qty and len(nums) >= 3 and is_money(nums[-2][2]):
            q, u = nums[-3][0], nums[-2][0]
            if abs(q * u - amt) > 0.02 and abs(u - amt) > 0.02:
                flag(f"{aw['text']}", f"Row arithmetic: qty {q:g} x unit price {u:,.2f} = {q * u:,.2f}, "
                                      f"but amount shown is {amt:,.2f}", "high", wbox(aw), pno, "rule")

    if not items:
        return
    plain = sum(v for _, v in items)
    with_qty = sum(q * v for q, v in items)
    if sub and abs(sub[0] - plain) > 1.0 and abs(sub[0] - with_qty) > 1.0:
        flag(f"Subtotal {sub[0]:,.2f}", f"Line amounts add up to {plain:,.2f}, not the stated subtotal",
             "high", wbox(sub[1]), pno, "rule")
    base = sub[0] if sub else plain
    if tax_rate and tax and tax_w is not None:
        exp = [base * tax_rate / 100, (base - disc) * tax_rate / 100]
        if all(abs(tax - e) > 1.0 for e in exp):
            flag(f"Tax {tax:,.2f}", f"{tax_rate:g}% of {base:,.2f} is {exp[0]:,.2f}, not {tax:,.2f}",
                 "medium", wbox(tax_w), pno, "rule")
    if total:
        cands = [base + tax - disc, plain + tax - disc, with_qty + tax - disc]
        if all(abs(c - total[0]) > 1.0 for c in cands):
            sev = "high" if sub else "medium"
            flag(f"Total {total[0]:,.2f}",
                 f"Subtotal/items {base:,.2f} + tax {tax:,.2f} - discount {disc:,.2f} = {cands[0]:,.2f}, "
                 f"but the total shown is {total[0]:,.2f}", sev, wbox(total[1]), pno, "rule")


def tok_date(t):
    for kind, rx in DATE_PATTERNS[:2]:
        m = rx.fullmatch(t)
        if m:
            return parse_date(kind, m.groups())
    return None


def labeled_date(lines, label):
    n = len(label)
    for ws in lines:
        toks = [clean(w["text"]).lower() for w in ws]
        for i in range(len(toks) - n + 1):
            if tuple(toks[i:i + n]) == label:
                for w in ws[i + n:]:
                    d = tok_date(clean(w["text"]))
                    if d:
                        return d, w
    return None


def check_date_logic(lines, pno):
    inv = labeled_date(lines, ("invoice", "date")) or labeled_date(lines, ("issue", "date"))
    due = labeled_date(lines, ("due", "date"))
    if not (inv and due):
        return
    (d_inv, _), (d_due, w_due) = inv, due
    alltext = " ".join(w["text"] for ws in lines for w in ws)
    if d_due < d_inv:
        flag(w_due["text"], f"Due date ({d_due:%d %b %Y}) is earlier than the invoice date ({d_inv:%d %b %Y})",
             "high", wbox(w_due), pno, "rule")
    else:
        m = re.search(r"within\s+(\d+)\s+days", alltext, re.I)
        if m and abs((d_due - d_inv).days - int(m.group(1))) > 2:
            flag(w_due["text"], f"Due date is {(d_due - d_inv).days} days after invoice date but terms say "
                                f"{m.group(1)} days", "medium", wbox(w_due), pno, "rule")


# --------------------------------------------------------------------------- driver
def load_pages(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        if fitz is None:
            sys.exit("PDF support needs PyMuPDF: pip install pymupdf")
        doc = fitz.open(path)
        check_pdf_metadata(path, doc)
        scale = PDF_DPI / 72
        for i, page in enumerate(doc, 1):
            pix = page.get_pixmap(dpi=PDF_DPI)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            yield i, img, page, scale
    else:
        img = Image.open(path)
        check_image_metadata(img)
        yield 1, img, None, 1


def _legend_font(size=22):
    for name in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _highlight(im, boxes, rgb, alpha, pad=3):
    """Paint translucent filled 'highlighter' rectangles so the text underneath stays readable."""
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x, y, w, h in boxes:
        d.rounded_rectangle([x - pad, y - pad, x + w + pad, y + h + pad], radius=4, fill=rgb + (alpha,))
    return Image.alpha_composite(im, layer)


def save_png(im, out):
    """Write via a plain 'wb' handle (PIL's own 'w+b' open fails with Errno 22 on some Windows drives),
    and fall back to the script folder, then the temp folder, if the target can't be written."""
    out = os.path.abspath(os.path.normpath(out))
    here = os.path.dirname(os.path.abspath(__file__))
    last = None
    for p in (out, os.path.join(here, os.path.basename(out)), os.path.join(tempfile.gettempdir(), os.path.basename(out))):
        try:
            with open(p, "wb") as fh:
                im.save(fh, format="PNG")
            if p != out:
                print(f"Could not write {out} ({last}); saved here instead:")
            return p
        except OSError as e:
            last = e
    print(f"Could not save the annotated image: {last}")
    return None


def annotate(path, pages_imgs):
    """Filled markers: RED = suspicious text/value (rule, layer, ELA, layout), YELLOW = font change."""
    RED, YELLOW = (255, 0, 0), (255, 214, 0)
    for pno, img in pages_imgs.items():
        im = img.convert("RGBA")
        page_flags = [f for f in flags if f["page"] == pno and f["bbox"]]
        yellow = [f["bbox"] for f in page_flags if f["marker"] == "yellow"]
        red = [f["bbox"] for f in page_flags if f["marker"] == "red"]
        im = _highlight(im, yellow, YELLOW, 150, pad=4)   # yellow first, red on top
        im = _highlight(im, red, RED, 110, pad=3)
        # legend bar on top
        bar = 52
        out_im = Image.new("RGB", (im.width, im.height + bar), "white")
        out_im.paste(im.convert("RGB"), (0, bar))
        ld = ImageDraw.Draw(out_im)
        fnt = _legend_font(22)
        ld.rounded_rectangle([16, 12, 44, 40], radius=4, fill=(255, 150, 150))
        ld.text((54, 12), "Suspicious text / value", fill="black", font=fnt)
        ld.rounded_rectangle([320, 12, 348, 40], radius=4, fill=(255, 226, 90))
        ld.text((358, 12), "Font change", fill="black", font=fnt)
        base = os.path.splitext(path)[0]
        out = f"{base}_annotated.png" if len(pages_imgs) == 1 else f"{base}_p{pno}_annotated.png"
        saved = save_png(out_im, out)
        if saved:
            print(f"Annotated image: {saved}")


def analyse(path):
    pages_imgs = {}
    for pno, img, page, scale in load_pages(path):
        pages_imgs[pno] = img
        words, lines = run_ocr(img)
        if page is not None:
            check_pdf_fonts(page, pno, scale)
            check_text_layer(page, words, pno, scale)
        elif (img.format or "").upper() == "JPEG":
            check_ela(img, words)
        else:
            print("Note: ELA skipped (only meaningful for JPEG input; PNG/screenshots are lossless "
                  "and give false positives on bold or coloured text).")
        check_layout(words, pno)
        check_rules(lines, pno)
        check_date_logic(lines, pno)
        if pno == 1:
            print("\n" + "=" * 80 + "\nOCR TEXT (page 1)\n" + "=" * 80)
            for ws in lines:
                print("  ".join(w["text"] for w in ws))
    return pages_imgs


def report(path):
    score = sum(SEV_WEIGHT[f["severity"]] for f in flags)
    strong = [f for f in flags if f["severity"] in ("medium", "high")]
    cats = {f["check"] for f in strong}
    verdict = ("LIKELY TAMPERED" if len(cats) >= 2 or score >= 12
               else "SUSPICIOUS" if strong else "NO STRONG SIGNS OF TAMPERING")
    print("\n" + "=" * 80 + f"\nTAMPERING REPORT: {os.path.basename(path)}\n" + "=" * 80)
    for f in sorted(flags, key=lambda f: -SEV_WEIGHT[f["severity"]]):
        print(f"[{f['severity'].upper():6}] p{f['page']} ({f['check']}) '{f['field']}': {f['reason']}")
    if not flags:
        print("No flags raised.")
    print(f"\nRisk score: {score}   Verdict: {verdict}")
    print("Note: flags are indicators, not proof. Verify with the issuer.")
    out = os.path.splitext(path)[0] + "_tamper_report.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"file": path, "risk_score": score, "verdict": verdict, "flags": flags}, fh, indent=2)
    print(f"JSON report: {out}")


def pick_file():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    p = filedialog.askopenfilename(title="Select document",
                                   filetypes=[("Documents", "*.pdf *.png *.jpg *.jpeg *.bmp")])
    root.destroy()
    return p


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else pick_file()
    if not file_path:
        sys.exit("No file selected.")
    imgs = analyse(file_path)
    report(file_path)
    annotate(file_path, imgs)