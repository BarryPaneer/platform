CREATE OR REPLACE VIEW `triboo_analytics_leaderboardview` AS
  SELECT
    `triboo_analytics_leaderboard`.`id` AS `id`,
    `triboo_analytics_leaderboard`.`user_id` AS `user_id`,
    `triboo_analytics_leaderboard_total`.`total_score` AS `total_score`,
    CASE
      WHEN `triboo_analytics_leaderboard_total`.`total_score` < `triboo_analytics_leaderboard`.`last_week_score` THEN 0
      ELSE `triboo_analytics_leaderboard_total`.`total_score` - `triboo_analytics_leaderboard`.`last_week_score`
    END AS `current_week_score`,
    CASE
      WHEN `triboo_analytics_leaderboard_total`.`total_score` < `triboo_analytics_leaderboard`.`last_month_score` THEN 0
      ELSE `triboo_analytics_leaderboard_total`.`total_score` - `triboo_analytics_leaderboard`.`last_month_score`
    END AS `current_month_score`,
    `triboo_analytics_leaderboard`.`last_week_rank` AS `last_week_rank`,
    `triboo_analytics_leaderboard`.`last_month_rank` AS `last_month_rank`,
    `triboo_analytics_leaderboard`.`modified` AS `last_updated`
  FROM
    (`triboo_analytics_leaderboard` JOIN `triboo_analytics_leaderboard_total`)
  WHERE
    (`triboo_analytics_leaderboard`.`user_id` = `triboo_analytics_leaderboard_total`.`user_id`)
  ORDER BY
    `triboo_analytics_leaderboard_total`.`total_score` DESC;