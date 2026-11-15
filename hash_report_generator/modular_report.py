"""Declarative report renderer. Cryptographic production flows stay separate."""
from __future__ import annotations

import hashlib
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

# Support direct execution and package imports.
_report_dir = Path(__file__).resolve().parent
for _report_path in (str(_report_dir.parent), str(_report_dir)):
    if str(_report_path) not in sys.path:
        sys.path.insert(0, str(_report_path))

from reportlab import platypus
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm

from hash_report_generator.a4_document import A4DocTemplate
from hash_report_generator.module_loader import load_modules, load_profiles
from hash_report_generator.pdf_object_rules import (
    aligned_fields,
    font_name,
    GlobalReportTable,
    legal_panel,
    legal_qr_box_style,
    legal_qr_layout_style,
    report_title_flowables,
    reportlab_table_style,
)
from hash_report_generator.style_loader import load_styles
from hash_report_generator.style_runtime import visual as _central_visual


def _paragraph_style(role, objects, visual):
    spec = objects[role]
    size = spec.get("font_size_pt", visual["default_font_size_pt"])
    return ParagraphStyle(
        role,
        fontName=font_name(spec.get("font_role", visual["default_font_role"])),
        fontSize=size,
        leading=spec.get(
            "leading_pt", size * visual["default_leading_multiplier"]
        ),
        spaceBefore=spec.get("space_before_pt", visual["default_space_before_pt"]),
        spaceAfter=spec.get("space_after_pt", visual["default_space_after_pt"]),
        alignment=TA_LEFT,
        keepWithNext=role == "section_title",
        splitLongWords=_central_visual("modular_report__L25__splitLongWords"),
        textColor=colors.HexColor(
            spec.get("color", visual["default_text_color"])
        ),
    )


def _file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    named_after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
        or after.st_dev != named_after.st_dev
        or after.st_ino != named_after.st_ino
    ):
        raise RuntimeError(f"File changed while its report was being generated: {path}")
    return digest.hexdigest(), after


def _format_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )[:-3]


def _file_information(path, module, context):
    digest, metadata = _file_digest(path)
    size_format = module.get("size_display", {})
    if size_format.get("unit") != "KB":
        raise ValueError("file_information size_display.unit must be KB")
    decimal_places = size_format.get("decimal_places", 3)
    if not isinstance(decimal_places, int) or not 0 <= decimal_places <= 6:
        raise ValueError("file_information size_display.decimal_places must be 0..6")
    size_kb = f"{metadata.st_size / 1024:,.{decimal_places}f} KB"
    return {
        "name": path.name,
        "size_kb": size_kb,
        "created": _format_timestamp(
            getattr(metadata, "st_birthtime", metadata.st_ctime)
        ),
        "modified": _format_timestamp(metadata.st_mtime),
        "sha256": digest,
        "hardware_id": context.get(
            "Hardware ID", context.get("hardware_id", "Unknown")
        ),
        "report_id": context["Report ID"],
    }


def _make_file_information_table(values, module, rules, objects, visual, width):
    fields = module.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError("file_information module must declare a non-empty fields list")
    labels = {
        "name": "File Name",
        "size_kb": "File Size",
        "created": "Created",
        "modified": "Last Modified",
        "sha256": "SHA-256 Hash",
        "hardware_id": "Hardware ID",
        "report_id": "Report ID",
    }
    cell_style = _paragraph_style("table_cell", objects, visual)
    header_spec = objects["table_header"]
    header_style = ParagraphStyle(
        "file_information_header",
        parent=cell_style,
        fontName=font_name(header_spec["font_role"]),
        fontSize=header_spec["font_size_pt"],
        textColor=colors.HexColor(header_spec["color"]),
        alignment=1,
    )
    rows = [[
        platypus.Paragraph("Property", header_style),
        platypus.Paragraph("Value", header_style),
    ]]
    for key in fields:
        if key not in labels:
            raise ValueError(f"Unsupported file_information field: {key}")
        if key not in values:
            raise ValueError(f"Missing value for file_information field: {key}")
        value = escape(str(values[key]))
        if key == "sha256":
            value = "<br/>".join(value[i:i + visual["hash_chunk_chars"]]
                                 for i in range(0, len(value), visual["hash_chunk_chars"]))
        rows.append([
            platypus.Paragraph(escape(labels[key]), cell_style),
            platypus.Paragraph(value, cell_style),
        ])
    proportions = rules["COLUMNS"]["info"]
    table = GlobalReportTable(
        rows,
        colWidths=[width * proportions["property"], width * proportions["value"]],
        repeatRows=visual["repeat_header_rows"],
        splitByRow=visual["split_by_row"],
        hAlign=visual["table_horizontal_alignment"],
    )
    table.setStyle(reportlab_table_style(header=True))
    return table


