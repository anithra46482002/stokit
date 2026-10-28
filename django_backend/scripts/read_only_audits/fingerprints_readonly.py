from pathlib import Path
import re, json, hashlib
from datetime import datetime, date, time
from decimal import Decimal, InvalidOperation
from dotenv import dotenv_values
import MySQLdb
from MySQLdb.constants import FIELD_TYPE
DUMP=Path(r'C:\Users\.MSI\Downloads\stokit_sql_work\u144866523_stokitDB.sql')
SQL=DUMP.read_text(encoding='utf-8',errors='replace')

def stmt_end(text,start):
    i=start; q=None; depth=0
    while i<len(text):
        c=text[i]
        if q:
            if c=='\\': i+=2; continue
            if c==q:
                if i+1<len(text) and text[i+1]==q: i+=2; continue
                q=None
            i+=1; continue
        if c in "'\"`": q=c
        elif c=='(': depth+=1
        elif c==')' and depth: depth-=1
        elif c==';' and depth==0: return i+1
        i+=1
    return len(text)

def split_top(text, delimiter=','):
    out=[]; start=0; i=0; q=None; depth=0
    while i<len(text):
        c=text[i]
        if q:
            if c=='\\': i+=2; continue
            if c==q:
                if i+1<len(text) and text[i+1]==q: i+=2; continue
                q=None
            i+=1; continue
        if c in "'\"`": q=c
        elif c=='(': depth+=1
        elif c==')' and depth: depth-=1
        elif c==delimiter and depth==0: out.append(text[start:i].strip()); start=i+1
        i+=1
    out.append(text[start:].strip()); return out

def parse_tuple_tokens(values):
    rows=[]; i=0; start=None; q=None; depth=0
    while i<len(values):
        c=values[i]
        if q:
            if c=='\\': i+=2; continue
            if c==q:
                if i+1<len(values) and values[i+1]==q: i+=2; continue
                q=None
            i+=1; continue
        if c in "'\"`": q=c
        elif c=='(':
            if depth==0: start=i+1
            depth+=1
        elif c==')' and depth:
            depth-=1
            if depth==0 and start is not None:
                rows.append(split_top(values[start:i])); start=None
        elif c==';' and depth==0: break
        i+=1
    return rows

def decode_sql_value(token, column_type):
    t=token.strip()
    if t.upper()=='NULL': return None
    if len(t)>=2 and t[0] in "'\"" and t[-1]==t[0]:
        raw=t[1:-1]; out=[]; i=0
        escapes={'0':'\0','b':'\b','n':'\n','r':'\r','t':'\t','Z':'\x1a','\\':'\\',"'":"'",'"':'"','%':'%','_':'_'}
        while i<len(raw):
            if raw[i]=='\\' and i+1<len(raw): out.append(escapes.get(raw[i+1],raw[i+1])); i+=2; continue
            if raw[i]==t[0] and i+1<len(raw) and raw[i+1]==t[0]: out.append(t[0]); i+=2; continue
            out.append(raw[i]); i+=1
        value=''.join(out)
        base=column_type.lower().split('(')[0].strip()
        try:
            if base in ('tinyint','smallint','mediumint','int','integer','bigint','year'): return int(value) if value!='' else value
            if base in ('decimal','numeric'): return Decimal(value)
            if base in ('float','double','real'): return float(value)
            if base in ('date',) and value not in ('0000-00-00',''): return date.fromisoformat(value)
            if base in ('datetime','timestamp') and value and not value.startswith('0000-00-00'): return datetime.fromisoformat(value.replace(' ','T'))
            if base=='time' and value: return time.fromisoformat(value)
        except (ValueError, InvalidOperation): pass
        return value
    base=column_type.lower().split('(')[0].strip()
    if re.fullmatch(r'-?\d+',t):
        if base in ('decimal','numeric'): return Decimal(t)
        if base in ('float','double','real'): return float(t)
        return int(t)
    if re.fullmatch(r'-?\d+\.\d+',t):
        if base in ('float','double','real'): return float(t)
        return Decimal(t)
    if t.upper().startswith('0X'): return bytes.fromhex(t[2:])
    return t

