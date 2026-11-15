import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import zlib from 'node:zlib';
import os from 'node:os';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const execFileAsync=promisify(execFile);
import {timestampPdf,extractTimestamps,verifyTimestamp,SimpleTrustStore} from 'pdf-rfc3161';

const a=Object.fromEntries(process.argv.slice(2).reduce((x,v,i,z)=>i%2?x:(x.push([v.replace(/^--/,''),z[i+1]]),x),[]));
if(!a.input||!a.output||!a.policy||!a.audit) throw Error('usage --input PDF --output PDF --policy JSON --audit JSON');
const cfg=JSON.parse(await fs.readFile(a.policy,'utf8')), pol=cfg.rfc3161;
const projectRoot=path.resolve(path.dirname(a.policy),'..');
if(pol.require_qualified_stop===true){
 const listCfg=pol.trusted_list_validation||{},requiredList=['lotl_file','lotl_signer_certificate_file','lotl_signer_sha256','member_tsl_file','member_tsl_url'];
 const missing=requiredList.filter(k=>!listCfg[k]);
 if(missing.length)throw Error(`QUALIFIED_TIMESTAMP_VALIDATION_FAILED: trusted-list validation is not provisioned (${missing.join(', ')})`);
 const qualified=(pol.stop||[]).find(p=>p.qualified===true);
 if(!qualified)throw Error('QUALIFIED_TIMESTAMP_VALIDATION_FAILED: qualified STOP provider is not configured');
 if(qualified.service_access_confirmed!==true)throw Error('QUALIFIED_TIMESTAMP_VALIDATION_FAILED: contracted qualified TSA access is not confirmed');
 if(qualified.auth&&qualified.auth!=='none')throw Error(`QUALIFIED_TIMESTAMP_VALIDATION_FAILED: authentication mode "${qualified.auth}" is unsupported`);
 if(!(qualified.trust_root_files||[]).length)throw Error('QUALIFIED_TIMESTAMP_VALIDATION_FAILED: no CA trust anchor configured');
}
let pdf=new Uint8Array(await fs.readFile(a.input));
if(pol.require_qualified_stop===true){if((pol.mode||'DUAL-STAMP')!=='DUAL-STAMP')throw Error('qualified STOP requires DUAL-STAMP mode');if(!(pol.stop||[]).some(p=>p.qualified===true))throw Error('qualified STOP is required but no qualified provider is configured');}
for(const p of [...(pol.start||[]),...(pol.stop||[])])if(p.auth&&p.auth!=='none')throw Error(`${p.name||'TSA'}: authentication mode "${p.auth}" is not supported by the RFC 3161 bridge`);
// Fail closed BEFORE contacting any TSA: never append a second START/STOP pair.
// A previously sealed PDF must be verified, not timestamped again.
// A real signature is a ByteRange paired with a /Contents hex string in the same PDF object;
// a bare ByteRange mention elsewhere must not reject an unsigned PDF.
function signatureByteRanges(s){const out=[],re=/\/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]/g;let m;while((m=re.exec(s))){const start=Math.max(0,s.lastIndexOf('obj',m.index)),endobj=s.indexOf('endobj',m.index),obj=s.slice(start,endobj<0?s.length:endobj),c=obj.match(/\/Contents\s*<([0-9A-Fa-f\s]+)>/);if(c)out.push({byteRange:m.slice(1,5).map(Number),contentsHex:c[1]})}return out}
const existingPdfText=Buffer.from(pdf).toString('latin1');
const priorDocStamps=(existingPdfText.match(/\/Type\s*\/DocTimeStamp\b/g)||[]).length;
const priorRfc3161=(existingPdfText.match(/\/SubFilter\s*\/ETSI\.RFC3161\b/g)||[]).length;
if(priorDocStamps||priorRfc3161||signatureByteRanges(existingPdfText).length) {
 throw Error(`INPUT_ALREADY_SIGNED: ${priorDocStamps} DocTimeStamp objects, ${priorRfc3161} RFC3161 subfilters; refusing to append timestamps. Select an unsigned source report, or use the independent verification workflow.`);
}
const events=[], applied=[];
const digest=(b,alg='sha256')=>crypto.createHash(alg).update(b).digest('hex');
const resolveFile=f=>path.isAbsolute(f)?f:path.resolve(path.dirname(a.policy),'..',f);
function pemToDer(bytes){const s=Buffer.from(bytes).toString('utf8');if(!s.includes('-----BEGIN CERTIFICATE-----'))return new Uint8Array(bytes);const m=s.match(/-----BEGIN CERTIFICATE-----([\s\S]*?)-----END CERTIFICATE-----/);if(!m)throw Error('invalid PEM certificate');return new Uint8Array(Buffer.from(m[1].replace(/\s+/g,''),'base64'));}
async function providerCertificates(provider){const out=[];for(const k of ['trust_root_files','intermediate_certificate_files','embed_certificate_files'])for(const f of provider[k]||[])out.push(pemToDer(await fs.readFile(resolveFile(f))));if(provider.trusted_list_service_certificate_file)out.push(pemToDer(await fs.readFile(resolveFile(provider.trusted_list_service_certificate_file))));return out;}
async function store(provider){const s=new SimpleTrustStore();const roots=[];for(const f of provider.trust_root_files||[])roots.push(pemToDer(await fs.readFile(resolveFile(f))));if(!roots.length)throw Error(`${provider.name}: no CA trust anchor configured; the TSA service identity certificate is not a CA trust anchor`);if(provider.qualified===true){if(!provider.policy_oid||!/^(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*))+$/u.test(provider.policy_oid))throw Error(`${provider.name}: qualified provider requires a valid policy_oid`);if(provider.trusted_list_service_status!=='granted'||!provider.trusted_list_service_certificate_sha256)throw Error(`${provider.name}: active Trusted List service status and certificate pin are required`);if(!provider.trusted_list_service_certificate_file)throw Error(`${provider.name}: Trusted List service identity certificate file is not configured`);const serviceCert=pemToDer(await fs.readFile(resolveFile(provider.trusted_list_service_certificate_file)));const pin=provider.trusted_list_service_certificate_sha256.replaceAll(':','').toUpperCase();if(digest(Buffer.from(serviceCert)).toUpperCase()!==pin)throw Error(`${provider.name}: service identity certificate does not match the Trusted List fingerprint`)}for(const c of roots)s.addCertificate(c);return s;}
async function verifyOne(ts,p,pdfBytes){if(p.qualified===true&&ts?.info?.policy!==p.policy_oid)throw Error(`${p.name}: timestamp policy mismatch (expected ${p.policy_oid}, found ${ts?.info?.policy||'missing'})`);/* Qualified chains are independently checked by OpenSSL and the LOTL/TSL validator; SimpleTrustStore cannot model an untrusted intermediate. */const trust=p.qualified===true?undefined:await store(p);const v=await verifyTimestamp(ts,{...(trust?{trustStore:trust}:{}),pdf:pdfBytes,strictESSValidation:pol.strict_ess!==false,requireTimestampingEKU:true,requireCertValidAtGenTime:true});if(v?.verified!==true)throw Error(`${p.name}: verification failed: ${v?.verificationError||'no verifier detail returned'}`);if(p.qualified===true&&v?.info?.policy!==p.policy_oid)throw Error(`${p.name}: verified token policy mismatch (expected ${p.policy_oid}, found ${v?.info?.policy||'missing'})`);return v;}
// Configured semantic checks (ESS, TSA EKU, validity at genTime) are mandatory: failing to extract or verify is fatal.
async function verifyExtractedMandatory(bytes,expected,providers,label){let extracted;try{extracted=await extractTimestamps(bytes)}catch(e){throw Error(`${label}: library timestamp extraction failed, mandatory semantic verification impossible: ${String(e?.message||e)}`)}if(!Array.isArray(extracted)||extracted.length<expected)throw Error(`${label}: library extractor found ${Array.isArray(extracted)?extracted.length:0} timestamp(s), expected at least ${expected}; mandatory semantic verification impossible`);const tail=extracted.slice(extracted.length-providers.length);for(let i=0;i<providers.length;i++)await verifyOne(tail[i],providers[i],bytes);return extracted}
function endpointKey(u){try{const x=new URL(u);return x.host.toLowerCase()+x.pathname.replace(/\/+$/,'')}catch{return String(u||'').toLowerCase()}}
function sameProvider(x,y){return String(x.name||'').trim().toLowerCase()===String(y.name||'').trim().toLowerCase()||endpointKey(x.url)===endpointKey(y.url)}
function isoGenTime(value){return value instanceof Date?value.toISOString():String(value||'')}
// Signer identity = SHA-256 of configured embed_certificate_files (TSA leaf); shared generic roots/intermediates are deliberately ignored.
async function signerHashes(p){return Promise.all((p.embed_certificate_files||[]).map(async f=>digest(pemToDer(await fs.readFile(resolveFile(f))))))}
function requireHttps(p){let u;try{u=new URL(p.url)}catch{throw Error(`${p.name}: TSA endpoint is not a valid URL`)}if(!/^https?:$/.test(u.protocol))throw Error(`${p.name}: TSA endpoint must be an http(s) URL`)}
function extractRawDocTimeStamps(bytes){
 const s=Buffer.from(bytes).toString('latin1'), out=[]; 
 for(const sig of signatureByteRanges(s)){const br=sig.byteRange;let hex=sig.contentsHex.replace(/\s+/g,'').replace(/(?:00)+$/,'');if(hex.length%2)hex=hex.slice(0,-1);const token=Buffer.from(hex,'hex');const signed=Buffer.concat([Buffer.from(bytes).subarray(br[0],br[0]+br[1]),Buffer.from(bytes).subarray(br[2],br[2]+br[3])]);out.push({byteRange:br,token,signed,tokenSha256:digest(token),signedSha256:digest(signed)});} return out;
}
async function opensslVerifyRaw(raw,provider){
 const openssl=process.env.CHRONOSEAL_OPENSSL||cfg.tools?.openssl||'openssl'; const td=await fs.mkdtemp(path.join(os.tmpdir(),'chronoseal-rfc3161-')); try{
  const token=path.join(td,'token.tsr'), data=path.join(td,'signed.bin'), ca=path.join(td,'ca.pem'), untrusted=path.join(td,'untrusted.pem'); await fs.writeFile(token,raw.token);await fs.writeFile(data,raw.signed);
  const roots=[];for(const f of provider.trust_root_files||[])roots.push(await fs.readFile(resolveFile(f)));if(!roots.length)throw Error(`${provider.name}: no CA trust anchor configured for independent OpenSSL RFC3161 verification`);await fs.writeFile(ca,Buffer.concat(roots.map((x,i)=>Buffer.concat([x,Buffer.from(i?'\n':'')]))));
  const inter=[];for(const f of [...(provider.intermediate_certificate_files||[]),...(provider.embed_certificate_files||[])])inter.push(await fs.readFile(resolveFile(f)));if(inter.length)await fs.writeFile(untrusted,Buffer.concat(inter.map(x=>Buffer.concat([x,Buffer.from('\n')]))));
  const args=['ts','-verify','-token_in','-in',token,'-data',data,'-CAfile',ca];if(inter.length)args.push('-untrusted',untrusted);
  let r;
  if(process.platform==='win32'&&/\.(?:cmd|bat)$/i.test(openssl)){
   const wrapper=path.join(td,'run-openssl.cmd'),env={...process.env,CHRONOSEAL_OPENSSL:openssl};
   const commandArgs=args.map((value,index)=>{const key=`CHRONOSEAL_OPENSSL_ARG_${index}`;env[key]=String(value);return `"%${key}%"`;});
   await fs.writeFile(wrapper,`@echo off\r\n"%CHRONOSEAL_OPENSSL%" ${commandArgs.join(' ')}\r\nexit /b %ERRORLEVEL%\r\n`,{encoding:'utf8'});
   r=await execFileAsync(process.env.ComSpec||'cmd.exe',['/d','/s','/c',`call "${wrapper}"`],{timeout:30000,windowsHide:true,maxBuffer:1024*1024,env,windowsVerbatimArguments:true});
  }else{
   r=await execFileAsync(openssl,args,{timeout:30000,windowsHide:true,maxBuffer:1024*1024});
  }
  if(!/Verification:\s*OK/i.test((r.stdout||'')+(r.stderr||'')))throw Error('OpenSSL RFC3161 verification did not report OK');return {verified:true,engine:'openssl ts -verify',token_sha256:raw.tokenSha256,signed_sha256:raw.signedSha256};
 }finally{await fs.rm(td,{recursive:true,force:true}).catch(()=>{})}
}
async function validateQualifiedStop(raw,provider,genTime){
 const python=process.env.CHRONOSEAL_PYTHON||cfg.tools?.python||cfg.generator?.python||'python',temp=await fs.mkdtemp(path.join(os.tmpdir(),'chronoseal-qualified-stop-'));
 const tokenPath=path.join(temp,'token.der');await fs.writeFile(tokenPath,raw.token);
 const script=path.join(projectRoot,'chronoseal','qualified_validation.py');
 try{
  const {stdout,stderr}=await execFileAsync(python,[script,'--token',tokenPath,'--gen-time',String(genTime||''),'--policy',path.resolve(a.policy),'--provider',provider.name,'--evidence',a.evidence?path.resolve(a.evidence):path.dirname(path.resolve(a.audit))],{cwd:projectRoot,timeout:180000,windowsHide:true,maxBuffer:4*1024*1024,env:{...process.env,CHRONOSEAL_OPENSSL:process.env.CHRONOSEAL_OPENSSL||cfg.tools?.openssl||'openssl',PYTHONIOENCODING:'utf-8',PYTHONUTF8:'1'}});
  let result;try{result=JSON.parse(stdout.trim())}catch{throw Error(`qualified evidence validator returned invalid JSON: ${stderr||stdout}`)}
  if(result.status!=='PASS')throw Error('qualified evidence validator did not return PASS');
  const folder=a.evidence?path.resolve(a.evidence):path.dirname(path.resolve(a.audit));
  await fs.writeFile(path.join(folder,'qualified-stop-validation.json'),JSON.stringify(result,null,2));
  return result;
 }catch(e){throw Error(`QUALIFIED_TIMESTAMP_VALIDATION_FAILED: ${String(e?.message||e)}`)}
 finally{await fs.rm(temp,{recursive:true,force:true})}
}

