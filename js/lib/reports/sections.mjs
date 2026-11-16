/**
 * Content sections shared by the per-type JS report modules.
 *
 * The Python generator writes a report as a sequence of named blocks
 * (system information, evidence table, TSA record, generation note, legal
 * documentation, checksum appendix). The clone keeps that vocabulary: a report
 * type module declares the base profile plus the extra sections it prints, and
 * this file implements the blocks once so every type shows the same wording.
 *
 * Honesty rule: the clone never signs, never seals and never talks to a TSA, so
 * every timestamp block states NOT APPLIED / NOT VERIFIED instead of borrowing
 * the Python report's VERIFIED wording.
 */
import { COMBINED_COLUMNS, REPORT_TYPE_LABELS, displayDigest, tableRows } from '../report.mjs';
import { ALL_TEXT_ALGORITHMS, PAGE_TEXT_ALGORITHMS } from './checksums.mjs';

const SECTIONS = new Map();

function define(id, build) {
  SECTIONS.set(id, Object.freeze({ id, build }));
}

/** Resolve a section builder by id; unknown ids fail loudly, never silently. */
export function getSection(id) {
  const section = SECTIONS.get(id);
  if (!section) throw new Error(`Unknown report section: ${id}`);
  return section;
}

export function sectionIds() {
  return [...SECTIONS.keys()];
}

function small(layout, text, { role = 'regular', color = null } = {}) {
  layout.paragraph(text, {
    role,
    size: layout.fonts.small,
    leading: layout.leading.small,
    color: color || layout.colors.muted,
  });
  return layout;
}

function body(layout, text) {
  layout.paragraph(text, {
    size: layout.fonts.body,
    leading: layout.leading.body,
    color: layout.colors.ink,
  });
  return layout;
}

/** Two-column property table with the appendix header names from the rules. */
function propertyTable(layout, rows, { valueRole = 'monospace', valueSize = 7.4, valueLeading = 10 } = {}) {
  const identity = layout.identity || {};
  layout.table({
    columns: [
      {
        key: 'property',
        title: identity.appendix_property_header || 'Property',
        weight: 0.24,
        role: 'bold',
        size: 8,
      },
      {
        key: 'value',
        title: identity.appendix_value_header || 'Value',
        weight: 0.76,
        role: valueRole,
        size: valueSize,
        leading: valueLeading,
      },
    ],
    rows,
  });
  return layout;
}

/* ------------------------------------------------------------------ */
/* CRYPTOGRAPHIC TIMESTAMP                                             */
/* ------------------------------------------------------------------ */

define('timestamp_record', (layout, context) => {
  layout.pageBreak();
  layout.heading('CRYPTOGRAPHIC TIMESTAMP:', 'section');
  layout.paragraph(
    'Status of the RFC 3161 evidence timestamp in THIS report. The JavaScript clone '
    + 'runs offline and without a TSA client, so no token is requested, embedded or '
    + 'verified here; the rows below record that fact instead of implying a seal.',
    { size: layout.fonts.small, leading: layout.leading.small, color: layout.colors.ink },
  );
  layout.keyValues([
    ['Protocol', 'RFC 3161 (Time-Stamp Protocol) - reference only, not executed by the clone'],
    ['RFC 3161 Timestamp', 'NOT APPLIED - no token present in this report'],
    ['TSA Selection', 'none - the clone has no TSA client and no failover chain'],
    ['Evidence Digest Algorithm', 'SHA-256 over the aggregated document proof'],
    ['Token Format', 'none - no TimeStampToken, no /DSS entry'],
    ['Timestamp Structure', 'not applicable to this report'],
    ['START / STOP Binding', 'informational boundaries only; nothing is bound to a token'],
    ['Token Verification', 'NOT VERIFIED - no token to verify'],
    ['Signer Validation', 'NOT VERIFIED - no signer certificate'],
    ['Revocation Validation', 'NOT VERIFIED - no CRL / OCSP response'],
    ['genTime Precision', 'not applicable - this report carries no genTime'],
    ['Evidence Preservation', 'local file only; the archive record stores the produced bytes'],
    ['Qualification Status', 'not qualified; not a qualified electronic signature or seal'],
    ['Local Timing Status', `${context.generatedAt} ${context.timezone} - local wall clock, not an independent time proof`],
  ]);

  layout.heading('CRYPTOGRAPHIC TIMESTAMP START:', 'section');
  layout.paragraph('CHRONOSEAL PRE-SEAL RECORD (INFORMATIONAL ONLY)', {
    size: layout.fonts.body,
    leading: layout.leading.body,
    color: layout.colors.ink,
  });
  layout.keyValues([
    ['Recorded at', `${context.generatedAt} ${context.timezone}`],
    ['Report ID', context.reportId],
    ['Evidence digest (SHA-256)', String(context.documentProof || '').toUpperCase()],
    ['Files in scope', String(context.files.length)],
    ['Seal status', 'NOT SEALED - no TSA request was made'],
  ]);

  layout.heading('CRYPTOGRAPHIC TIMESTAMP STOP:', 'section');
  layout.keyValues([
    ['Recorded at', `${context.generatedAt} ${context.timezone}`],
    ['Evidence digest (SHA-256)', String(context.documentProof || '').toUpperCase()],
    ['Pages sealed by a token', 'none'],
    ['Report pages modified after layout', 'none'],
    ['Seal status', 'NOT SEALED - closing boundary of the same unsealed run'],
  ]);
  return layout;
});

