/**
 * Flow layout for the JS clone: turns the declarative style rules into pages.
 *
 * The geometry comes from the same rule files the Python generator reads
 * (style/00_page.js, 10_palette.js, 20_typography.js, 30_tables.js, 96_page_identity.js),
 * so a clone report and a Python report are laid out from one source of truth.
 *
 * Pagination policy (style/90_pagination.js) is honoured explicitly:
 *   * a section heading never ends a page (no orphan headings);
 *   * a short table stays together when it fits one page;
 *   * a table header repeats on every continuation page and rows never split.
 */
import { MM } from '../util.mjs';
import { measureText, wrapParagraph, wrapToken } from '../fonts.mjs';

const ALIGN = Object.freeze({ LEFT: 'LEFT', CENTER: 'CENTER', RIGHT: 'RIGHT' });

export class ReportLayout {
  constructor({ styles, builder, footer = {}, title = '', totalPages = 0, footerHashes = null, reportId = '' }) {
    this.styles = styles;
    this.builder = builder;
    this.footerRules = footer;
    // Two-pass rendering: the first pass learns the page count, the second one
    // prints it, so a footer can read "1 / 3" exactly like the Python report.
    this.totalPages = totalPages;
    this.title = title;
    const page = styles.PAGE;
    this.pageWidth = page.width_mm * MM;
    this.pageHeight = page.height_mm * MM;
    this.left = page.left_mm * MM;
    this.right = this.pageWidth - page.right_mm * MM;
    this.top = this.pageHeight - page.top_mm * MM;
    this.bodyBottom = page.bottom_mm * MM;
    this.contentWidth = this.right - this.left;
    this.footerReserved = (page.footer_reserved_mm || 15) * MM;
    this.colors = styles.COLORS;
    this.fonts = styles.FONTS;
    this.leading = styles.LEADING;
    this.hierarchy = styles.TITLE_HIERARCHY;
    this.tableRules = styles.TABLE;
    this.columns = styles.COLUMNS;
    this.keyValue = styles.KEY_VALUE;
    this.identity = styles.PAGE_IDENTITY || {};
    this.minimumContentWidth = (page.minimum_content_width_mm || 100) * MM;
    if (this.contentWidth < this.minimumContentWidth) {
      throw new Error('Page geometry leaves a content area narrower than the policy minimum');
    }
    this.cursor = this.top;
    this.pages = [];
    // Two-pass text hashing: every body draw call is recorded per page so the
    // appendix and the footer can publish digests of the text that was drawn.
    // Footer draws are excluded, exactly like the Python page identity.
    this.pageTexts = [];
    this.footerHashes = Array.isArray(footerHashes) ? footerHashes : null;
    this.reportId = reportId;
    const drawText = this.builder.drawText.bind(this.builder);
    this.builder.drawText = (args = {}) => {
      if (args.band !== 'footer' && this.pageTexts.length) {
        this.pageTexts[this.pageTexts.length - 1].push(String(args.text ?? ''));
      }
      return drawText(args);
    };
    this.newPage();
  }

  get pageCount() {
    return this.pages.length;
  }

  newPage() {
    if (this.builder.pageIndex > 0) this.builder.finishPage();
    this.builder.beginPage();
    this.cursor = this.top;
    this.pageTexts.push([]);
    this.drawFooter();
    this.pages.push({ index: this.builder.pageIndex });
    return this.pages.length;
  }