def _make_legal_panel(content, module, use_qr, doc, rules, styles):
    paragraph = platypus.Paragraph(content, styles["legal_notice"])
    qr_name = module.get("qr_image")
    if not qr_name or not use_qr:
        return legal_panel(paragraph, doc.width)

    image_path = (_report_dir / qr_name).resolve()
    if not image_path.is_relative_to(_report_dir) or not image_path.is_file():
        raise FileNotFoundError(f"Legal QR image is missing or outside assets: {image_path}")

    qr_rules = rules["BRIDGE_LAYOUT"]["legal_qr"]
    qr_width = doc.width * qr_rules["qr_column_fraction"]
    qr_size = min(
        rules["LAYOUT_OBJECTS"]["qr_code"]["size_pt"],
        qr_rules["qr_size_mm"] * mm,
    )
    qr_image = platypus.Image(str(image_path), width=qr_size, height=qr_size)
    qr_image.hAlign = "CENTER"
    caption_style = ParagraphStyle(
        "legal_qr_caption",
        parent=styles["legal_notice"],
        fontSize=qr_rules["caption_font_pt"],
        leading=qr_rules["caption_leading_pt"],
        alignment=1,
        textColor=colors.HexColor(rules["BRIDGE_LAYOUT"]["colors"]["qr_caption"]),
    )
    caption = platypus.Paragraph(module.get("qr_caption", ""), caption_style)
    qr_box = platypus.Table([[qr_image], [caption]], colWidths=[qr_width])
    qr_box.setStyle(legal_qr_box_style())
    table = platypus.Table(
        [[paragraph, qr_box]],
        colWidths=[doc.width - qr_width, qr_width],
        hAlign="LEFT",
    )
    table.setStyle(legal_qr_layout_style())
    return table