/* ------------------------------------------------------------------ */
/* TECHNISCHER ERZEUGUNGSVERMERK                                       */
/* ------------------------------------------------------------------ */

define('generation_note', (layout, context) => {
  layout.pageBreak();
  layout.heading('TECHNISCHER ERZEUGUNGSVERMERK (KEINE EIDESSTATTLICHE VERSICHERUNG):', 'section');
  const volume = context.volume || {};
  layout.keyValues([
    ['Erstellt am', `${context.generatedAt} ${context.timezone}`],
    ['Erstellt durch', (context.user && context.user.user) || 'unknown'],
    ['Computer / Betriebssystem', `${(context.user && context.user.host) || 'unknown'} / ${(context.user && context.user.operating_system) || 'unknown'}`],
    ['Hardware-ID', context.hardwareId || 'not available'],
    ['Report-ID', context.reportId],
    ['Report-Typ', REPORT_TYPE_LABELS[context.reportType] || context.reportType],
    ['Prüfumfang', `${context.files.length} file(s) from ${context.source}`],
    ['Auswahlfilter', context.filterText],
    ['Gesamtgröße', `${context.totalSizeKb} KB`],
    ['Datenträger', volume.short_path ? `${volume.short_path} (${volume.filesystem || 'filesystem unknown'})` : 'not determined'],
    ['Aggregationsmethode', context.aggregationMethod],
    ['Zeitstempel', 'RFC 3161 not applied by this engine - see CRYPTOGRAPHIC TIMESTAMP'],
  ]);

  body(layout, 'Automated technical record (not an affidavit):');
  small(layout, '- The report was produced without human review of the individual file contents.');
  small(layout, '- Every digest is computed from the bytes read at generation time; the evidence set carries no copy of the files.');
  small(layout, '- A matching digest documents byte equality towards the referenced file, nothing about origin, authorship or truth.');
  small(layout, '- Status words VERIFIED / FAILED / NOT VERIFIED describe the actual check result and are never a presumption.');
  small(layout, '- This record contains no affidavit, no notarial certification and no qualified signature.');

  body(layout, 'Prüfumfang / Verification scope:');
  small(layout, '- Reproducible by re-hashing the same bytes with the same eleven algorithms and the same aggregation order.');
  small(layout, '- The aggregation method is printed in SYSTEM INFORMATION so the aggregate value can be recomputed exactly.');
  small(layout, '- Timestamp, signer, revocation and qualification statements of the Python report do not apply to this file.');
  small(layout, '- The archive record and the manifest of this run store digests and paths; they are the audit trail of the run.');

  body(layout, 'Engine:');
  layout.keyValues([
    ['Engine', 'ChronoSeal Enterprise - JavaScript clone (no signing, no TSA)'],
    ['Renderer', 'js/lib/pdf (declarative rules from hash_report_generator/style)'],
    ['Digest engine', `Node ${process.version} crypto`],
    ['PDF/A', 'PDF/A-2b via tools/pdfnorm'],
    ['Statement', 'Automatisch erzeugter technischer Bericht - keine eidesstattliche Versicherung.'],
  ]);
  return layout;
});