  drawFooter() {
    const identity = this.identity;
    const separatorY = identity.separator_y_pt || 65;
    this.builder.drawLine({
      x1: this.left,
      y1: separatorY,
      x2: this.right,
      y2: separatorY,
      color: identity.separator_color || this.colors.grid,
      width: identity.separator_width_pt || 0.55,
    });
    const left = identity.footer_left_x_pt || 16;
    const right = this.pageWidth - (identity.footer_right_margin_mm || 5) * MM - 1;
    const pageNumber = this.builder.pageIndex;

    // Per-page text hashes: tiny, searchable, lower-left. The first line is the
    // scope heading, the six algorithm lines follow at the declared leading.
    const hashLines = this.footerHashes ? this.footerHashes[pageNumber - 1] : null;
    if (hashLines && hashLines.length) {
      const hashSize = identity.footer_hash_font_pt || 4;
      const leading = identity.footer_hash_leading_pt || 6;
      const headingY = identity.footer_heading_y_pt || 57;
      const startY = identity.footer_hash_start_y_pt || 50;
      hashLines.forEach((text, position) => {
        this.builder.drawText({
          role: 'regular',
          size: hashSize,
          x: left,
          y: position === 0 ? headingY : startY - (position - 1) * leading,
          text,
          color: this.colors.muted,
          band: 'footer',
        });
      });
    }

    // Identity block: right aligned, as in the Python page identity.
    const lines = [
      [identity.brand || 'CRYPTO REPORT ENTERPRICE', identity.footer_brand_font_pt || 7, 'bold', identity.footer_brand_y_pt || 45],
      [identity.license || '', identity.footer_other_font_pt || 6.6, 'regular', identity.footer_license_y_pt || 35],
      [identity.developer || '', identity.footer_other_font_pt || 6.6, 'regular', identity.footer_developer_y_pt || 25],
      [identity.url || '', identity.footer_other_font_pt || 6.6, 'regular', identity.footer_url_y_pt || 16],
    ];
    for (const [text, size, role, y] of lines) {
      if (!text) continue;
      const maxWidth = identity.footer_left_max_width_pt || 300;
      const fitted = measureText(role, text, size) <= maxWidth
        ? text
        : wrapToken(role, text, size, maxWidth)[0];
      this.builder.drawText({
        role,
        size,
        x: right - measureText(role, fitted, size),
        y,
        text: fitted,
        color: this.colors.muted,
        band: 'footer',
      });
    }

    if (this.reportId) {
      const idSize = identity.footer_id_font_pt || 6.3;
      this.builder.drawText({
        role: 'regular',
        size: idSize,
        x: right - measureText('regular', this.reportId, idSize),
        y: identity.footer_id_y_pt || 55,
        text: this.reportId,
        color: this.colors.ink,
        band: 'footer',
      });
    }

    const pageLabel = this.totalPages > 0
      ? `${pageNumber} / ${this.totalPages}`
      : `Page ${pageNumber}`;
    const size = identity.footer_page_font_pt || 8;
    const width = measureText('bold', pageLabel, size);
    this.builder.drawText({
      role: 'bold',
      size,
      x: (this.pageWidth - width) / 2,
      y: identity.footer_page_y_pt || 55,
      text: pageLabel,
      color: this.colors.ink,
      band: 'footer',
    });
  }

  /** Recorded body text per page, in draw order; footers are never included. */
  pageTextLines() {
    return this.pageTexts.map((lines) => [...lines]);
  }

  spaceFor(height) {
    return this.cursor - height >= this.bodyBottom;
  }

  /**
   * Start a new page when the current one already carries content. A declared
   * layout of its own (the checksum appendix) must never inherit the tail of the
   * previous section, or its heading would be separated from its table.
   */
  pageBreak() {
    if (this.cursor < this.top - 1) return this.newPage();
    return this.pages.length;
  }

  ensure(height) {
    if (this.spaceFor(height)) return false;
    this.newPage();
    return true;
  }

  gap(points) {
    this.cursor -= points;
  }

  heading(text, level = 'section', { center = false } = {}) {
    const rule = this.hierarchy[level] || this.hierarchy.section;
    const size = rule.size_pt;
    const role = rule.bold ? 'bold' : 'regular';
    const display = rule.uppercase ? String(text).toUpperCase() : String(text);
    const leading = Math.max(size * 1.3, 12);
    // No orphan headings: the heading and its first lines must share a page.
    this.ensure(leading + this.leading.body * 3);
    this.cursor -= leading * 0.35;
    const width = measureText(role, display, size);
    const x = center ? this.left + (this.contentWidth - width) / 2 : this.left;
    this.builder.drawText({ role, size, x, y: this.cursor - size, text: display, color: this.colors.accent });
    this.cursor -= leading;
    return this;
  }

