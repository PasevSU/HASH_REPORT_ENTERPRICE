"""Non-mutating signature inspection before PDF composition and timestamping."""
from pathlib import Path

def inspect_pdf(path):
    from pypdf import PdfReader
    from pypdf.generic import DictionaryObject
    reader=PdfReader(str(path),strict=True)
    if reader.is_encrypted:
        raise ValueError('Encrypted PDF: signature inspection unavailable')
    signatures=[]
    seen=set()
    def add_signature(value, field_name='', source='acroform'):
        obj=value.get_object() if hasattr(value,'get_object') else value
        if not isinstance(obj,DictionaryObject): return
        if '/ByteRange' not in obj and '/SubFilter' not in obj: return
        # One signature is reachable through both /AcroForm and /Perms, so it must
        # count once. Deduplicate on the signature content: a transient proxy id
        # may be recycled by the interpreter and would silently drop a signature.
        marker=(str(obj.get('/ByteRange','')), str(obj.get('/SubFilter','')),
                str(obj.get('/M','')), str(obj.get('/Filter','')), str(obj.get('/Contents','')))
        if marker in seen:return
        seen.add(marker)
        raw_range=obj.get('/ByteRange',[])
        try:byte_range=[int(part) for part in raw_range]
        except (TypeError,ValueError):byte_range=[]
        signatures.append({
            'field_name':field_name,
            'source':source,
            'type':str(obj.get('/Type','')),
            'subfilter':str(obj.get('/SubFilter','')),
            'byte_range':byte_range,
            'signing_time':str(obj.get('/M','')),
            'signer_name':str(obj.get('/Name','')),
            'cryptographic_validation':'NOT_PERFORMED',
        })
    def visit(field, parents=()):
        obj=field.get_object()
        if not isinstance(obj,DictionaryObject):return
        current=parents+((str(obj.get('/T','')), ) if obj.get('/T') else ())
        value=obj.get('/V')
        if value:add_signature(value,'.'.join(current))
        for child in obj.get('/Kids',[]): visit(child,current)
    fields=reader.trailer['/Root'].get('/AcroForm')
    if fields:
        for field in fields.get_object().get('/Fields',[]):visit(field)
    perms=reader.trailer['/Root'].get('/Perms')
    if perms:
        permissions=perms.get_object()
        for key in ('/DocMDP','/DocTimeStamp'):
            if permissions.get(key):add_signature(permissions[key],source='catalog'+key)
    return {
        'signed':bool(signatures),
        'signatures':signatures,
        'pages':len(reader.pages),
        'verification_status':'SIGNATURES_PRESENT_NOT_CRYPTOGRAPHICALLY_VALIDATED' if signatures else 'NO_SIGNATURES_DETECTED',
        'scope_note':'Signature dictionaries are inventoried only; cryptographic integrity, trust, revocation, and qualification are not verified here.',
    }
