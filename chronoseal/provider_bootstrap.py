from pathlib import Path
import subprocess, tempfile, urllib.request, ssl, re, os

NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0

TSA_EKU='1.3.6.1.5.5.7.3.8'

class BootstrapError(RuntimeError): pass

def _run(args, **kw):
    # pythonw.exe has no valid stdin; every helper child gets an explicit one.
    stdin=kw.pop('stdin',subprocess.DEVNULL); flags=kw.pop('creationflags',NO_WINDOW)
    q=subprocess.run(args,capture_output=True,text=True,timeout=kw.pop('timeout',30),
                     stdin=stdin,creationflags=flags,**kw)
    if q.returncode: raise BootstrapError((q.stderr or q.stdout or 'command failed').strip())
    return q

def _download(url, dst):
    req=urllib.request.Request(url,headers={'User-Agent':'ChronoSeal/5.1'})
    with urllib.request.urlopen(req,timeout=30,context=ssl.create_default_context()) as r:
        data=r.read()
    if not data: raise BootstrapError(f'Empty certificate download: {url}')
    Path(dst).write_bytes(data); return Path(dst)

def _cert_ok(openssl, p):
    # Accept PEM or DER; normalize to PEM for bridge/OpenSSL portability.
    for inform in ('PEM','DER'):
        q=subprocess.run([openssl,'x509','-inform',inform,'-in',str(p),'-noout','-subject','-issuer','-serial'],capture_output=True,text=True,
                         stdin=subprocess.DEVNULL,creationflags=NO_WINDOW)
        if q.returncode==0:return inform,q.stdout.strip()
    raise BootstrapError(f'Not a parseable X.509 certificate: {p}')

def _normalize(openssl, src, dst):
    inform,_=_cert_ok(openssl,src)
    _run([openssl,'x509','-inform',inform,'-in',str(src),'-outform','PEM','-out',str(dst)])
    _cert_ok(openssl,dst); return dst

def bootstrap_official_download(root, provider, openssl):
    urls=provider.get('official_certificate_urls') or []
    if not urls: raise BootstrapError(f"{provider.get('name')}: no official certificate URLs configured")
    outdir=Path(root)/'trust'/provider.get('name','provider'); outdir.mkdir(parents=True,exist_ok=True)
    files=[]; details=[]
    for i,url in enumerate(urls,1):
        raw=outdir/f'download-{i}.bin'; pem=outdir/f'certificate-{i}.pem'
        _download(url,raw); _normalize(openssl,raw,pem); raw.unlink(missing_ok=True)
        _,d=_cert_ok(openssl,pem); files.append(str(pem.resolve())); details.append({'url':url,'file':str(pem.resolve()),'x509':d})
    return files,details

def _post_tsa(url, body):
    req=urllib.request.Request(url,data=body,method='POST',headers={'Content-Type':'application/timestamp-query','Accept':'application/timestamp-reply','User-Agent':'ChronoSeal/5.1'})
    with urllib.request.urlopen(req,timeout=30) as r:data=r.read()
    if not data:raise BootstrapError(f'Empty RFC3161 response from {url}')
    return data