  paragraph(text, { role = 'regular', size = this.fonts.body, leading = this.leading.body, color = this.colors.ink, indent = 0, maxWidth = null } = {}) {
    const width = (maxWidth || this.contentWidth) - indent;
    for (const line of wrapParagraph(role, text, size, width)) {
      this.ensure(leading);
      this.cursor -= leading;
      this.builder.drawText({ role, size, x: this.left + indent, y: this.cursor + (leading - size) * 0.25, text: line, color });
    }
    return this;
  }

  /**
   * Paragraph with the `<b>` / `<br/>` markup the legal block uses. Runs keep
   * their own font role, so a bold lead-in measures and wraps correctly.
   */
  richParagraph(markup, { size = this.fonts.legal, leading = this.leading.legal, color = this.colors.ink } = {}) {
    const blocks = String(markup).split(/<br\s*\/?>/i);
    for (const block of blocks) {
      const tokens = [];
      let bold = false;
      for (const part of block.split(/(<\/?b>)/i)) {
        if (/^<b>$/i.test(part)) { bold = true; continue; }
        if (/^<\/b>$/i.test(part)) { bold = false; continue; }
        if (!part) continue;
        const role = bold ? 'bold' : 'regular';
        for (const piece of part.split(/(\s+)/)) {
          if (piece) tokens.push({ text: piece, role, space: /^\s+$/.test(piece) });
        }
      }
      let line = [];
      let width = 0;
      const flush = () => {
        while (line.length && line[line.length - 1].space) line.pop();
        if (!line.length) return;
        this.ensure(leading);
        this.cursor -= leading;
        let x = this.left;
        for (const token of line) {
          this.builder.drawText({
            role: token.role,
            size,
            x,
            y: this.cursor + (leading - size) * 0.25,
            text: token.text,
            color,
          });
          x += measureText(token.role, token.text, size);
        }
        line = [];
        width = 0;
      };
      for (const token of tokens) {
        const tokenWidth = measureText(token.role, token.text, size);
        if (!token.space && width + tokenWidth > this.contentWidth && line.length) flush();
        line.push(token);
        width += tokenWidth;
      }
      flush();
    }
    return this;
  }

  /** Label/value rows using the declared KEY_VALUE ratio and TABLE padding. */
  keyValues(pairs, { labelRole = 'bold', valueRole = 'regular', size = this.fonts.body, leading = this.leading.body } = {}) {
    const ratio = this.keyValue.label_ratio;
    const padding = this.tableRules.padding_pt;
    const labelWidth = this.contentWidth * ratio - padding * 2;
    const valueWidth = this.contentWidth * (1 - ratio) - padding * 2;
    for (const [label, value] of pairs) {
      const labelLines = wrapParagraph(labelRole, label, size, labelWidth);
      const valueLines = wrapParagraph(valueRole, String(value), size, valueWidth);
      const rows = Math.max(labelLines.length, valueLines.length);
      const height = rows * leading + padding * 2;
      this.ensure(height);
      this.cursor -= height;
      this.builder.drawRect({
        x: this.left,
        y: this.cursor,
        width: this.contentWidth,
        height,
        color: this.styles.OBJECTS?.stripe_color || this.colors.stripe,
        stroke: this.keyValue.rule_color || this.colors.grid,
        lineWidth: this.keyValue.rule_pt || 0.2,
      });
      labelLines.forEach((line, index) => {
        this.builder.drawText({
          role: labelRole,
          size,
          x: this.left + padding,
          y: this.cursor + height - padding - size - index * leading,
          text: line,
          color: this.colors.ink,
        });
      });
      valueLines.forEach((line, index) => {
        this.builder.drawText({
          role: valueRole,
          size,
          x: this.left + this.contentWidth * ratio + padding,
          y: this.cursor + height - padding - size - index * leading,
          text: line,
          color: this.colors.ink,
        });
      });
    }
    this.gap(4);
    return this;
  }

