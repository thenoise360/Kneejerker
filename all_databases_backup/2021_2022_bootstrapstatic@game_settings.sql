-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: 2021_2022_bootstrapstatic    Table: game_settings
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `game_settings`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `game_settings` (
  `league_join_private_max` int DEFAULT NULL,
  `league_join_public_max` int DEFAULT NULL,
  `league_max_size_public_classic` int DEFAULT NULL,
  `league_max_size_public_h2h` int DEFAULT NULL,
  `league_max_size_private_h2h` int DEFAULT NULL,
  `league_max_ko_rounds_private_h2h` int DEFAULT NULL,
  `league_prefix_public` text,
  `league_points_h2h_win` int DEFAULT NULL,
  `league_points_h2h_lose` int DEFAULT NULL,
  `league_points_h2h_draw` int DEFAULT NULL,
  `league_ko_first_instead_of_random` int DEFAULT NULL,
  `cup_start_event_id` int DEFAULT NULL,
  `cup_stop_event_id` int DEFAULT NULL,
  `cup_qualifying_method` int DEFAULT NULL,
  `cup_type` int DEFAULT NULL,
  `squad_squadplay` int DEFAULT NULL,
  `squad_squadsize` int DEFAULT NULL,
  `squad_team_limit` int DEFAULT NULL,
  `squad_total_spend` int DEFAULT NULL,
  `ui_currency_multiplier` int DEFAULT NULL,
  `ui_use_special_shirts` int DEFAULT NULL,
  `ui_special_shirt_exclusions` int DEFAULT NULL,
  `stats_form_days` int DEFAULT NULL,
  `sys_vice_captain_enabled` int DEFAULT NULL,
  `transfers_cap` int DEFAULT NULL,
  `transfers_sell_on_fee` float DEFAULT NULL,
  `league_h2h_tiebreak_stats_goals_scored` text,
  `league_h2h_tiebreak_stats__goals_conceded` text,
  `league_h2h_tiebreak_stats` text,
  `timezone` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