/* ------------------------------------------------------------------ */
/* Legal documentation (explanatory document of the Python report)     */
/* ------------------------------------------------------------------ */

define('legal_documentation', (layout, context) => {
  layout.pageBreak();
  layout.heading('RECHTLICHE GRUNDLAGEN FÜR DEUTSCHE GERICHTE', 'section');
  layout.table({
    columns: [
      { key: 'law', title: 'Gesetz / Entscheidung', weight: 0.36, role: 'bold', size: 8 },
      { key: 'meaning', title: 'Bedeutung für den Hash Report', weight: 0.64, role: 'regular', size: 8 },
    ],
    rows: [
      { law: '§ 286 ZPO (Zivilprozessordnung)', meaning: 'Das Gericht würdigt Beweise nach seiner freien Überzeugung. Die technische Dokumentation unterliegt der freien Beweiswürdigung im konkreten Verfahren.' },
      { law: '§ 371 ZPO', meaning: 'Ist eine elektronische Datei Gegenstand des Beweises, erfolgt der Beweisantritt durch Vorlegung oder Übermittlung der Datei. Ein übereinstimmender Hash dokumentiert Byte-Gleichheit zur referenzierten Datei.' },
      { law: '§ 156 StGB (nur bei gesonderter Versicherung an Eides statt)', meaning: 'Die Strafnorm betrifft falsche Versicherungen an Eides statt, soweit eine solche rechtlich vorgesehen und tatsächlich abgegeben wird. Dieser automatisch erstellte technische Bericht enthält keine Versicherung an Eides statt.' },
      { law: 'Art. 41 eIDAS (EU) Nr. 910/2014', meaning: 'Ein elektronischer Zeitstempel darf nicht allein wegen seiner elektronischen Form oder fehlender Qualifikation als Beweismittel zurückgewiesen werden; die besondere Vermutungswirkung gilt für qualifizierte Zeitstempel.' },
    ],
  });

  layout.heading('1. AUTHENTIZITÄT DES REPORTS (SHA-256-HASH)', 'section');
  small(layout, 'Der Report enthält den SHA-256-Hash-Wert der geprüften Datei. SHA-256 ist eine kollisionsresistente kryptographische Prüfsumme. Ein übereinstimmender Hash:');
  small(layout, '• dokumentiert, dass die verglichenen Bytefolgen denselben SHA-256-Wert besitzen;');
  small(layout, '• mit einem Befehl überprüft werden kann: sha256sum [Datei];');
  small(layout, 'Rechtliche Grundlage: Stimmt der neu berechnete Hash mit dem im Report überein, ist die geprüfte Bytefolge mit der referenzierten Bytefolge kryptographisch konsistent. Die rechtliche Würdigung erfolgt im Einzelfall.');

  layout.heading('2. AUTOMATISCHE GENERIERUNG (TECHNISCHE UNABHÄNGIGKEIT)', 'section');
  layout.table({
    columns: [
      { key: 'element', title: 'Element', weight: 0.3, role: 'bold', size: 8 },
      { key: 'proves', title: 'Was es beweist', weight: 0.7, role: 'regular', size: 8 },
    ],
    rows: [
      { element: 'Hardware ID', proves: 'Lokale Systemkennung zur technischen Protokollierung; kein unabhängiger Identitätsnachweis' },
      { element: 'RFC 3161 Timestamp', proves: 'Falls im Report als erfolgreich verifiziert ausgewiesen: signierter Zeitstempel einer unabhängigen TSA. Der Python-Client verwendet Primary + 3 Alternativen (DFN, DigiCert, GlobalSign, Sectigo) mit automatischem Failover. Bei Status UNAVAILABLE liegt kein TSA-Zeitnachweis vor. Dieser JavaScript-Bericht enthält keinen Token.' },
      { element: 'Generated (CET/CEST)', proves: 'Systemzeit des Computers, der den Report erstellt hat' },
    ],
  });
  small(layout, 'Technische Bedeutung: Ein erfolgreich verifizierter RFC-3161-Token bindet den im Token enthaltenen Message Imprint an die von der TSA angegebene Zeit. Lokale Systemzeit und Hardwaredaten sind ergänzende Metadaten und kein unabhängiger Zeitnachweis.');

  layout.heading('WIE KANN DAS GERICHT ODER DIE STAATSANWALTSCHAFT PRÜFEN?', 'section');
  small(layout, 'SCHRITT 1 – Hash-Prüfung: Get-FileHash "[zu_pruefende_Datei]" -Algorithm SHA256 / Vergleich mit dem Hash im Report');
  small(layout, 'SCHRITT 2 – RFC-3161-Prüfung: TSA-Token kryptographisch prüfen; SHA-256 Message Imprint und Nonce mit der Anfrage bzw. dem geprüften Hash vergleichen. Status UNAVAILABLE bedeutet: kein unabhängiger TSA-Zeitnachweis.');
  small(layout, 'SCHRITT 3 – Hardware ID: Lokale Systemkennung nur ergänzend vergleichen; sie ist kein kryptographischer Identitätsnachweis');
  small(layout, 'SCHRITT 4 – Digitale PDF-Signatur (falls vorhanden): Öffnen mit Adobe Acrobat Reader → "Signaturen" / Status: "Die Signatur ist gültig"');

  layout.heading('ZUSAMMENFASSUNG', 'section');
  layout.table({
    columns: [
      { key: 'what', title: 'Was beweist der Report?', weight: 0.3, role: 'regular', size: 7.6 },
      { key: 'how', title: 'Wie wird es geprüft?', weight: 0.36, role: 'regular', size: 7.6 },
      { key: 'basis', title: 'Rechtliche Grundlage', weight: 0.34, role: 'regular', size: 7.6 },
    ],
    rows: [
      { what: 'Byte-Gleichheit zur Referenz', how: 'SHA-256 neu berechnen + vergleichen', basis: 'Technischer Nachweis; Würdigung nach § 286 ZPO' },
      { what: 'Zeitbindung des Message Imprint (nur bei gültigem RFC-3161-Token)', how: 'TSA-Token, Signatur, Imprint und Nonce prüfen', basis: 'Technischer Nachweis; gerichtliche Würdigung nach den Umständen des Einzelfalls' },
      { what: 'OTS / Blockchain (nur bei beigefügtem und geprüftem OTS-Nachweis)', how: 'OTS-Proof, Dateihash und Blockchain-Anker separat verifizieren; ohne OTS-Proof kein OTS-Nachweis', basis: 'Technischer Zusatznachweis; nicht Bestandteil dieses RFC-3161-Berichts, sofern nicht ausdrücklich beigefügt' },
      { what: 'Versicherung an Eides statt (nicht enthalten)', how: 'Nur ein eigenständiger, tatsächlich abgegebener und rechtlich zulässiger Erklärungstext wäre gesondert zu prüfen', basis: '§ 156 StGB nur bei Vorliegen der gesetzlichen Voraussetzungen' },
    ],
  });

  layout.heading('VERFAHRENSHINWEISE FÜR DAS GERICHT', 'section');
  small(layout, '1. Dieses Begleitdokument erläutert die reproduzierbaren technischen Prüfschritte des separat erzeugten Hash Reports.');
  small(layout, '2. Die konkrete Beweiswürdigung bleibt dem zuständigen Gericht anhand des gesamten Verfahrensinhalts vorbehalten.');
  small(layout, '3. Bei Widerspruch sollte das Gericht:');
  small(layout, '   • Einen forensischen EDV-Sachverständigen bestellen;');
  small(layout, '   • Die oben genannten technischen Prüfungen durchführen;');
  small(layout, '   • Die Grundsätze des § 286 ZPO zur freien Beweiswürdigung anwenden.');
  small(layout, 'Hinweis: Dieses Begleitdokument ist keine gerichtliche Bewertung und keine Vorgabe für die Beweiswürdigung.');

  layout.heading('ABSCHLIEßENDE ERKLÄRUNG', 'section');
  small(layout, 'Dieses Dokument dient dazu, das Gericht und die Staatsanwaltschaft bei der korrekten rechtlichen und technischen Bewertung des beigefügten SHA-256-Hash-Reports zu unterstützen. Es enthält die erforderlichen rechtlichen Grundlagen und technischen Anweisungen, damit die enthaltenen kryptographischen Angaben unabhängig nachvollzogen und im jeweiligen Verfahren sachgerecht gewürdigt werden können.');
  small(layout, `Erzeugt am ${context.generatedAt} ${context.timezone} für Report ${context.reportId}.`);
  return layout;
});
/* ------------------------------------------------------------------ */
/* TEXT CHECKSUMS appendix                                             */
/* ------------------------------------------------------------------ */

