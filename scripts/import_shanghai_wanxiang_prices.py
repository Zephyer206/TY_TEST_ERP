#!/usr/bin/env python3
import argparse,json,re,sys,zipfile,os
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET
Q=chr(34)
ERR={'#N/A','#VALUE!','#REF!','#DIV/0!','#NAME?','#NUM!','#NULL!'}
RX=re.compile(r'(?:_xlfn\.)?DISPIMG\('+Q+r'([^'+Q+r' ]+)'+Q)
def iid(v):
 m=RX.search(v) if isinstance(v,str) else None
 return m.group(1) if m else None
def canonical_part_number(v):
 if v is None:return None
 if isinstance(v,bool):return str(v)
 if isinstance(v,int):return str(v)
 if isinstance(v,float):
  if v != v:return None
  return str(int(v)) if v.is_integer() else format(v,'.15g')
 text=str(v).strip()
 if not text:return None
 m=re.fullmatch(r'([+-]?\d+)\.0+',text)
 return m.group(1) if m else text
def pn(v):
 return canonical_part_number(v)
def val(v):
 if v is None or isinstance(v,str) and v.strip().upper() in ERR:return None
 try:return float(v)
 except (TypeError,ValueError):return None
def col2num(c):
 n=0
 for x in c.upper():n=n*26+(ord(x)-64)
 return n
def ref2rc(r):
 m=re.match(r'^([A-Z]+)(\d+)$',r)
 if not m:return None,None
 return int(m.group(2)),col2num(m.group(1))
def media(path):
 with zipfile.ZipFile(path) as z:
  try:a=z.read('xl/cellimages.xml').decode('utf-8');b=z.read('xl/_rels/cellimages.xml.rels').decode('utf-8')
  except KeyError:return {}
 rel=dict(re.findall(r'<Relationship Id='+Q+r'([^'+Q+r']+)'+Q+r'[^>]*Target='+Q+r'([^'+Q+r']+)'+Q,b))
 out={}
 for x in re.findall(r'<etc:cellImage>(.*?)</etc:cellImage>',a,re.S):
  n=re.search(r'name='+Q+r'(ID_[^'+Q+r']+)'+Q,x);r=re.search(r'r:embed='+Q+r'(rId\d+)'+Q,x)
  if n and r and r.group(1) in rel:out[n.group(1)]='xl/'+rel[r.group(1)].lstrip('/ ')
 return out
def media_blob(path,member):
 with zipfile.ZipFile(path) as z:
  try:return z.read(member)
  except KeyError:return None
def export_images(source,output_dir):
 media_map=media(source)
 output_dir=Path(output_dir)
 output_dir.mkdir(parents=True,exist_ok=True)
 exported=[]
 for img_id,member in sorted(media_map.items()):
  blob=media_blob(source,member)
  if not blob:raise ValueError(f'failed to extract {member}')
  ext=Path(member).suffix or '.png'
  target=output_dir/f'{img_id}{ext}'
  target.write_bytes(blob)
  exported.append(str(target))
 return exported
def parse_xlsx(path):
 with zipfile.ZipFile(path) as z:
  wb=ET.fromstring(z.read('xl/workbook.xml'))
  sheets=[]
  for s in wb.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet'):
   sheets.append(s.get('name'))
  if not sheets or sheets[0]!='Sheet3':raise ValueError('first worksheet must be Sheet3')
  try:ss_xml=z.read('xl/sharedStrings.xml');ss=ET.fromstring(ss_xml);shared=[''.join(t.text or '' for t in si.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')) for si in ss.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si')]
  except KeyError:shared=[]
  ws=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
  cells={};formulas={}
  for c in ws.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
   cref=c.get('r');t=c.get('t','n');v_el=c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v');f_el=c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}f')
   if v_el is not None:
    if t=='s' and v_el.text and shared:
     try:cells[cref]=shared[int(v_el.text)]
     except (IndexError,ValueError):cells[cref]=v_el.text
    else:cells[cref]=v_el.text
   if f_el is not None and f_el.text:formulas[cref]=f_el.text
  merges=[]
  merged_values={}
  for m in ws.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}mergeCell'):
   rng=m.get('ref')
   if rng:
    parts=rng.split(':')
    if len(parts)==2:
     r1,c1=ref2rc(parts[0]);r2,c2=ref2rc(parts[1])
     if c1==c2:
      if c1==2:merges.append((r1,r2))
      col=re.match(r'^([A-Z]+)',parts[0]).group(1)
      source=cells.get(parts[0])
      if source is not None:
       for row in range(r1,r2+1):merged_values[col+str(row)]=source
  return sheets,cells,formulas,merges,merged_values
