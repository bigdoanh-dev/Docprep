create or replace function content_mapping_guard() returns trigger language plpgsql as $$
begin
 if coalesce((new.mapping->>'approved')::boolean,false) and not exists(
   select 1 from content_user u join content_user_role r on r.user_id=u.id
   where u.id::text=new.mapping->>'approved_by' and u.active and r.role='reviewer') then
   raise exception 'Mapping requires an active reviewer'; end if;
 return new;
end $$;
drop trigger if exists content_mapping_guard on taxonomy_snapshot;
create trigger content_mapping_guard before insert on taxonomy_snapshot for each row execute function content_mapping_guard();
insert into content_schema_version values(3);