function pdfStructuralSnapshot(bytes){
 const s=Buffer.from(bytes).toString('latin1');
 return {
  docTimeStampObjects:(s.match(/\/Type\s*\/DocTimeStamp\b/g)||[]).length,
  rfc3161SubFilters:(s.match(/\/SubFilter\s*\/ETSI\.RFC3161\b/g)||[]).length,
  byteRanges:signatureByteRanges(s).length,
  contentsEntries:(s.match(/\/Contents\s*</g)||[]).length,
  dss:/\/DSS\b/.test(s), certs:/\/Certs\b/.test(s)
 };
}
function assertStructuralTimestampAdded(before,after){
 const deltas={docTimeStampObjects:after.docTimeStampObjects-before.docTimeStampObjects,rfc3161SubFilters:after.rfc3161SubFilters-before.rfc3161SubFilters,byteRanges:after.byteRanges-before.byteRanges,contentsEntries:after.contentsEntries-before.contentsEntries};
 if(deltas.docTimeStampObjects<1||deltas.rfc3161SubFilters<1||deltas.byteRanges<1||deltas.contentsEntries<1)throw Error(`PDF structural DocTimeStamp invariant failed: ${JSON.stringify(deltas)}`);
 return {verified:true,deltas,after};
}
function assertPdfDss(bytes){const x=pdfStructuralSnapshot(bytes);if(!x.dss)throw Error('PDF DSS dictionary missing after LTV embed');if(!x.certs)throw Error('PDF DSS /Certs entry missing after LTV embed');return {dss:true,certs:true};}
function x509Metadata(bytes){
 const der=Buffer.from(bytes), x=new crypto.X509Certificate(der);
 return {sha256:digest(der),bytes:der.length,subject:x.subject,issuer:x.issuer,serial_number:x.serialNumber,valid_from:x.validFrom,valid_to:x.validTo,ca:x.ca,fingerprint_sha256:x.fingerprint256,key_usage_oids:x.keyUsage||[],subject_alt_name:x.subjectAltName||null,authority_info_access:x.infoAccess||null};
}
function inventoryLTV(ltv={}){return {certificates:(ltv.certificates||[]).map(x=>x509Metadata(Buffer.from(x))),ocspResponses:(ltv.ocspResponses||[]).map(x=>({sha256:digest(Buffer.from(x)),bytes:Buffer.from(x).length})),crls:(ltv.crls||[]).map(x=>({sha256:digest(Buffer.from(x)),bytes:Buffer.from(x).length}))};}
function latestDssCertRefs(bytes){
 const s=Buffer.from(bytes).toString('latin1');let pos=s.lastIndexOf('/Type /DSS');if(pos<0)pos=s.lastIndexOf('/Type\n/DSS');if(pos<0)throw Error('final PDF DSS dictionary not found for physical certificate audit');
 const tail=s.slice(pos,pos+12000),m=tail.match(/\/Certs\s*\[([^\]]+)\]/);if(!m)throw Error('final PDF DSS /Certs array not found for physical certificate audit');
 const refs=[];for(const x of m[1].matchAll(/(\d+)\s+(\d+)\s+R/g))refs.push([Number(x[1]),Number(x[2])]);if(!refs.length)throw Error('final PDF DSS /Certs array is empty');return refs;
}
function extractObjectStream(bytes,obj,gen){
 const b=Buffer.from(bytes),s=b.toString('latin1'),re=new RegExp(`(?:^|\\n)${obj}\\s+${gen}\\s+obj\\b`,'g');let m,last=-1;while((m=re.exec(s)))last=m.index+(m[0].startsWith('\n')?1:0);if(last<0)throw Error(`PDF object ${obj} ${gen} not found`);
 const streamWord=s.indexOf('stream',last);if(streamWord<0)throw Error(`PDF object ${obj} ${gen} has no stream`);let start=streamWord+6;if(s[start]==='\r'&&s[start+1]==='\n')start+=2;else if(s[start]==='\n'||s[start]==='\r')start+=1;
 const dict=s.slice(last,streamWord),lm=dict.match(/\/Length\s+(\d+)\b/);let raw;if(lm)raw=b.subarray(start,start+Number(lm[1]));else{const end=s.indexOf('endstream',start);if(end<0)throw Error(`PDF object ${obj} ${gen} stream is unterminated`);raw=b.subarray(start,end);}
 if(/\/Filter\s*\/FlateDecode\b/.test(dict))raw=zlib.inflateSync(raw);return Buffer.from(raw);
}
function physicalDssCertificateInventory(bytes){
 const refs=latestDssCertRefs(bytes),certificates=[];for(const [obj,gen] of refs){const der=extractObjectStream(bytes,obj,gen);certificates.push({...x509Metadata(der),pdf_object:`${obj} ${gen} R`});}return {count:certificates.length,certificates};
}
async function saveEvidence(stage,provider,result){const dir=a.evidence?path.resolve(a.evidence):path.dirname(path.resolve(a.audit));await fs.mkdir(dir,{recursive:true});const ltv=result.ltvData||{};const inv=inventoryLTV(ltv);let i=0;for(const c of ltv.certificates||[])await fs.writeFile(path.join(dir,`${stage}-${provider.name}-cert-${++i}.der`),Buffer.from(c));i=0;for(const x of ltv.ocspResponses||[])await fs.writeFile(path.join(dir,`${stage}-${provider.name}-ocsp-${++i}.der`),Buffer.from(x));i=0;for(const x of ltv.crls||[])await fs.writeFile(path.join(dir,`${stage}-${provider.name}-crl-${++i}.der`),Buffer.from(x));await fs.writeFile(path.join(dir,`${stage}-${provider.name}-ltv-inventory.json`),JSON.stringify(inv,null,2));return inv;}
async function assertConfiguredCertificatesPresent(provider,result){const configured=await providerCertificates(provider);const present=new Set((result.ltvData?.certificates||[]).map(x=>digest(Buffer.from(x))));const missing=configured.map(x=>digest(Buffer.from(x))).filter(h=>!present.has(h));if(missing.length)throw Error(`${provider.name}: ${missing.length} configured TSA certificate(s) missing from LTV/DSS candidate material`);return {configured:configured.length,present:(result.ltvData?.certificates||[]).length,allConfiguredPresent:true};}
async function apply(stage,providers){let last;for(const p of providers){try{
 if(p.qualified===true&&stage!=='STOP')throw Error(`${p.name}: qualified provider must be configured for the final STOP timestamp`);if(stage==='STOP'&&pol.require_qualified_stop===true&&p.qualified!==true)throw Error(`${p.name}: final STOP timestamp must use a configured qualified provider`);if(!p.url||p.url.startsWith('REPLACE_'))throw Error('TSA endpoint not configured'); requireHttps(p); await store(p);const supplied=await providerCertificates(p); const beforeStructure=pdfStructuralSnapshot(pdf); const beforeRaw=extractRawDocTimeStamps(pdf);
 // Proof path A is inside pdf-rfc3161 itself: timestampPdf validates the request-bound
 // TSA response (nonce/imprint/CMS/signer/EKU) before it embeds the revision.
 const r=await timestampPdf({pdf,tsa:{url:p.url,hashAlgorithm:pol.hash_algorithm||'SHA-512',timeout:30000,retry:3,retryDelay:1000,...(p.policy_oid?{policy:p.policy_oid}:{})},enableLTV:pol.enable_ltv!==false,revocationData:{certificates:supplied},signatureFieldName:`ChronoSeal_${stage}`,omitModificationTime:true,ignoreEncryption:false});
 const next=r.pdf, afterStructure=pdfStructuralSnapshot(next), structuralProof=assertStructuralTimestampAdded(beforeStructure,afterStructure);
 // Proof path B: raw PDF parser must independently see one additional ByteRange/Contents token.
 const afterRaw=extractRawDocTimeStamps(next);if(afterRaw.length<beforeRaw.length+1)throw Error(`raw PDF timestamp extraction failed after embed: before=${beforeRaw.length}, after=${afterRaw.length}`);const raw=afterRaw.at(-1);if(!raw.token.length)throw Error('raw PDF timestamp token is empty');
 // Proof path C: OpenSSL independently verifies CMS signature, chain and message imprint
 // against the exact bytes selected by the PDF ByteRange.
 const opensslProof=await opensslVerifyRaw(raw,p);
 // Proof path D: library extractor + semantic verification (strict ESS, TSA EKU, valid at genTime) is MANDATORY.
 const extracted=await verifyExtractedMandatory(next,applied.length+1,[p],`${stage}/${p.name}`);const extractor={status:'PASS',before:applied.length,after:extracted.length,error:null,verified:true};
 const qualifiedGenTime=extracted.at(-1)?.info?.genTime||r.timestamp?.genTime||r.timestamp?.info?.genTime;
 const qualifiedValidation=stage==='STOP'&&pol.require_qualified_stop===true?await validateQualifiedStop(raw,p,isoGenTime(qualifiedGenTime)):null;
 const certInvariant=await assertConfiguredCertificatesPresent(p,r), dssInvariant=assertPdfDss(next), ltvInventory=await saveEvidence(stage,p,r);
 events.push({stage,provider:p.name,url:p.url,status:'PASS',verified:true,genTime:r.timestamp?.genTime||r.timestamp?.info?.genTime,qualified_provider:{configured:p.qualified===true,policy_oid:p.policy_oid||null,observed_policy_oid:extracted.at(-1)?.info?.policy||null,trusted_list_service_name:p.trusted_list_service_name||null,trusted_list_service_status:p.trusted_list_service_status||null,trusted_list_service_certificate_sha256:p.trusted_list_service_certificate_sha256||null},qualified_validation:qualifiedValidation,proofs:{library_embed_gate:{verified:true},pdf_structure:structuralProof,raw_pdf:{verified:true,byteRange:raw.byteRange,token_sha256:raw.tokenSha256},openssl:opensslProof,library_extractor:extractor},certificate_embedding:certInvariant,pdf_dss:dssInvariant,ltv_inventory:ltvInventory});
 applied.push({stage,provider:p,rawTokenSha256:raw.tokenSha256});pdf=next;return p;
 }catch(e){last=e;events.push({stage,provider:p.name,url:p.url,status:'FAIL',error:String(e.message||e)})}}throw last||Error('no TSA provider');}