define('text_checksums', (layout, context) => {
  const checksums = context.checksums || {};
  const identity = layout.identity || {};
  const document = checksums.document || {};
  const pages = checksums.pages || [];
  const scopePages = checksums.scope && Number.isFinite(checksums.scope.pageCount)
    ? checksums.scope.pageCount
    : pages.length;

  layout.pageBreak();
  layout.heading(identity.combined_appendix_title || 'TEXT CHECKSUMS', 'section');
  small(layout, identity.document_appendix_scope
    || 'Scope: whole file = report pages + embedded PDF pages; appendices and footers excluded.');
  small(layout, identity.document_appendix_encoding
    || 'Encoding: UTF-8; NFC; LF; strip; drawn text order.');
  small(layout, identity.document_appendix_framing
    || 'Page framing: 8-byte big-endian length followed by each page text.');
  small(layout, String(identity.document_appendix_page_count || 'Included report and source pages: {page_count}')
    .replace('{page_count}', String(scopePages)));

  layout.heading(identity.combined_file_heading || 'FILE TEXT', 'section');
  propertyTable(layout, ALL_TEXT_ALGORITHMS.map((label) => ({
    property: label,
    value: displayDigest(document[label] || ''),
  })));

  layout.heading(identity.combined_pdf_heading || 'PDF TEXT', 'section');
  small(layout, 'Per-page values over the same framing, one digest per report page. '
    + 'The appendix itself is outside the scope, so no value hashes its own page.');
  layout.table({
    columns: [
      { key: 'page', title: 'Page', weight: 0.11, role: 'bold', size: 8, align: 'RIGHT' },
      {
        key: 'sha256', title: 'SHA-256', weight: 0.58, role: 'monospace', size: 7, leading: 10, chunk: 64,
      },
      { key: 'md5', title: 'MD5', weight: 0.31, role: 'monospace', size: 6.4, leading: 9, chunk: 32 },
    ],
    rows: pages.map((page) => ({
      page: String(page.index),
      sha256: displayDigest((page.digests || {})['SHA-256'] || ''),
      md5: displayDigest((page.digests || {})['MD5'] || ''),
    })),
  });

  layout.gap(4);
  small(layout, identity.appendix_note_page_values
    || 'Individual page values: first six algorithms appear in report-page footers.');
  small(layout, identity.appendix_note_all_algorithms
    || 'All eleven digest algorithms are listed in this appendix and manifest.');
  small(layout, identity.appendix_note_scope
    || 'This checksum appendix is excluded from the text checksum scope.');
  small(layout, `Algorithms in this appendix: ${ALL_TEXT_ALGORITHMS.join(', ')}; footer algorithms: ${PAGE_TEXT_ALGORITHMS.join(', ')}.`);
  return layout;
});

