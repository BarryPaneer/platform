insert into auth_group (name)
values ('Studio Admin'),
       ('Learning Path Admin'),
       ('Catalog Denied Users'),
       ('EdFlex Denied Users'),
       ('Crehana Denied Users'),
       ('Anderspink Denied Users'),
       ('Restricted Triboo Analytics Admin'),
       ('Triboo Analytics Admin'),
       ('Multi-Sites Login'),
       ('Learnlight Denied Users'),
       ('Linkedin Learning Denied Users'),
       ('Udemy Denied Users'),
       ('Founderz Denied Users'),
       ('Siemens Denied Users'),
       ('Centrical Denied Users');
insert into waffle_switch (name, active, created, modified, note) values ('completion.enable_completion_tracking', 1, now(), now(), "");
insert into grades_persistentgradesenabledflag (enabled, enabled_for_all_courses, change_date) values (1, 1, now());
insert into bulk_email_bulkemailflag (enabled, require_course_email_auth, change_date) values (1, 0, now());
insert into certificates_certificategenerationconfiguration (enabled, change_date) values (1, now());
insert into dark_lang_darklangconfig (enabled, released_languages, change_date) values (1, 'fr, zh-cn, pt-br', now());
