-- Expand the supported taxonomy without relabelling existing immutable tag sets.
alter table chunk_tag_set drop constraint chunk_tag_set_bloom_ceiling_check;
alter table chunk_tag_set add constraint chunk_tag_set_bloom_ceiling_check
    check (bloom_ceiling in ('Nhớ','Hiểu','Áp dụng','Phân tích','Đánh giá','Sáng tạo'));
insert into content_schema_version values(4);
