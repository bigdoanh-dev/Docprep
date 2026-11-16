alter table chunk_review_task add unique(id,chunk_id,purpose);
alter table chunk_review_decision add foreign key(task_id,chunk_id,purpose) references chunk_review_task(id,chunk_id,purpose);
alter table chunk_tag_set add check(bloom_ceiling in ('Nhớ','Hiểu','Áp dụng','Phân tích','Đánh giá'));
alter table chunk_tag_set add check(cardinality(population)<=3);
create function content_decision_guard() returns trigger language plpgsql as $$
begin
 if not exists(select 1 from content_user u join content_user_role r on r.user_id=u.id
   where u.id=new.reviewer_id and u.active and r.role='reviewer') then
   raise exception 'Decision requires active reviewer'; end if;
 return new;
end $$;
create trigger content_decision_guard before insert on chunk_review_decision for each row execute function content_decision_guard();
insert into content_schema_version values(2);