def bootstrap_windows_chain(root, provider, openssl):
    if os.name!='nt': raise BootstrapError('Windows certificate-chain bootstrap is only available on Windows')
    url=provider.get('url');
    if not url:raise BootstrapError(f"{provider.get('name')}: TSA URL missing")
    outdir=Path(root)/'trust'/provider.get('name','provider'); outdir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chronoseal_tsa_') as td:
        td=Path(td); data=td/'probe.bin'; req=td/'probe.tsq'; resp=td/'probe.tsr'; token=td/'token.p7b'; bundle=td/'bundle.pem'
        data.write_bytes(b'ChronoSeal RFC3161 trust bootstrap probe')
        _run([openssl,'ts','-query','-data',str(data),'-sha256','-cert','-out',str(req)])
        resp.write_bytes(_post_tsa(url,req.read_bytes()))
        _run([openssl,'ts','-reply','-in',str(resp),'-token_out','-out',str(token)])
        _run([openssl,'pkcs7','-inform','DER','-in',str(token),'-print_certs','-out',str(bundle)])
        text=bundle.read_text(encoding='utf-8',errors='ignore')
        certs=re.findall(r'-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----',text)
        if not certs:raise BootstrapError('TSA response contained no extractable certificates')
        extracted=[]
        for i,c in enumerate(certs,1):
            p=td/f'embedded-{i}.pem';p.write_text(c+'\n',encoding='ascii');extracted.append(p)
        # Find the timestamp signer by EKU using OpenSSL.
        leaf=None
        for p in extracted:
            q=_run([openssl,'x509','-in',str(p),'-noout','-text'])
            if 'Time Stamping' in q.stdout or TSA_EKU in q.stdout:leaf=p;break
        if leaf is None:raise BootstrapError('Could not identify timestamp-signing certificate (EKU timeStamping)')
        ps=td/'build_chain.ps1'; export=td/'chain';export.mkdir()
        ps.write_text(r'''param([string]$Leaf,[string]$Out)
$ErrorActionPreference='Stop'
$c=[System.Security.Cryptography.X509Certificates.X509Certificate2]::new($Leaf)
$ch=[System.Security.Cryptography.X509Certificates.X509Chain]::new()
$ch.ChainPolicy.RevocationMode=[System.Security.Cryptography.X509Certificates.X509RevocationMode]::Online
$ch.ChainPolicy.RevocationFlag=[System.Security.Cryptography.X509Certificates.X509RevocationFlag]::EntireChain
$ch.ChainPolicy.VerificationFlags=[System.Security.Cryptography.X509Certificates.X509VerificationFlags]::NoFlag
$ch.ChainPolicy.UrlRetrievalTimeout=[TimeSpan]::FromSeconds(20)
$ok=$ch.Build($c)
if(-not $ok){$s=($ch.ChainStatus|ForEach-Object {$_.Status.ToString()+': '+$_.StatusInformation}) -join '; '; throw "Windows X509Chain validation failed: $s"}
$i=0
foreach($e in $ch.ChainElements){$i++; [IO.File]::WriteAllBytes((Join-Path $Out ("chain-{0}.cer" -f $i)),$e.Certificate.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert))}
''',encoding='utf-8')
        _run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ps),'-Leaf',str(leaf),'-Out',str(export)],timeout=60)
        files=[];details=[]
        for i,cer in enumerate(sorted(export.glob('chain-*.cer')),1):
            pem=outdir/f'chain-{i}.pem';_normalize(openssl,cer,pem);_,d=_cert_ok(openssl,pem);files.append(str(pem.resolve()));details.append({'source':'Windows X509Chain + live TSA response','file':str(pem.resolve()),'x509':d})
        if not files:raise BootstrapError('Windows chain builder returned no certificates')
        return files,details

def _x509_meta(openssl, cert):
    q=_run([openssl,'x509','-in',str(cert),'-noout','-subject','-issuer','-text'])
    txt=q.stdout
    subject=re.search(r'^subject\s*=\s*(.+)$',txt,re.M)
    issuer=re.search(r'^issuer\s*=\s*(.+)$',txt,re.M)
    is_ca='CA:TRUE' in txt
    return {'subject':subject.group(1).strip() if subject else '', 'issuer':issuer.group(1).strip() if issuer else '', 'is_ca':is_ca, 'self_signed':bool(subject and issuer and subject.group(1).strip()==issuer.group(1).strip()), 'text':txt}

def _write_bundle(dst, files):
    data=b''
    for f in files:
        b=Path(f).read_bytes()
        data += b + (b'\n' if not b.endswith(b'\n') else b'')
    Path(dst).write_bytes(data)