/* ------------------------------------------------------------------ */
/* Embedded source PDF evidence                                        */
/* ------------------------------------------------------------------ */

define('source_pdf_evidence', (layout, context) => {
  const embedded = context.embeddedPdf;
  if (!embedded) return layout;
  // `reportPages` is settled by the composition fixed-point in generate.mjs, so the
  // printed page number is the one the published file really has.
  const reportPages = Number(embedded.reportPages) || 0;
  const firstSourcePage = embedded.position === 'before'
    ? '1'
    : (reportPages ? String(reportPages + 1) : 'first page after the report pages');
  layout.pageBreak();
  layout.heading('EMBEDDED SOURCE PDF:', 'section');
  layout.keyValues([
    ['Source file', embedded.name || embedded.source || ''],
    ['Source SHA-256', displayDigest(embedded.sha256 || '')],
    ['Source pages', String(embedded.pages ?? '')],
    ['Attachment name', embedded.attachment || ''],
    ['Attachment SHA-256', displayDigest(embedded.attachmentSha256 || '')],
    ['Attachment mode', 'byte-for-byte /EmbeddedFiles attachment, no re-encoding'],
    ['Page order', embedded.position === 'before'
      ? (embedded.reportPages
        ? `source pages precede the ${embedded.reportPages} report page(s)`
        : "source pages precede this report's pages")
      : (embedded.reportPages
        ? `source pages follow the ${embedded.reportPages} report page(s)`
        : "source pages are appended after this report's pages")],
    ['First source page in file', firstSourcePage],
    ['Signature inventory', embedded.auditStatus || 'not recorded'],
  ]);
  small(layout, 'The source pages are included unchanged; the footer strip of a source page is '
    + 'drawn in an extra bottom band so no original glyph is covered. The attachment and the '
    + 'visible pages are the same bytes, so a reader can extract the original file and compare '
    + 'it with the digest above.');
  small(layout, 'The signature inventory reports which signature objects exist in the source file. '
    + 'It does not validate signatures, trust chains, revocation or eIDAS qualification.');
  return layout;
});