def fp(columns, values):
    canonical=[]
    for v in values:
        if v is None: canonical.append({'type':'null'})
        elif isinstance(v,bool): canonical.append({'type':'bool','value':v})
        elif isinstance(v,int): canonical.append({'type':'int','value':str(v)})
        elif isinstance(v,Decimal): canonical.append({'type':'decimal','value':format(v,'f')})
        elif isinstance(v,datetime): canonical.append({'type':'datetime','value':v.isoformat(timespec='microseconds')})
        elif isinstance(v,date): canonical.append({'type':'date','value':v.isoformat()})
        elif isinstance(v,time): canonical.append({'type':'time','value':v.isoformat(timespec='microseconds')})
        elif isinstance(v,bytes): canonical.append({'type':'bytes','value':v.hex()})
        elif isinstance(v,float): canonical.append({'type':'float','value':v.hex()})
        elif isinstance(v,str): canonical.append({'type':'str','value':v})
        else: canonical.append({'type':type(v).__name__,'value':str(v)})
    payload=json.dumps({'columns':columns,'values':canonical},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(payload).hexdigest()

# Parse dump INSERTs; values never emitted to stdout or report.
insert_re=re.compile(r'INSERT\s+INTO\s+`([^`]+)`\s*\((.*?)\)\s*VALUES\s*',re.I|re.S)
dump_rows={}; tuple_count=0; statements=0; parse_errors=[]
for m in insert_re.finditer(SQL):
    end=stmt_end(SQL,m.end()-1); stmt=SQL[m.start():end]
    # Find VALUES in the matched statement and parse only the tuple region.
    vm=re.search(r'\bVALUES\b',stmt,re.I)
    if not vm: continue
    columns=[x.strip().strip('`') for x in split_top(m.group(2))]
    rows=parse_tuple_tokens(stmt[vm.end():])
    statements+=1; tuple_count+=len(rows)
    for n,row in enumerate(rows):
        if len(row)!=len(columns):
            parse_errors.append({'table':m.group(1),'row_index':n,'column_count':len(columns),'value_count':len(row)}); continue
        dump_rows.setdefault(m.group(1),[]).append((columns,row))

cfg={k:v for k,v in dotenv_values(r'C:\Users\.MSI\Downloads\StokIt Backend\django_backend\.env').items() if v is not None}
conn=MySQLdb.connect(host=cfg.get('DB_HOST','127.0.0.1'),port=int(cfg.get('DB_PORT','3306')),user=cfg.get('DB_USER',''),password=cfg.get('DB_PASSWORD',''),database=cfg.get('DB_NAME',''),connect_timeout=8,charset='utf8mb4')
summary={}; scan_started=datetime.now().astimezone().isoformat(timespec='seconds')
try:
    with conn.cursor() as cur:
        cur.execute('SET SESSION TRANSACTION READ ONLY')
        cur.execute('SELECT DATABASE(),VERSION()'); db,version=cur.fetchone()
        if db!='stokit_legacy_test': raise RuntimeError('Unexpected source database; refusing')
        cur.execute('SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,ORDINAL_POSITION FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME,ORDINAL_POSITION',(db,))
        colmeta={};
        for t,c,typ,pos in cur.fetchall(): colmeta.setdefault(t,[]).append((c,typ))
        cur.execute("SELECT TABLE_NAME,COLUMN_NAME,SEQ_IN_INDEX FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s AND INDEX_NAME='PRIMARY' ORDER BY TABLE_NAME,SEQ_IN_INDEX",(db,))
        pk={}
        for t,c,pos in cur.fetchall(): pk.setdefault(t,[]).append(c)
        cur.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME',(db,)); live_tables=[r[0] for r in cur.fetchall()]
        live_counts={}
        for t in live_tables:
            cur.execute('SELECT COUNT(*) FROM `'+t.replace('`','``')+'`'); live_counts[t]=int(cur.fetchone()[0])
        for t,rows in dump_rows.items():
            if t not in live_tables or t not in pk or len(pk[t])!=1: continue
            pkcol=pk[t][0]; cols=[x[0] for x in colmeta[t]]; types={x[0]:x[1] for x in colmeta[t]}
            if pkcol not in cols: continue
            ix=cols.index(pkcol)
            dump_by_id={}
            for rowcols, tokens in rows:
                if pkcol not in rowcols: continue
                d={c:decode_sql_value(tokens[i],types.get(c,'')) for i,c in enumerate(rowcols)}
                try: key=int(d[pkcol])
                except (ValueError,TypeError): continue
                dump_by_id[key]=d
            # Select every live column ordered by PK; no values are printed.
            quoted=', '.join('`'+c.replace('`','``')+'`' for c in cols)
            cur.execute('SELECT '+quoted+' FROM `'+t.replace('`','``')+'` ORDER BY `'+pkcol.replace('`','``')+'`')
            live_by_id={}
            for values in cur.fetchall():
                d=dict(zip(cols,values))
                try: key=int(d[pkcol])
                except (ValueError,TypeError): continue
                live_by_id[key]=d
            shared_ids=set(dump_by_id)&set(live_by_id); match=0; mismatch=0; examples=[]
            for key in shared_ids:
                dv=dump_by_id[key]; lv=live_by_id[key]
                # Canonicalize both in the same metadata column order. Keep values private.
                try:
                    dvals=[decode_sql_value(str(dv.get(c)) if not isinstance(dv.get(c),str) else "'"+dv[c].replace('\\','\\\\').replace("'","\\'")+"'",types.get(c,'')) if False else dv.get(c) for c in cols]
                    lvals=[lv.get(c) for c in cols]
                    if fp(cols,dvals)==fp(cols,lvals): match+=1
                    else:
                        mismatch+=1
                        if len(examples)<3: examples.append(key)
                except Exception:
                    mismatch+=1
                    if len(examples)<3: examples.append(key)
            summary[t]={'live_rows':live_counts[t],'dump_tuples':len(rows),'dump_unique_pk':len(dump_by_id),'live_unique_pk':len(live_by_id),'shared_pk':len(shared_ids),'fingerprint_matches':match,'fingerprint_mismatches':mismatch,'mismatch_pk_samples':sorted(examples)}
finally: conn.close()
scan_finished=datetime.now().astimezone().isoformat(timespec='seconds')
report={'status':'PRELIMINARY; fingerprint parser conversion not yet fully validated','scan_started_local':scan_started,'scan_finished_local':scan_finished,'source_database':db,'server_version':version,'live_table_count':len(live_tables),'dump_insert_statements':statements,'dump_tuple_total':tuple_count,'parse_errors_count':len(parse_errors),'parse_errors':parse_errors[:20],'tables':summary,'limitations':['Only single-column integer primary keys compared.','Dump SQL literals are parsed conservatively; fingerprints require validation against representative typed columns.','No row values, password hashes, tokens, or secrets are included.','Source authority is not inferred from fingerprint results.']}
out=Path(r'C:\Users\.MSI\Downloads\StokIt Backend\docs\STOKIT_SOURCE_ROW_FINGERPRINTS_READONLY.json')
out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'report_path':str(out),'scan_started_local':scan_started,'scan_finished_local':scan_finished,'database':db,'server':version,'dump_statements':statements,'dump_tuples':tuple_count,'parse_errors':len(parse_errors),'tables_fingerprinted':len(summary),'total_shared_pk':sum(x['shared_pk'] for x in summary.values()),'fingerprint_matches':sum(x['fingerprint_matches'] for x in summary.values()),'fingerprint_mismatches':sum(x['fingerprint_mismatches'] for x in summary.values()),'limitations':report['limitations']},indent=2))

