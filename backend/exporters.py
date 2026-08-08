"""
Evidence export for government agencies.

A cleanup operation is only actionable to NEA / marine parks / municipal waste
teams if the detections leave this system in a format their existing tooling
already reads. Three formats cover that:

  * CSV     — opens in Excel, ingests into almost any municipal database
  * GeoJSON — drops straight into QGIS / ArcGIS / Google Earth as a point layer
  * PDF     — a signed-off situation report a human can file or forward

Every export carries provenance (mission, capture time, model confidence,
detection method) so a receiving agency can audit where a coordinate came from.
"""

import csv
import datetime
import io
from typing import Dict, List, Optional

# Fields exported to CSV, in the order agencies expect to read them.
CSV_COLUMNS = [
    "pin_id",
    "mission_title",
    "mission_date",
    "latitude",
    "longitude",
    "confidence",
    "status",
    "detected_at",
    "cleaned_at",
    "assigned_to",
    "image_url",
    "detection_method",
]


def _fmt(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _confidence_band(confidence: Optional[float]) -> str:
    """Human-readable reliability band — agencies rarely want a bare float."""
    if confidence is None:
        return "Unknown"
    if confidence >= 0.75:
        return "High"
    if confidence >= 0.5:
        return "Medium"
    return "Low"


def build_csv(pins: List[Dict], mission: Optional[Dict] = None) -> str:
    """Renders detections as CSV text."""
    mission = mission or {}
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    for pin in pins:
        writer.writerow({
            "pin_id": _fmt(pin.get("id")),
            "mission_title": _fmt(mission.get("title"), "Unassigned Patrol"),
            "mission_date": _fmt(mission.get("mission_date")),
            "latitude": _fmt(pin.get("latitude")),
            "longitude": _fmt(pin.get("longitude")),
            "confidence": _fmt(round(float(pin["confidence"]), 4)) if pin.get("confidence") is not None else "",
            "status": _fmt(pin.get("status"), "detected"),
            "detected_at": _fmt(pin.get("detected_at")),
            "cleaned_at": _fmt(pin.get("cleaned_at")),
            "assigned_to": _fmt(pin.get("assigned_to")),
            "image_url": _fmt(pin.get("image_url")),
            "detection_method": "YOLOv8 + SAHI tiled aerial inference",
        })

    return buffer.getvalue()


def build_geojson(pins: List[Dict], mission: Optional[Dict] = None) -> Dict:
    """
    Renders detections as a GeoJSON FeatureCollection.

    Coordinates are [longitude, latitude] per the GeoJSON spec (RFC 7946) — the
    reverse of the lat/lon ordering used everywhere else in this codebase, which
    is the single most common mistake when wiring these exports into GIS tools.
    """
    mission = mission or {}
    features = []

    for pin in pins:
        lat, lon = pin.get("latitude"), pin.get("longitude")
        if lat is None or lon is None:
            continue

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(lon), float(lat)],
            },
            "properties": {
                "pin_id": pin.get("id"),
                "status": pin.get("status", "detected"),
                "confidence": pin.get("confidence"),
                "confidence_band": _confidence_band(pin.get("confidence")),
                "detected_at": pin.get("detected_at"),
                "cleaned_at": pin.get("cleaned_at"),
                "assigned_to": pin.get("assigned_to"),
                "image_url": pin.get("image_url"),
                "mission_title": mission.get("title", "Unassigned Patrol"),
                "mission_date": mission.get("mission_date"),
                "detection_method": "YOLOv8 + SAHI tiled aerial inference",
            },
        })

    return {
        "type": "FeatureCollection",
        "name": mission.get("title", "Beach Litter Detections"),
        "crs": {
            # WGS84 stated explicitly; some older GIS importers assume a local
            # projection otherwise and place every point in the wrong hemisphere.
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "metadata": {
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "generated_by": "Beach Litter Management System",
            "total_detections": len(features),
        },
        "features": features,
    }


def summarise(pins: List[Dict]) -> Dict:
    """Headline numbers reused by both the PDF report and the dashboard preview."""
    total = len(pins)
    cleaned = sum(1 for p in pins if p.get("status") == "cleaned")
    outstanding = total - cleaned
    confidences = [float(p["confidence"]) for p in pins if p.get("confidence") is not None]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    high_conf = sum(1 for c in confidences if c >= 0.75)

    lats = [float(p["latitude"]) for p in pins if p.get("latitude") is not None]
    lons = [float(p["longitude"]) for p in pins if p.get("longitude") is not None]
    bbox = {
        "min_lat": min(lats), "max_lat": max(lats),
        "min_lon": min(lons), "max_lon": max(lons),
    } if lats and lons else None

    return {
        "total_detections": total,
        "cleaned": cleaned,
        "outstanding": outstanding,
        "average_confidence": round(avg_conf, 4),
        "high_confidence_count": high_conf,
        "bbox": bbox,
    }


def build_pdf(pins: List[Dict], mission: Optional[Dict] = None) -> bytes:
    """
    Renders a situation report PDF.

    Raises RuntimeError if reportlab is unavailable so the route can return a
    clear 503 rather than a stack trace — CSV and GeoJSON still work without it.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                        TableStyle, PageBreak)
    except ImportError as e:
        raise RuntimeError(
            "PDF export requires reportlab. Install it with: pip install reportlab"
        ) from e

    mission = mission or {}
    stats = summarise(pins)
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Coastal Litter Detection Report — {mission.get('title', 'Patrol')}",
        author="Beach Litter Management System",
    )

    styles = getSampleStyleSheet()
    ocean = colors.HexColor("#0B5563")
    accent = colors.HexColor("#12A594")

    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"],
                                 fontSize=20, textColor=ocean, spaceAfter=4)
    subtitle_style = ParagraphStyle("ReportSubtitle", parent=styles["Normal"],
                                    fontSize=10, textColor=colors.HexColor("#5A6B72"),
                                    spaceAfter=14)
    heading_style = ParagraphStyle("SectionHeading", parent=styles["Heading2"],
                                   fontSize=13, textColor=ocean, spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("ReportBody", parent=styles["Normal"],
                                fontSize=9.5, leading=14)

    story = []
    generated = datetime.datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")

    story.append(Paragraph("Coastal Litter Detection Report", title_style))
    story.append(Paragraph(
        f"Aerial survey evidence package · Generated {generated}", subtitle_style))

    # --- Mission provenance ---
    story.append(Paragraph("Survey Details", heading_style))
    detail_rows = [
        ["Mission", mission.get("title", "Unassigned Patrol")],
        ["Survey date", _fmt(mission.get("mission_date"), "Not recorded")],
        ["Detection method", "YOLOv8 object detection with SAHI tiled inference"],
        ["Positioning", "Drone GPS telemetry with per-frame interpolation (WGS84)"],
        ["Report generated", generated],
    ]
    detail_table = Table(detail_rows, colWidths=[45 * mm, 120 * mm])
    detail_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), ocean),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#DDE5E8")),
    ]))
    story.append(detail_table)

    # --- Headline figures ---
    story.append(Paragraph("Summary", heading_style))
    summary_rows = [
        ["Total detections", "Outstanding", "Resolved", "High confidence", "Mean confidence"],
        [
            str(stats["total_detections"]),
            str(stats["outstanding"]),
            str(stats["cleaned"]),
            str(stats["high_confidence_count"]),
            f"{stats['average_confidence'] * 100:.1f}%",
        ],
    ]
    summary_table = Table(summary_rows, colWidths=[33 * mm] * 5)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ocean),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, 1), 15),
        ("TEXTCOLOR", (0, 1), (-1, 1), accent),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDE5E8")),
    ]))
    story.append(summary_table)

    if stats["bbox"]:
        bbox = stats["bbox"]
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"<b>Survey extent:</b> {bbox['min_lat']:.6f}, {bbox['min_lon']:.6f} "
            f"to {bbox['max_lat']:.6f}, {bbox['max_lon']:.6f} (WGS84)", body_style))

    # --- Full detection register ---
    story.append(PageBreak())
    story.append(Paragraph("Detection Register", heading_style))
    story.append(Paragraph(
        "Each row is a distinct litter object located by aerial survey. Coordinates are "
        "WGS84 decimal degrees and may be pasted directly into a mapping tool.", body_style))
    story.append(Spacer(1, 8))

    register_rows = [["#", "Latitude", "Longitude", "Confidence", "Status", "Detected"]]
    for index, pin in enumerate(pins, start=1):
        detected = _fmt(pin.get("detected_at"))[:19].replace("T", " ")
        conf = pin.get("confidence")
        register_rows.append([
            str(index),
            f"{float(pin['latitude']):.6f}" if pin.get("latitude") is not None else "—",
            f"{float(pin['longitude']):.6f}" if pin.get("longitude") is not None else "—",
            f"{float(conf) * 100:.1f}% ({_confidence_band(conf)})" if conf is not None else "—",
            _fmt(pin.get("status"), "detected").title(),
            detected or "—",
        ])

    register = Table(register_rows, colWidths=[10 * mm, 30 * mm, 30 * mm, 35 * mm, 25 * mm, 35 * mm],
                     repeatRows=1)
    register.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ocean),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F8F9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDE5E8")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(register)

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "<i>Detections are machine-generated from aerial imagery and carry a stated confidence. "
        "Ground verification is recommended before enforcement action.</i>",
        ParagraphStyle("Disclaimer", parent=body_style, fontSize=8,
                       textColor=colors.HexColor("#5A6B72"))))

    doc.build(story)
    return buffer.getvalue()