def _validate_chain(openssl, leaf, roots, inter):
    if not leaf or not roots: raise BootstrapError('Cannot validate TSA chain without leaf and root')
    with tempfile.TemporaryDirectory(prefix='chronoseal_chaincheck_') as td:
        td=Path(td); ca=td/'roots.pem'; un=td/'untrusted.pem'; _write_bundle(ca,roots)
        args=[openssl,'verify','-purpose','timestampsign','-CAfile',str(ca)]
        if inter:
            _write_bundle(un,inter); args += ['-untrusted',str(un)]
        args += [str(leaf)]
        q=subprocess.run(args,capture_output=True,text=True,timeout=30,stdin=subprocess.DEVNULL,creationflags=NO_WINDOW)
        if q.returncode: raise BootstrapError((q.stderr or q.stdout or 'TSA chain validation failed').strip())
        return (q.stdout or '').strip()

def _classify_downloaded(openssl, files):
    metas=[_x509_meta(openssl,f) for f in files]
    roots=[f for f,m in zip(files,metas) if m['is_ca'] and m['self_signed']]
    leaves=[f for f,m in zip(files,metas) if not m['is_ca']]
    inter=[f for f,m in zip(files,metas) if m['is_ca'] and not m['self_signed']]
    # Timestamp leaf is preferred; official bundles can contain more than one non-CA cert.
    tsa=[]
    for f,m in zip(files,metas):
        if not m['is_ca'] and ('Time Stamping' in m['text'] or TSA_EKU in m['text']): tsa.append(f)
    if tsa: leaves=tsa + [x for x in leaves if x not in tsa]
    return roots,inter,leaves,metas

def bootstrap_providers(root,cfg,openssl):
    report={'providers':[],'status':'PASS'}
    for stage in ('start','stop'):
        for p in cfg.get('rfc3161',{}).get(stage,[]):
            mode=p.get('bootstrap')
            # Existing material is accepted only when it was chain-qualified by this bootstrap.
            if p.get('trust_root_files') and p.get('trust_chain_validated'):
                report['providers'].append({'stage':stage,'name':p.get('name'),'status':'EXISTING_VALIDATED','trust_roots':p['trust_root_files'],'intermediates':p.get('intermediate_certificate_files',[]),'embed_certificates':p.get('embed_certificate_files',[])})
                continue
            details=[]; validation=''
            if mode=='official-download':
                files,details=bootstrap_official_download(root,p,openssl)
                roots,inter,embed,metas=_classify_downloaded(openssl,files)
                # Do not guess a root from a filename. If the official set is incomplete,
                # use the live TSA token + Windows X509Chain/AIA as an independent recovery path.
                try:
                    if not embed: raise BootstrapError('official bundle has no TSA signer certificate')
                    if not roots: raise BootstrapError('official bundle has no self-signed trust anchor')
                    validation=_validate_chain(openssl,embed[0],roots,inter)
                except Exception as official_error:
                    if os.name!='nt': raise
                    chain_files,chain_details=bootstrap_windows_chain(root,p,openssl)
                    cmeta=[_x509_meta(openssl,f) for f in chain_files]
                    roots=[chain_files[-1]]; inter=chain_files[1:-1]; embed=[chain_files[0]]
                    validation=_validate_chain(openssl,embed[0],roots,inter)
                    details += [{'recovery':'Windows X509Chain/AIA','reason':str(official_error)}] + chain_details
            elif mode=='windows-chain':
                files,details=bootstrap_windows_chain(root,p,openssl)
                roots=files[-1:] if files else []; inter=files[1:-1] if len(files)>2 else []; embed=files[:1]
                validation=_validate_chain(openssl,embed[0],roots,inter)
            else: raise BootstrapError(f"{stage}/{p.get('name')}: no trust bootstrap strategy")
            if not roots: raise BootstrapError(f"{p.get('name')}: bootstrap did not identify a trust anchor")
            p['trust_root_files']=roots; p['intermediate_certificate_files']=inter; p['embed_certificate_files']=embed
            p['trust_chain_validated']=True; p['trust_chain_validation']=validation
            report['providers'].append({'stage':stage,'name':p.get('name'),'status':'BOOTSTRAPPED_VALIDATED','trust_roots':roots,'intermediates':inter,'embed_certificates':embed,'validation':validation,'details':details})
    return report,cfg