  columnGeometry(weights) {
    const total = weights.reduce((sum, value) => sum + value, 0) || 1;
    let x = this.left;
    return weights.map((weight) => {
      const width = (this.contentWidth * weight) / total;
      const box = { x, width };
      x += width;
      return box;
    });
  }

  /**
   * Draw a table. `columns` carry `title`, `weight`, `align`, `role`, `size`,
   * and an optional `chunk` size used to break digests into fixed-width lines.
   */
  table({ columns, rows }) {
    const padding = this.tableRules.padding_pt;
    const headerSize = this.fonts.table_header;
    const headerLeading = headerSize * 1.25;
    const geometry = this.columnGeometry(columns.map((column) => column.weight));
    const headerLines = columns.map((column, index) => wrapParagraph('bold', column.title, headerSize, geometry[index].width - padding * 2));
    const headerHeight = Math.max(...headerLines.map((lines) => lines.length)) * headerLeading + padding * 2;

    const drawHeader = () => {
      this.ensure(headerHeight);
      this.cursor -= headerHeight;
      this.builder.drawRect({
        x: this.left,
        y: this.cursor,
        width: this.contentWidth,
        height: headerHeight,
        color: this.colors.accent,
      });
      headerLines.forEach((lines, index) => {
        lines.forEach((line, lineIndex) => {
          this.builder.drawText({
            role: 'bold',
            size: headerSize,
            x: geometry[index].x + padding,
            y: this.cursor + headerHeight - padding - headerSize - lineIndex * headerLeading,
            text: line,
            color: this.colors.header_text,
          });
        });
      });
    };

    drawHeader();
    let index = 0;
    for (const row of rows) {
      const cells = columns.map((column, columnIndex) => {
        const width = geometry[columnIndex].width - padding * 2;
        const role = column.role || 'regular';
        const size = column.size || this.fonts.table_text;
        const leading = column.leading || (role === 'monospace' ? this.leading.table_hash : this.leading.table_text);
        const raw = String(row[column.key] ?? '');
        const chunkSize = typeof column.chunk === 'function' ? column.chunk(width, size) : column.chunk;
        let lines;
        if (chunkSize) {
          lines = raw.match(new RegExp(`.{1,${chunkSize}}`, 'g')) || [''];
        } else if (column.multiline && raw.includes('\n')) {
          lines = raw.split('\n').flatMap((part) => wrapParagraph(role, part, size, width));
        } else {
          lines = wrapParagraph(role, raw, size, width);
        }
        return { lines, role, size, leading, align: column.align || ALIGN.LEFT, width };
      });
      const height = Math.max(...cells.map((cell) => cell.lines.length * cell.leading)) + padding * 2;
      if (!this.spaceFor(height)) {
        this.newPage();
        drawHeader();
      }
      this.cursor -= height;
      if (this.tableRules.alternate_rows && index % 2 === 1) {
        this.builder.drawRect({
          x: this.left,
          y: this.cursor,
          width: this.contentWidth,
          height,
          color: this.colors.stripe,
        });
      }
      cells.forEach((cell, columnIndex) => {
        cell.lines.forEach((line, lineIndex) => {
          let x = geometry[columnIndex].x + padding;
          if (cell.align === ALIGN.RIGHT) {
            x = geometry[columnIndex].x + geometry[columnIndex].width - padding - measureText(cell.role, line, cell.size);
          } else if (cell.align === ALIGN.CENTER) {
            x = geometry[columnIndex].x + (geometry[columnIndex].width - measureText(cell.role, line, cell.size)) / 2;
          }
          this.builder.drawText({
            role: cell.role,
            size: cell.size,
            x,
            y: this.cursor + height - padding - cell.size - lineIndex * cell.leading,
            text: line,
            color: this.colors.ink,
          });
        });
      });
      this.builder.drawLine({
        x1: this.left,
        y1: this.cursor,
        x2: this.right,
        y2: this.cursor,
        color: this.colors.grid,
        width: 0.4,
      });
      index += 1;
    }
    this.gap(6);
    return this;
  }

  finish() {
    this.builder.finishPage();
    return this.pages;
  }
}

export { ALIGN };