def preview(path):
 sheets,cells,formulas,merges,merged_values=parse_xlsx(path)
 by={}
 for r1,r2 in merges:
  cref='B'+str(r1)
  if cref in formulas:
   x=iid(formulas[cref])
   if x:
    for r in range(r1,r2+1):by[r]=x
 for r in range(2,27):
  cref='B'+str(r)
  if cref in formulas:
   x=iid(formulas[cref])
   if x:by[r]=x
 rows=[]
 for r in range(2,27):
  pn_val=pn(cells.get('A'+str(r)))
  if pn_val:
   price_val=val(cells.get('Q'+str(r)))
   sales_val=val(cells.get('R'+str(r)))
   cpn_val=pn(cells.get('C'+str(r)))
   mat_ref='E'+str(r)
   mat_val=pn(cells.get(mat_ref,merged_values.get(mat_ref)))
   rows.append({'part_number':pn_val,'customer_part_name':cpn_val,'material_name':mat_val,'price_2025':price_val,'annual_sales_2025':sales_val,'image_id':by.get(r)})
 groups=defaultdict(list)
 for x in rows:
  if x['image_id']:groups[x['image_id']].append(x['part_number'])
 d=[{'image_id':k,'part_numbers':x,'media_member':media(path).get(k)} for k,x in groups.items()]
 missing=[x['part_number'] for x in rows if x['price_2025'] is None]
 return {'source_sheet':'Sheet3','ignored_sheets':sheets[1:],'products_total':len(rows),'price_year':2025,'price_rows':len(rows)-len(missing),'missing_price_part_numbers':missing,'current_year':2026,'current_year_price_records':0,'image_groups':len(d),'image_groups_detail':d,'shared_image_pairs':[x['part_numbers'] for x in d if len(x['part_numbers'])==2],'rows':rows}
def norm_customer(name):
 return name.replace('（','(').replace('）',')')
def resolve_aliases(cur,customer_id,part_numbers):
 cur.execute("SELECT part_id, customer_part_no FROM part_customer_aliases WHERE customer_id=%s AND is_active=true",(customer_id,))
 by_number=defaultdict(set)
 for part_id,alias_no in cur.fetchall():
  canonical=canonical_part_number(alias_no)
  if canonical is not None: by_number[canonical].add(part_id)
 resolved={};missing=[];ambiguous=[]
 for cpn in part_numbers:
  canonical=canonical_part_number(cpn)
  matches=sorted(by_number.get(canonical,set()))
  if len(matches)==0:missing.append(cpn)
  elif len(matches)>1:ambiguous.append(cpn)
  else:resolved[cpn]=matches[0]
 return resolved,missing,ambiguous
def async_to_sync_url(url):
 if not url:return None
 if url.startswith('postgresql+asyncpg://'):return url.replace('postgresql+asyncpg://','postgresql://',1)
 return url
def check_db(source,env_file):
 import psycopg2
 db_url=None
 if env_file and Path(env_file).exists():
  for line in Path(env_file).read_text(encoding='utf-8').splitlines():
   line=line.strip()
   if line.startswith('DATABASE_URL='):
    db_url=line.split('=',1)[1].strip().strip('"').strip("'")
    break
 if not db_url:db_url=os.environ.get('DATABASE_URL')
 if not db_url:raise ValueError('DATABASE_URL not found in env file or environment')
 db_url=async_to_sync_url(db_url)
 prev=preview(source)
 rows=prev['rows']
 target='万向钱潮(上海)汽车制动系统有限公司'
 norm_target=norm_customer(target)
 conn=psycopg2.connect(db_url)
 conn.set_session(readonly=True,autocommit=False)
 try:
  cur=conn.cursor()
  cur.execute("SELECT id FROM customers WHERE REPLACE(REPLACE(name,'（','('),'）',')')=%s",(norm_target,))
  cust=cur.fetchall()
  if len(cust)==0:return {'error':'customer not found'}
  if len(cust)>1:return {'error':'ambiguous customer'}
  customer_id=cust[0][0]
  part_numbers=[x['part_number'] for x in rows]
  resolved,missing,ambiguous=resolve_aliases(cur,customer_id,part_numbers)
  cur.close()
  conn.rollback()
  return {'customer_found':1,'products_resolved':len(resolved),'missing':missing,'ambiguous':ambiguous}
 finally:conn.close()
