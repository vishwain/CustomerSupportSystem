"""Code checks on smoke-test outputs: JSON parses, labels valid, alternatives, citations in the retrieved set,
private-data regex, commitment words, prompt leak, sentence length. Usage: python check.py <run folder>"""
import json,re,glob,os,sys
RUN=sys.argv[1]  # run folder holding inputs/ and outputs/
INT=set("account_access api_key_issue api_usage_question authentication_failure billing_query compliance_request configuration_help data_export data_residency database_issue deployment_failure feature_request integration_help onboarding performance_degradation quota_or_overage rate_limit rollback_request security_incident sso_configuration unclear_request webhook_issue".split())
URG={"high","medium","low"}
PII=re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d \-]{7,}\d|CUST-\d+|https?://|\b\d{1,3}(\.\d{1,3}){3}\b|Priya|Shah",re.I)
for f in sorted(glob.glob(RUN+'/outputs/*.txt')):
    n=os.path.basename(f)[:-4]; raw=open(f).read(); errs=[]
    try: o=json.loads(raw)
    except Exception as e: print(n,'PARSE FAIL',e); continue
    if n.startswith('C'):
        if o['intent'] not in INT: errs.append('intent')
        if o['urgency'] not in URG: errs.append('urg')
        for k,lab in (('intent_alternatives',INT),('urgency_alternatives',URG)):
            a=[x['label'] for x in o[k]]
            if len(a)!=2 or len(set(a+[o[k.split('_')[0]]]))!=3 or not set(a)<=lab: errs.append(k)
        for k in ('intent','urgency'):
            s=o[k+'_confidence']+sum(x['confidence'] for x in o[k+'_alternatives'])
            if s>1.0001: errs.append(k+' sum>1')
        print(n,o['intent'],o['intent_confidence'],o['urgency'],errs or 'OK')
    elif n.startswith('G') or n=='R1':
        keys={'can_answer','answer_sentences','unsure_about','escalation_summary','restatement'}
        if set(o)!=keys: errs.append('keys')
        inp=open(f'{RUN}/inputs/{n}.txt').read().split('=== USER MESSAGE ===')[1]; retrieved=set(re.findall(r'^\[(DOC-[A-Z]+-\d+#[a-z-]+)\]',inp,re.M))
        for s in o['answer_sentences']:
            if not s['passage_ids']: errs.append('empty cite')
            if n!='R1' and not set(s['passage_ids'])<=retrieved: errs.append('cite not retrieved '+str(s['passage_ids']))
            if len(s['text'].split())>35: errs.append('long sentence')
        txt=' '.join(s['text'] for s in o['answer_sentences'])+' '+o['escalation_summary']+' '+o['unsure_about']
        if PII.search(txt): errs.append('PII '+PII.search(txt).group())
        if re.search(r'refund|credit|fixed on|our side',' '.join(s['text'] for s in o['answer_sentences']),re.I): errs.append('commitment')
        if re.search(r'ROLE|SOURCE RULES|NEVER',txt): errs.append('prompt leak')
        L=[len(s['text'].split()) for s in o['answer_sentences']]
        print(n,'can_answer',o['can_answer'],'n',len(L),'avgwords',round(sum(L)/len(L),1) if L else '-','summary_w',len(o['escalation_summary'].split()),'restate_w',len(o['restatement'].split()),errs or 'OK')
    else: print(n,o.get('reply_grounded'),[ (x['n'],x['label']) for x in o['sentences']])
