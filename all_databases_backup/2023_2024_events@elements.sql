-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: 2023_2024_events    Table: elements
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `elements`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `elements` (
  `gameweek` int DEFAULT NULL,
  `id` int DEFAULT NULL,
  `minutes` int DEFAULT NULL,
  `goals_scored` int DEFAULT NULL,
  `assists` int DEFAULT NULL,
  `clean_sheets` int DEFAULT NULL,
  `goals_conceded` int DEFAULT NULL,
  `own_goals` int DEFAULT NULL,
  `penalties_saved` int DEFAULT NULL,
  `penalties_missed` int DEFAULT NULL,
  `yellow_cards` int DEFAULT NULL,
  `red_cards` int DEFAULT NULL,
  `saves` int DEFAULT NULL,
  `bonus` int DEFAULT NULL,
  `bps` int DEFAULT NULL,
  `influence` text,
  `creativity` text,
  `threat` text,
  `ict_index` text,
  `starts` int DEFAULT NULL,
  `expected_goals` text,
  `expected_assists` text,
  `expected_goal_involvements` text,
  `expected_goals_conceded` text,
  `total_points` int DEFAULT NULL,
  `in_dreamteam` int DEFAULT NULL,
  `fixture` int DEFAULT NULL,
  `minutes_points` int DEFAULT NULL,
  `minutes_value` int DEFAULT NULL,
  `assists_points` int DEFAULT NULL,
  `assists_value` int DEFAULT NULL,
  `goals_scored_points` int DEFAULT NULL,
  `goals_scored_value` int DEFAULT NULL,
  `bonus_points` int DEFAULT NULL,
  `bonus_value` int DEFAULT NULL,
  `goals_conceded_points` int DEFAULT NULL,
  `goals_conceded_value` int DEFAULT NULL,
  `saves_points` int DEFAULT NULL,
  `saves_value` int DEFAULT NULL,
  `yellow_cards_points` int DEFAULT NULL,
  `yellow_cards_value` int DEFAULT NULL,
  `clean_sheets_points` int DEFAULT NULL,
  `clean_sheets_value` int DEFAULT NULL,
  `red_cards_points` int DEFAULT NULL,
  `red_cards_value` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
