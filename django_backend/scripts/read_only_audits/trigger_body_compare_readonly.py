from pathlib import Path
import re, hashlib, json
from dotenv import dotenv_values
import MySQLdb
sql=Path(r'C:\Users\.MSI\Downloads\stokit_sql_work\u144866523_stokitDB.sql').read_text(encoding='utf-8',errors='replace')
m=re.search(r'CREATE\s+TRIGGER\s+`?update_target_progress_after_order`?.*?\bBEGIN\b(.*?)\bEND\s*\$\$',sql,re.I|re.S)
if not m: raise RuntimeError('Could not parse trigger body from dump')
dump_body=re.sub(r'\s+',' ',m.group(1).strip()).lower()
cfg={k:v for k,v in dotenv_values(r'C:\Users\.MSI\Downloads\StokIt Backend\django_backend\.env').items() if v is not None}
c=MySQLdb.connect(host=cfg.get('DB_HOST','127.0.0.1'),port=int(cfg.get('DB_PORT','3306')),user=cfg.get('DB_USER',''),password=cfg.get('DB_PASSWORD',''),database=cfg.get('DB_NAME',''),connect_timeout=8,charset='utf8mb4')
try:
 with c.cursor() as q:
  q.execute('SET SESSION TRANSACTION READ ONLY');q.execute('SELECT DATABASE()');db=q.fetchone()[0]
  if db!='stokit_legacy_test':raise RuntimeError('wrong database')
  q.execute("SELECT ACTION_STATEMENT FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME=%s",(db,'update_target_progress_after_order'))
  row=q.fetchone()
  if not row: raise RuntimeError('live trigger not found')
  live_body=re.sub(r'\s+',' ',row[0].strip()).lower()
finally:c.close()
report={'trigger':'update_target_progress_after_order','dump_body_sha256':hashlib.sha256(dump_body.encode()).hexdigest(),'live_body_sha256':hashlib.sha256(live_body.encode()).hexdigest(),'normalized_body_match':dump_body==live_body,'comparison_note':'Whitespace and case normalized only; SQL semantics/definer/security mode not compared.'}
out=Path(r'C:\Users\.MSI\Downloads\StokIt Backend\docs\STOKIT_TRIGGER_BODY_COMPARE_READONLY.json');out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