def render_report(
    profile_id,
    output_path,
    files=(),
    system=None,
    legal_text="",
    source=None,
    scope=None,
):
    """Render a report from an ordered profile of declarative content modules."""
    rules = load_styles()
    modules = load_modules()
    profiles = load_profiles(modules=modules)
    if profile_id not in profiles:
        raise ValueError(f"Unknown profile: {profile_id}")

    profile = profiles[profile_id]
    context = dict(system or {})
    generated = datetime.now().astimezone()
    context.setdefault("Generated", generated.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
    report_stamp = generated.strftime("%Y%m%d-%H%M%S%f")[:-3]
    context.setdefault(
        "Report ID",
        f"RPT-{report_stamp}-{uuid.uuid4().hex[:8].upper()}",
    )
    context.setdefault("Report Type", profile.get("title", profile_id))

    obj = rules["LAYOUT_OBJECTS"]
    page = rules["PAGE"]
    blocks = rules["PROCESS_BLOCKS"]
    visual = rules["MODULAR_RENDERER_VISUAL"]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = A4DocTemplate(str(output))
    styles = {
        role: _paragraph_style(role, obj, visual)
        for role in ("section_title", "field_label", "field_value", "legal_notice", "table_cell")
    }
    story = [
        platypus.Spacer(1, visual["title_top_offset_pt"]),
        *report_title_flowables(doc.width),
    ]

    def add_fields(pairs):
        if pairs:
            aligned_fields(story, pairs, styles["field_value"], doc.width)

    for module_id in profile["modules"]:
        module = modules[module_id]
        role = module.get("style", module_id)
        heading = blocks.get(role, {}).get("title", module["title"])
        story.append(platypus.Paragraph(escape(heading.upper()), styles["section_title"]))

        if module["type"] == "hash_table":
            mode = scope or profile.get("input_scope", "single_file")
            selected_source = source
            if selected_source is None:
                if mode == "single_file" and len(files) == 1:
                    selected_source = files[0]
                else:
                    raise ValueError("source is required for hash_table module")
            from hash_report_generator.hash_table_engine import build_rows

            records = build_rows(
                selected_source,
                mode,
                algorithms=tuple(module.get("algorithms", ["sha256"])),
                exclude=[output],
            )
            if not records:
                story.append(platypus.Paragraph("No files found", styles["field_value"]))
            elif mode == "single_file":
                add_fields([
                    (label, str(records[0][key]))
                    for key, label in (
                        ("path", "File Name"),
                        ("type", "Type"),
                        ("size_bytes", "File Size (bytes)"),
                        ("created", "Created (UTC)"),
                        ("modified", "Modified (UTC)"),
                        ("sha256", "SHA-256 Hash"),
                    )
                    if key in records[0]
                ])
            else:
                headers = [
                    "#", "File Name", "Type", "Size (bytes)",
                    "Created (UTC)", "Modified (UTC)", "SHA-256 Hash",
                ]
                widths = list(rules["COLUMNS"]["combined"].values())
                cell_style = _paragraph_style("table_cell", obj, visual)
                head_style = ParagraphStyle(
                    "hash_table_header",
                    parent=cell_style,
                    fontName=font_name(obj["table_header"]["font_role"]),
                    fontSize=obj["table_header"]["font_size_pt"],
                    textColor=colors.HexColor(obj["table_header"]["color"]),
                )

                def cell(value, header=False):
                    text = escape(str(value))
                    if not header and len(text) == 64 and all(
                        char in "0123456789abcdef" for char in text
                    ):
                        text = "<br/>".join(
                            text[i:i + visual["hash_chunk_chars"]]
                            for i in range(0, len(text), visual["hash_chunk_chars"])
                        )
                    return platypus.Paragraph(text, head_style if header else cell_style)

                rows = [[cell(value, True) for value in headers]]
                rows.extend([
                    [cell(record[key]) for key in (
                        "index", "path", "type", "size_bytes",
                        "created", "modified", "sha256",
                    )]
                    for record in records
                ])
                table = GlobalReportTable(
                    rows,
                    colWidths=[doc.width * width for width in widths],
                    splitByRow=visual["split_by_row"],
                    repeatRows=visual["repeat_header_rows"],
                    hAlign=visual["table_horizontal_alignment"],
                )
                table.setStyle(reportlab_table_style(variant="combined", header=True))
                story.append(table)
        elif module["type"] == "file_information":
            selected_files = [Path(item) for item in files]
            if source is not None:
                selected_files = [Path(source)]
            if len(selected_files) != 1:
                raise ValueError("file_information requires exactly one file")
            path = selected_files[0].resolve(strict=True)
            if not path.is_file():
                raise ValueError(f"file_information requires a file: {path}")
            if path == output.resolve():
                raise ValueError("The report output path cannot overwrite its source file")
            values = _file_information(path, module, context)
            story.append(
                _make_file_information_table(values, module, rules, obj, visual, doc.width)
            )
        elif module["type"] == "key_values":
            requested = module.get("fields")
            pairs = (
                [(key, context[key]) for key in requested if key in context]
                if requested
                else list(context.items())
            )
            add_fields(pairs)
        elif module["type"] == "text":
            content = (
                escape(legal_text)
                if legal_text
                else module.get("content")
            )
            if not content:
                raise ValueError(f"No text supplied for module: {module_id}")
            story.append(
                _make_legal_panel(
                    content, module, not bool(legal_text), doc, rules, styles
                )
            )
        else:
            raise ValueError(f"Unsupported module type: {module['type']}")

        story.append(platypus.Spacer(1, rules["DESIGN_LAYOUT"]["section_gap_pt"]))

    def footer(canvas, document):
        canvas.saveState()
        spec = obj["page_footer"]
        canvas.setFont(
            font_name(spec.get("font_role", visual["default_font_role"])),
            spec["font_size_pt"],
        )
        canvas.drawCentredString(
            page["width_mm"] * mm / 2,
            page["footer_reserved_mm"] * mm / 2,
            f"Page {document.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output