def apply_import(source,env_file,operator_id=None,bootstrap_from_excel=False):
 import psycopg2
 from datetime import datetime
 db_url=None
 if env_file and Path(env_file).exists():
  for line in Path(env_file).read_text(encoding='utf-8').splitlines():
   line=line.strip()
   if line.startswith('DATABASE_URL='):
    db_url=line.split('=',1)[1].strip().strip('"').strip("'")
    break
 if not db_url:db_url=os.environ.get('DATABASE_URL')
 if not db_url:raise ValueError('DATABASE_URL not found in env file or environment')
 db_url=async_to_sync_url(db_url)
 prev=preview(source)
 rows=prev['rows']
 target='万向钱潮(上海)汽车制动系统有限公司'
 norm_target=norm_customer(target)
 media_map=media(source)
 image_groups={}
 for x in rows:
  if x['image_id']:
   if x['image_id'] not in image_groups:image_groups[x['image_id']]=[]
   image_groups[x['image_id']].append(x['part_number'])
 preflight_images=[]
 for img_id in image_groups:
  if img_id not in media_map:raise ValueError(f'image_id {img_id} not found in media')
  member=media_map[img_id]
  blob=media_blob(source,member)
  if not blob:raise ValueError(f'failed to extract {member}')
  preflight_images.append((img_id,member,blob))
 conn=psycopg2.connect(db_url)
 try:
  cur=conn.cursor()
  now=datetime.utcnow()
  cur.execute("SELECT id FROM customers WHERE REPLACE(REPLACE(name,'（','('),'）',')')=%s",(norm_target,))
  cust=cur.fetchall()
  if len(cust)==0:raise ValueError('customer not found')
  if len(cust)>1:raise ValueError('ambiguous customer')
  customer_id=cust[0][0]
  part_numbers=[x['part_number'] for x in rows]
  resolved,missing,ambiguous=resolve_aliases(cur,customer_id,part_numbers)
  if ambiguous:raise ValueError(f'ambiguous aliases: {ambiguous}')
  if missing and not bootstrap_from_excel:raise ValueError(f'missing aliases without --bootstrap-from-excel: {missing}')
  parts_created=0
  aliases_created=0
  if missing and bootstrap_from_excel:
   rows_by_pn={x['part_number']:x for x in rows}
   for cpn in missing:
    row=rows_by_pn[cpn]
    cur.execute("INSERT INTO parts(internal_name,customer_product_no,customer_product_name,material_name,part_status,spray_status,stock_pcs,is_deleted,version,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",(None,row['part_number'],row['customer_part_name'],row['material_name'],'DRAFT','pending',0,False,'V1.0',now,now))
    part_id=cur.fetchone()[0]
    parts_created+=1
    cur.execute("SELECT name FROM customers WHERE id=%s",(customer_id,))
    customer_name=cur.fetchone()[0]
    cur.execute("INSERT INTO part_customer_aliases(part_id,customer_id,customer_name,customer_part_no,customer_part_name,revision,is_active,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(part_id,customer_id,customer_name,row['part_number'],row['customer_part_name'],'',True,now,now))
    aliases_created+=1
    resolved[cpn]=part_id
  aliases_reused=len([x for x in part_numbers if x not in missing])
  price_upserted=0
  price_year_upserted=0
  materials_updated=0
  for x in rows:
   part_id=resolved[x['part_number']]
   if x['material_name'] is not None:
    cur.execute("UPDATE parts SET material_name=%s,updated_at=%s WHERE id=%s AND material_name IS DISTINCT FROM %s",(x['material_name'],now,part_id,x['material_name']))
    materials_updated+=cur.rowcount
   cur.execute("SELECT id FROM prices WHERE part_id=%s AND customer_id=%s",(part_id,customer_id))
   existing=cur.fetchone()
   if existing:
    price_id=existing[0]
    cur.execute("UPDATE prices SET updated_at=%s WHERE id=%s",(now,price_id))
   else:
    cur.execute("INSERT INTO prices(part_id,customer_id,created_at,updated_at) VALUES(%s,%s,%s,%s) RETURNING id",(part_id,customer_id,now,now))
    price_id=cur.fetchone()[0]
   price_upserted+=1
   if x['price_2025'] is not None:
    cur.execute("INSERT INTO price_years(price_id,year,unit_price,annual_sales,operator_id,updated_at) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(price_id,year) DO UPDATE SET unit_price=EXCLUDED.unit_price,annual_sales=EXCLUDED.annual_sales,operator_id=EXCLUDED.operator_id,updated_at=EXCLUDED.updated_at",(price_id,2025,x['price_2025'],x['annual_sales_2025'],operator_id,now))
    price_year_upserted+=1
   if x['image_id'] and x['image_id'] in media_map:
    member=media_map[x['image_id']]
    ext=Path(member).suffix or '.png'
    fname=f"{x['image_id']}{ext}"
    drawing_url=f"/static/uploads/part_images/wanxiang_shanghai/{fname}"
    cur.execute("UPDATE parts SET drawing_url=%s,updated_at=%s WHERE id=%s AND (drawing_url IS NULL OR drawing_url!=%s)",(drawing_url,now,part_id,drawing_url))
  image_dir=Path(__file__).parent.parent/'static'/'uploads'/'part_images'/'wanxiang_shanghai'
  image_dir.mkdir(parents=True,exist_ok=True)
  images_exported=0
  for img_id,member,blob in preflight_images:
   ext=Path(member).suffix or '.png'
   fname=f"{img_id}{ext}"
   (image_dir/fname).write_bytes(blob)
   images_exported+=1
  conn.commit()
  cur.close()
  return {'parts_created':parts_created,'aliases_created':aliases_created,'aliases_reused':aliases_reused,'materials_updated':materials_updated,'price_accounts_upserted':price_upserted,'price_years_upserted':price_year_upserted,'images_exported':images_exported}
 except Exception as e:
  conn.rollback()
  raise
 finally:conn.close()
def main():
 if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
 if hasattr(sys.stderr,'reconfigure'):sys.stderr.reconfigure(encoding='utf-8')
 p=argparse.ArgumentParser()
 p.add_argument('--source','--file',dest='source',required=True)
 p.add_argument('--dry-run',action='store_true',default=False)
 p.add_argument('--check-db',action='store_true',default=False)
 p.add_argument('--apply',action='store_true',default=False)
 p.add_argument('--bootstrap-from-excel',action='store_true',default=False)
 p.add_argument('--export-images',dest='export_images',default=None,help='Extract embedded images without touching the database')
 p.add_argument('--env-file',dest='env_file',default=None)
 x=p.parse_args()
 if x.apply and x.dry_run:print(json.dumps({'error':'--apply and --dry-run are mutually exclusive'}),file=sys.stderr);return 2
 if x.check_db and x.dry_run:print(json.dumps({'error':'--check-db and --dry-run are mutually exclusive'}),file=sys.stderr);return 2
 try:
  if x.export_images:
   exported=export_images(x.source,x.export_images)
   print(json.dumps({'images_exported':len(exported),'output_dir':str(Path(x.export_images))},ensure_ascii=False))
   return 0
  elif x.apply:
   result=apply_import(x.source,x.env_file,bootstrap_from_excel=x.bootstrap_from_excel)
   print(json.dumps(result,ensure_ascii=False))
   return 0
  elif x.check_db:
   result=check_db(x.source,x.env_file)
   print(json.dumps(result,ensure_ascii=False))
   return 0
  else:
   print(json.dumps(preview(x.source),ensure_ascii=False))
   return 0
 except Exception as e:
  print(json.dumps({'error':str(e)},ensure_ascii=False),file=sys.stderr)
  return 1
if __name__=='__main__':raise SystemExit(main())
