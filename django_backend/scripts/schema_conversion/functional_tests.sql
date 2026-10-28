-- Functional tests for the converted schema. Run ONLY against the isolated validation DB. Always rolls back.
\set ON_ERROR_STOP on
BEGIN;
CREATE FUNCTION pg_temp.assert_test(ok boolean, label text) RETURNS void LANGUAGE plpgsql AS $assert$
BEGIN
  IF ok IS DISTINCT FROM TRUE THEN
    RAISE EXCEPTION 'Functional test failed: %', label;
  END IF;
  RAISE NOTICE '%: PASS', label;
END
$assert$;
DO $$
DECLARE
  uid int; cid int; pid int; tid int; oid_ int; r record; t1 timestamp; bad boolean;
BEGIN
  -- 1 enum CHECK rejects a bad value
  bad := false;
  BEGIN
    INSERT INTO users(username,password,email,fullname,token,latitude,longitude,status) VALUES('x','x','x@x','x','t','1','1','BOGUS');
  EXCEPTION WHEN check_violation THEN bad := true; END;
  PERFORM pg_temp.assert_test(bad, 'T1 enum check rejects bad users.status');

  INSERT INTO users(username,password,email,fullname,token,latitude,longitude) VALUES('u1','p','u1@x.com','U One','t','1','1') RETURNING id INTO uid;
  PERFORM pg_temp.assert_test(uid IS NOT NULL, 'T2 identity id assigned');

  -- 3 unique email
  bad := false;
  BEGIN
    INSERT INTO users(username,password,email,fullname,token,latitude,longitude) VALUES('u2','p','u1@x.com','U Two','t','1','1');
  EXCEPTION WHEN unique_violation THEN bad := true; END;
  PERFORM pg_temp.assert_test(bad, 'T3 unique users.email enforced');

  -- 4 ON UPDATE emulation: updated_at NULL initially, set on a real change, not set on a no-op update
  SELECT updated_at INTO t1 FROM users WHERE id = uid;
  PERFORM pg_temp.assert_test(t1 IS NULL, 'T4a updated_at initially NULL');
  UPDATE users SET fullname = 'U One' WHERE id = uid;
  SELECT updated_at INTO t1 FROM users WHERE id = uid;
  PERFORM pg_temp.assert_test(t1 IS NULL, 'T4b no-op update leaves updated_at NULL');
  UPDATE users SET fullname = 'U Uno' WHERE id = uid;
  SELECT updated_at INTO t1 FROM users WHERE id = uid;
  PERFORM pg_temp.assert_test(t1 IS NOT NULL, 'T4c real update sets updated_at');

  -- 5 FK orphan rejected / cascade works
  bad := false;
  BEGIN
    INSERT INTO advance_pay_allocations(offer_id,user_id,payment_amount,bonus_percentage,duration_months,total_credit,start_date,end_date,payment_date) VALUES(99999,uid,1,1,1,1,current_date,current_date,current_date);
  EXCEPTION WHEN foreign_key_violation THEN bad := true; END;
  PERFORM pg_temp.assert_test(bad, 'T5a FK rejects orphan allocation');
  INSERT INTO notifications(customer_id,title,message) VALUES(uid,'t','m');
  DELETE FROM users WHERE id = uid;
  SELECT count(*) INTO oid_ FROM notifications WHERE customer_id = uid;
  PERFORM pg_temp.assert_test(oid_ = 0, 'T5b ON DELETE CASCADE users to notifications');

  -- 6 boolean default mapping
  INSERT INTO zg_category(category_name) VALUES('cat') RETURNING category_id INTO cid;
  SELECT category_active INTO bad FROM zg_category WHERE category_id = cid;
  PERFORM pg_temp.assert_test(bad IS TRUE, 'T6 category_active defaults true');

  -- 7 json check on zg_product.set_contains
  INSERT INTO users(username,password,email,fullname,token,latitude,longitude) VALUES('u3','p','u3@x.com','U Three','t','1','1') RETURNING id INTO uid;
  bad := false;
  BEGIN
    INSERT INTO zg_product(code,stock,product_name,color,product_price,product_keywords,top2,hand2,heading5_tag,heading6_tag,heading7_tag,added,view,set_contains)
      VALUES('c','1','p','c',1,'k',0,0,0,0,0,'a','v','{not json');
  EXCEPTION WHEN check_violation THEN bad := true; END;
  PERFORM pg_temp.assert_test(bad, 'T7a invalid JSON rejected in zg_product.set_contains');
  INSERT INTO zg_product(code,stock,product_name,color,product_price,product_keywords,top2,hand2,heading5_tag,heading6_tag,heading7_tag,added,view,category_id,set_contains)
    VALUES('c','1','p','c',1,'k',0,0,0,0,0,'a','v',cid,'{"a":1}') RETURNING product_id INTO pid;
  PERFORM pg_temp.assert_test(true, 'T7b valid JSON accepted');

  -- 8 translated checkout trigger: fulfilled order raises assignment progress
  INSERT INTO zg_targets(target_name,category_id,target_amount,reward_description,start_date,end_date)
    VALUES('t',cid,100,'r',current_date-1,current_date+1) RETURNING target_id INTO tid;
  INSERT INTO zg_target_assignments(target_id,user_id) VALUES(tid,uid);
  INSERT INTO zg_checkout("user",full_name,address,city,state,postal_code,country,phone,email,total_amount,status,view,payment_method,shipping_charge)
    VALUES('u','n','a','c','s','p','co','ph','u3@x.com',150,'pending','v','cod','0') RETURNING order_id INTO oid_;
  INSERT INTO zg_order_items(order_id,product_id,product_name,variant_name,quantity,price,discount,total_price)
    VALUES(oid_,pid,'p','v',1,150,0,150);
  UPDATE zg_checkout SET status = 'fulfilled' WHERE order_id = oid_;
  SELECT * INTO r FROM zg_target_assignments WHERE target_id = tid AND user_id = uid;
  PERFORM pg_temp.assert_test(r.achieved_amount = 150 AND r.order_count = 1 AND r.status = 'ACHIEVED' AND r.achieved_date IS NOT NULL, 'T8 checkout trigger updates target progress');
END $$;
ROLLBACK;
SELECT 'rows left in users: ' || count(*) FROM users;
