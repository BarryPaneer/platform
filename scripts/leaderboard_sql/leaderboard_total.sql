CREATE OR REPLACE VIEW `triboo_analytics_leaderboard_total` AS
SELECT
  `tl`.`user_id` AS `user_id`,
  `tl`.`first_login` * 10 + `tl`.`first_course_opened` * 5 + `tl`.`stayed_online` * 5 + `tl`.`non_graded_completed` + `tl`.`graded_completed` * 3 + `tl`.`unit_completed` + `tl`.`course_completed` * 15 + `tl`.`learning_path_completed` * 20 AS `total_score`
FROM
  `triboo_analytics_leaderboard` `tl`;