const p1=await apply('START',pol.start||[]);
if((pol.mode||'DUAL-STAMP')==='DUAL-STAMP'){let choices=pol.stop||[];if(pol.require_distinct_providers){const startSigners=await signerHashes(p1);choices=[];for(const x of pol.stop||[]){if(sameProvider(x,p1))continue;const sig=await signerHashes(x);if(sig.some(h=>startSigners.includes(h)))continue;choices.push(x)}}if(!choices.length)throw Error('no distinct STOP provider');await apply('STOP',choices)}
if(pol.require_qualified_stop===true&&!applied.at(-1)?.provider?.qualified)throw Error('qualified STOP timestamp was required but not applied');
await fs.mkdir(path.dirname(a.output),{recursive:true});await fs.writeFile(a.output,pdf);
const reopened=new Uint8Array(await fs.readFile(a.output));
const finalStructure=pdfStructuralSnapshot(reopened);
if(applied.length!==2)throw Error(`dual-stamp invariant failed: expected exactly 2 applied timestamps, got ${applied.length}`);
if(finalStructure.docTimeStampObjects!==2||finalStructure.rfc3161SubFilters!==2||finalStructure.byteRanges<2)throw Error(`final reopened PDF exact dual timestamp invariant failed: ${JSON.stringify(finalStructure)}`);
const finalRaw=extractRawDocTimeStamps(reopened);if(finalRaw.length!==2)throw Error(`final reopened raw timestamp count failed: expected exactly 2, got ${finalRaw.length}`);
if(applied[0].stage!=='START'||applied[1].stage!=='STOP')throw Error(`timestamp order invariant failed: ${applied.map(x=>x.stage).join(' -> ')}`);
if(applied[0].rawTokenSha256===applied[1].rawTokenSha256)throw Error('START and STOP RFC3161 tokens must be distinct');
// Mandatory reopen proof: locate the exact token committed for each stage by SHA-256 and
// independently re-run OpenSSL over its ByteRange-selected bytes from the physical file.
const finalChecks=[];for(const ap of applied){const raw=finalRaw.find(x=>x.tokenSha256===ap.rawTokenSha256);if(!raw)throw Error(`${ap.stage}: committed timestamp token missing after final reopen`);const v=await opensslVerifyRaw(raw,ap.provider);finalChecks.push({stage:ap.stage,provider:ap.provider.name,verified:true,token_sha256:raw.tokenSha256,engine:v.engine});}
const finalExtracted=await verifyExtractedMandatory(reopened,applied.length,applied.map(x=>x.provider),'final reopen');const finalExtractor={status:'PASS',count:finalExtracted.length,error:null};
const finalDss=assertPdfDss(reopened);
const certInventory={};for(const ev of events.filter(x=>x.status==='PASS')){certInventory[ev.stage]={provider:ev.provider,configured:ev.certificate_embedding?.configured||0,embedded_candidate:ev.certificate_embedding?.present||0,certificates:ev.ltv_inventory?.certificates||[]};}
const expectedCertHashes=new Set();for(const ev of events.filter(x=>x.status==='PASS'))for(const c of ev.ltv_inventory?.certificates||[])expectedCertHashes.add(c.sha256);
if(expectedCertHashes.size===0)throw Error('final certificate inventory is empty');
const physicalCerts=physicalDssCertificateInventory(reopened),physicalHashes=new Set(physicalCerts.certificates.map(c=>c.sha256));
const missingPhysical=[...expectedCertHashes].filter(h=>!physicalHashes.has(h));if(missingPhysical.length)throw Error(`final physical DSS certificate coverage failed: ${missingPhysical.length} expected certificate(s) missing`);
for(const c of physicalCerts.certificates){c.stages=Object.entries(certInventory).filter(([,v])=>(v.certificates||[]).some(x=>x.sha256===c.sha256)).map(([stage])=>stage);c.role=c.ca?(c.subject===c.issuer?'TRUST_ANCHOR_ROOT':'INTERMEDIATE_CA'):'TSA_SIGNER_OR_END_ENTITY';}
const qualifiedValidation=events.find(x=>x.stage==='STOP'&&x.status==='PASS')?.qualified_validation;
const qualifiedStopSelected=applied.at(-1)?.stage==='STOP'&&applied.at(-1)?.provider?.qualified===true;
const qualifiedValidationPassed=qualifiedValidation?.status==='PASS';
const audit={schema:'chronoseal.rfc3161-addon/v5.4-certificate-audit',input:a.input,input_sha256:digest(await fs.readFile(a.input)),output:a.output,output_sha256:digest(reopened),timestamps_total:applied.length,extractor_observed_total:finalExtracted.length,qualified_stop_required:pol.require_qualified_stop===true,qualified_stop_profile_selected:qualifiedStopSelected,qualified_stop_profile_verified:qualifiedStopSelected&&qualifiedValidationPassed,qualified_timestamp_status:pol.require_qualified_stop===true?(qualifiedValidationPassed?'VALIDATION_PASS':'NOT_ESTABLISHED'):qualifiedStopSelected?'NOT_ESTABLISHED':'NOT_REQUIRED',qualified_timestamp_status_reason:pol.require_qualified_stop===true?'Independent LOTL/TSL, historical QTSA service status, TSA signer chain and revocation evidence are mandatory and are recorded in qualified-stop-validation.json.':qualifiedStopSelected?'A qualified profile was selected without the court-use validation gate; no qualification is established.':'Qualified STOP validation not required by configuration.',events,pdf_structure:finalStructure,pdf_dss:finalDss,certificate_inventory:certInventory,physical_dss_certificate_inventory:physicalCerts,certificate_embedding:{required:true,all_events_pass:events.filter(x=>x.status==='PASS').every(x=>x.certificate_embedding?.allConfiguredPresent===true),unique_certificate_sha256_count:expectedCertHashes.size,physical_dss_count:physicalCerts.count,physical_coverage_pass:missingPhysical.length===0},verification_paths:{library_embed_gate:'MANDATORY',pdf_structure:'MANDATORY',raw_pdf_byte_range:'MANDATORY',openssl_rfc3161:'MANDATORY',final_reopen_openssl:'MANDATORY',physical_dss_certificate_extraction:'MANDATORY',library_extractor_semantic:'MANDATORY',library_extractor:finalExtractor},final_reverification:{verified:true,count:finalChecks.length,checks:finalChecks},status:'PASS'};
if(!audit.certificate_embedding.all_events_pass||!audit.certificate_embedding.physical_coverage_pass)throw Error('certificate embedding invariant failed');
await fs.writeFile(a.audit,JSON.stringify(audit,null,2));