/* ------------------------------------------------------------------ */
/* Volume / folder breakdown                                           */
/* ------------------------------------------------------------------ */

define('volume_breakdown', (layout, context) => {
  const files = context.files || [];
  if (!files.length) return layout;
  const groups = new Map();
  for (const file of files) {
    const name = String(file.name || file.path || '');
    const cut = name.lastIndexOf('/');
    const folder = cut > 0 ? name.slice(0, cut) : '.';
    const entry = groups.get(folder) || { folder, files: 0, bytes: 0 };
    entry.files += 1;
    entry.bytes += Number(file.size_bytes) || 0;
    groups.set(folder, entry);
  }
  const ordered = [...groups.values()].sort((a, b) => (a.folder < b.folder ? -1 : a.folder > b.folder ? 1 : 0));
  const duplicateNames = new Set();
  const seen = new Map();
  for (const file of files) {
    const base = String(file.name || file.path || '').split('/').pop();
    if (seen.has(base)) duplicateNames.add(base);
    seen.set(base, true);
  }
  layout.pageBreak();
  layout.heading('VOLUME BREAKDOWN:', 'section');
  layout.table({
    columns: [
      { key: 'folder', title: 'Folder', weight: 0.62, role: 'regular', size: 7.4 },
      { key: 'files', title: 'Files', weight: 0.14, role: 'regular', size: 7.4, align: 'RIGHT' },
      { key: 'size', title: 'Size (KB)', weight: 0.24, role: 'regular', size: 7.4, align: 'RIGHT' },
    ],
    rows: ordered.map((entry) => ({
      folder: entry.folder,
      files: String(entry.files),
      size: (entry.bytes / 1024).toFixed(3),
    })),
  });
  layout.keyValues([
    ['Folders in scope', String(ordered.length)],
    ['Files in scope', String(files.length)],
    ['Recursive selection', context.recursive ? 'yes' : 'no'],
    ['Aggregated document proof (SHA-256)', String(context.documentProof || '').toUpperCase()],
  ]);
  if (duplicateNames.size) {
    small(layout, `Base names that occur more than once: ${[...duplicateNames].sort().join(', ')}. `
      + 'The per-file digest is the disambiguator; the aggregation order is the displayed relative path.');
  }
  return layout;
});

export const SHARED_SECTIONS = Object.freeze(sectionIds());