// XMP packet and document-information helpers (PDF/A identification included).

const esc = (s) => String(s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&apos;');

export const pdfDate = (d) => {
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return 'D:' + d.getUTCFullYear() + p(d.getUTCMonth() + 1) + p(d.getUTCDate())
    + p(d.getUTCHours()) + p(d.getUTCMinutes()) + p(d.getUTCSeconds()) + 'Z';
};

export const xmpDate = (d) => d.toISOString().replace(/\.\d{3}Z$/, 'Z');

export const PDFA = { part: 2, conformance: 'B' };

export function buildXmp(meta) {
  const {
    title, author, subject, keywords, creatorTool, producer,
    createDate, modifyDate, toolVersion = 'ChronoSeal Enterprise 5.6.0',
  } = meta;
  const created = xmpDate(createDate);
  const modified = xmpDate(modifyDate);
  return `<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="${esc(toolVersion)}">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/"
    xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/"
    xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#"
    xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#">
   <dc:title>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">${esc(title)}</rdf:li>
    </rdf:Alt>
   </dc:title>
   <dc:creator>
    <rdf:Seq>
     <rdf:li>${esc(author)}</rdf:li>
    </rdf:Seq>
   </dc:creator>
   <dc:description>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">${esc(subject)}</rdf:li>
    </rdf:Alt>
   </dc:description>
   <dc:subject>
    <rdf:Bag>
     <rdf:li>${esc(keywords)}</rdf:li>
    </rdf:Bag>
   </dc:subject>
   <pdf:Producer>${esc(producer)}</pdf:Producer>
   <pdf:Keywords>${esc(keywords)}</pdf:Keywords>
   <xmp:CreatorTool>${esc(creatorTool)}</xmp:CreatorTool>
   <xmp:CreateDate>${created}</xmp:CreateDate>
   <xmp:ModifyDate>${modified}</xmp:ModifyDate>
   <xmp:MetadataDate>${modified}</xmp:MetadataDate>
   <pdfaid:part>${PDFA.part}</pdfaid:part>
   <pdfaid:conformance>${PDFA.conformance}</pdfaid:conformance>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
`;
}