import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {verifyPdfTimestamps,SimpleTrustStore} from 'pdf-rfc3161';

const args=process.argv.slice(2);
function option(flag){const i=args.indexOf(flag);return i<0?null:args[i+1]}
const input=option('--input'),output=option('--output'),roots=args.flatMap((x,i)=>x==='--root'?[args[i+1]]:[]);
if(!input||!output||!roots.length){console.error('Usage: node bridge/verify_pdf.mjs --input file.pdf --output audit.json --root trusted.pem [--root other.pem]');process.exit(2)}
const digest=x=>crypto.createHash('sha256').update(x).digest('hex');
const result={schema:'chronoseal.pdf-rfc3161-verification/v1',engine:'pdf-rfc3161',version:'0.2.1',input,trust_anchors:[],timestamps:[],status:'NOT_VERIFIED'};
let code=1;
try {
 const pdf=new Uint8Array(await fs.readFile(input));result.input_sha256=digest(pdf);result.input_bytes=pdf.length;
 const store=new SimpleTrustStore();
 for(const root of roots){const data=await fs.readFile(root);const s=data.toString('utf8');let der=data;if(s.includes('-----BEGIN CERTIFICATE-----')){const match=s.match(/-----BEGIN CERTIFICATE-----([\s\S]*?)-----END CERTIFICATE-----/);if(!match)throw Error('invalid PEM trust anchor');der=Buffer.from(match[1].replace(/\s+/g,''),'base64')}store.addCertificate(new Uint8Array(der));result.trust_anchors.push({sha256:digest(der),path:root})}
 const verified=await verifyPdfTimestamps(pdf,{trustStore:store,strictESSValidation:true,requireTimestampingEKU:true,requireCertValidAtGenTime:true});
 result.timestamps=verified.map((t,i)=>({index:i+1,verified:t.verified===true,verification_error:t.verificationError||null,byte_range:t.byteRange||null,gen_time:t.genTime?.toISOString?.()||t.info?.genTime?.toISOString?.()||null,ocsp_count:t.ocspCount??null,crl_count:t.crlCount??null}));
 result.status=verified.length===0?'NO_TIMESTAMPS':verified.every(t=>t.verified===true)?'PASS':'FAIL';code=result.status==='PASS'?0:1;
}catch(e){result.status='ERROR';result.error=String(e?.message||e)}
await fs.writeFile(output,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({status:result.status,count:result.timestamps.length,audit:output}));process.exitCode=code;
