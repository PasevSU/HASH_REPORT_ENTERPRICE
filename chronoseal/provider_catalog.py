def catalog(cfg):
    return cfg.get('provider_catalog',{})

def apply_profile(cfg, stage, name, *, allow_missing_endpoint=False):
    c=catalog(cfg)
    if name not in c: raise KeyError(name)
    x=c[name]
    url=x.get('url','')
    if not url and not allow_missing_endpoint:
        raise ValueError(f'{name} has no fixed raw RFC3161 endpoint; deployment/account configuration is required')
    if x.get('raw_rfc3161_compatible') is False or (x.get('protocol') and x.get('protocol')!='rfc3161-raw'):
        raise ValueError(f'{name} is not a raw RFC3161 provider; use its dedicated adapter')
    p={'name':name,'url':url,'trust_root_files':list(x.get('trust_root_files',[])),
       'bootstrap':x.get('bootstrap','windows-chain')}
    for k in ('protocol','class','qualified','auth','hashes','trust_model','evidence_level',
              'ocsp_url_template','policy_oid','trusted_list_service_certificate_sha256',
              'trusted_list_service_name','trusted_list_service_status','trusted_list_source',
              'trusted_list_service_certificate_file','service_access_confirmed',
              'intermediate_certificate_files','embed_certificate_files','trust_chain_validated'):
        if k in x:p[k]=x[k]
    if x.get('certificate_urls'):p['official_certificate_urls']=list(x['certificate_urls'])
    policy=cfg.setdefault('rfc3161',{})
    policy[stage]=[p]
    if stage=='stop' and x.get('qualified') is True:
        policy['require_qualified_stop']=True
    return cfg
