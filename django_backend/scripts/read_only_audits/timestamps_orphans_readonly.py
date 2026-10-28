from dotenv import dotenv_values
import MySQLdb, json, hashlib, re
cfg={k:v for k,v in dotenv_values(r'C:\Users\.MSI\Downloads\StokIt Backend\django_backend\.env').items() if v is not None}
c=MySQLdb.connect(host=cfg.get('DB_HOST','127.0.0.1'),port=int(cfg.get('DB_PORT','3306')),user=cfg.get('DB_USER',''),password=cfg.get('DB_PASSWORD',''),database=cfg.get('DB_NAME',''),connect_timeout=8,charset='utf8mb4')
try:
 with c.cursor() as q:
  q.execute('SET SESSION TRANSACTION READ ONLY'); q.execute('SELECT DATABASE(),VERSION(),NOW(6)');db,ver,scan_time=q.fetchone()
  if db!='stokit_legacy_test': raise RuntimeError('wrong database')
  q.execute("SELECT TABLE_NAME,COLUMN_NAME,DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND DATA_TYPE IN ('date','datetime','timestamp') AND (COLUMN_NAME LIKE '%%created%%' OR COLUMN_NAME LIKE '%%updated%%' OR COLUMN_NAME LIKE '%%modified%%' OR COLUMN_NAME LIKE '%%changed%%' OR COLUMN_NAME LIKE '%%time%%' OR COLUMN_NAME LIKE '%%date%%') ORDER BY TABLE_NAME,ORDINAL_POSITION",(db,))
  ts_cols=q.fetchall(); ts_summary=[]
  for t,col,typ in ts_cols:
   qt='`'+t.replace('`','``')+'`'; qc='`'+col.replace('`','``')+'`'
   q.execute(f'SELECT COUNT({qc}),MIN({qc}),MAX({qc}) FROM {qt}')
   n,lo,hi=q.fetchone()
   ts_summary.append({'table':t,'column':col,'type':typ,'nonnull_count':int(n),'min':lo.isoformat(sep=' ') if hasattr(lo,'isoformat') and hasattr(lo,'hour') else (lo.isoformat() if hasattr(lo,'isoformat') else lo),'max':hi.isoformat(sep=' ') if hasattr(hi,'isoformat') and hasattr(hi,'hour') else (hi.isoformat() if hasattr(hi,'isoformat') else hi)})
  q.execute("SELECT TABLE_NAME,CONSTRAINT_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME,ORDINAL_POSITION FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME IS NOT NULL ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION",(db,))
  raw=q.fetchall(); groups={}
  for t,n,col,rt,rc,pos in raw:
   x=groups.setdefault((t,n,rt),{'columns':[],'ref_columns':[]});x['columns'].append(col);x['ref_columns'].append(rc)
  orphan=[]
  for (t,n,rt),v in groups.items():
   # Only single-column FKs; composite checks need tuple-aware join logic.
   if len(v['columns'])!=1: continue
   col,rc=v['columns'][0],v['ref_columns'][0]
   q.execute(f'SELECT COUNT(*) FROM `{t}` c LEFT JOIN `{rt}` p ON c.`{col}`=p.`{rc}` WHERE c.`{col}` IS NOT NULL AND p.`{rc}` IS NULL')
   orphan.append({'table':t,'constraint':n,'column':col,'referenced_table':rt,'referenced_column':rc,'orphan_count':int(q.fetchone()[0])})
  q.execute("SELECT TRIGGER_NAME,EVENT_OBJECT_TABLE,ACTION_TIMING,EVENT_MANIPULATION,ACTION_STATEMENT FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s",(db,))
  live_trigs=[]
  for name,timing_table,timing,event,body in q.fetchall():
   live_trigs.append({'name':name,'table':timing_table,'timing':timing,'event':event,'body_sha256':hashlib.sha256(re.sub(r'\s+',' ',body.strip()).lower().encode()).hexdigest()})
  report={'scan_time_db':str(scan_time),'database':db,'server':ver,'timestamp_columns':ts_summary,'declared_single_column_fk_orphan_checks':orphan,'trigger_body_fingerprints':live_trigs}; out=__import__('pathlib').Path(r'C:\\Users\\.MSI\\Downloads\\StokIt Backend\\docs\\STOKIT_LIVE_TIMESTAMP_ORPHAN_READONLY.json'); out.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8'); print(json.dumps({'report_path':str(out),'scan_time_db':str(scan_time),'database':db,'server':ver,'timestamp_columns_checked':len(ts_summary),'declared_single_column_fk_checks':len(orphan),'orphan_checks_nonzero':sum(1 for x in orphan if x['orphan_count']),'trigger_count':len(live_trigs),'trigger_names':[x['name'] for x in live_trigs]},indent=2))
finally:c.close()


