from pathlib import Path
import re,json,importlib.util
from dotenv import dotenv_values
import MySQLdb
base=Path(r'C:\Users\.MSI\Downloads\StokIt Backend')
sql=Path(r'C:\Users\.MSI\Downloads\stokit_sql_work\u144866523_stokitDB.sql').read_text(encoding='utf-8',errors='replace')
spec=importlib.util.spec_from_file_location('mig',str(base/'django_backend/scripts/stokit_pg_migration.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
dump_tables=sorted(set(re.findall(r'CREATE\s+TABLE\s+`([^`]+)`',sql,re.I)))
counts={}; statements=0
for m in re.finditer(r'INSERT\s+INTO\s+`([^`]+)`',sql,re.I):
 end=mod._scan_sql_until_semicolon(sql,m.start()); stmt=sql[m.start():end+1]
 counts[m.group(1)]=counts.get(m.group(1),0)+mod.parse_insert_tuple_count(stmt);statements+=1
cfg={k:v for k,v in dotenv_values(str(base/'django_backend/.env')).items() if v is not None}
c=MySQLdb.connect(host=cfg.get('DB_HOST','127.0.0.1'),port=int(cfg.get('DB_PORT','3306')),user=cfg.get('DB_USER',''),password=cfg.get('DB_PASSWORD',''),database=cfg.get('DB_NAME',''),connect_timeout=8,charset='utf8mb4')
try:
 with c.cursor() as q:
  q.execute('SET SESSION TRANSACTION READ ONLY');q.execute('SELECT DATABASE(),VERSION(),NOW(6)');db,ver,scan=q.fetchone()
  if db!='stokit_legacy_test':raise RuntimeError('wrong source')
  q.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE=%s ORDER BY TABLE_NAME',(db,'BASE TABLE'));live_tables=[r[0] for r in q.fetchall()]
  live_counts={}
  for t in live_tables:
   q.execute('SELECT COUNT(*) FROM `'+t.replace('`','``')+'`');live_counts[t]=int(q.fetchone()[0])
finally:c.close()
tables={}
for t in sorted(set(dump_tables)|set(live_tables)):
 is_dump=t in dump_tables; is_live=t in live_counts
 tables[t]={'in_dump_schema':is_dump,'in_live_schema':is_live,'live_rows':live_counts.get(t),'dump_tuples':counts.get(t) if is_dump else None,'dump_insert_present':t in counts,'delta_dump_minus_live':(counts.get(t,0)-live_counts[t]) if is_dump and is_live else None}
shared=[t for t in dump_tables if t in live_counts]
report={'scan_time_db':str(scan),'source_database':db,'server_version':ver,'dump_create_table_count':len(dump_tables),'live_table_count':len(live_tables),'insert_statement_count':statements,'dump_tuple_total':sum(counts.values()),'shared_dump_live_tables':len(shared),'matching_row_counts':sum(1 for t in shared if counts.get(t,0)==live_counts[t]),'mismatching_row_counts':sum(1 for t in shared if counts.get(t,0)!=live_counts[t]),'dump_only_tables':sorted(set(dump_tables)-set(live_tables)),'live_only_tables':sorted(set(live_tables)-set(dump_tables)),'tables':tables}
out=base/'docs'/'STOKIT_SOURCE_ROWCOUNT_RECONCILIATION_READONLY.json';out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='tables'},indent=2))
