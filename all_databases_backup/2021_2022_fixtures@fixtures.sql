-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: 2021_2022_fixtures    Table: fixtures
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `fixtures`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `fixtures` (
  `code` int DEFAULT NULL,
  `event` int DEFAULT NULL,
  `finished` int DEFAULT NULL,
  `finished_provisional` int DEFAULT NULL,
  `id` int DEFAULT NULL,
  `kickoff_time` text,
  `minutes` int DEFAULT NULL,
  `provisional_start_time` int DEFAULT NULL,
  `started` int DEFAULT NULL,
  `team_a` int DEFAULT NULL,
  `team_a_score` int DEFAULT NULL,
  `team_h` int DEFAULT NULL,
  `team_h_score` int DEFAULT NULL,
  `goals_scored_a` text,
  `goals_scored_h` text,
  `assists_a` text,
  `assists_h` text,
  `own_goals_a` text,
  `own_goals_h` text,
  `penalties_saved_a` text,
  `penalties_saved_h` text,
  `penalties_missed_a` text,
  `penalties_missed_h` text,
  `yellow_cards_a` text,
  `yellow_cards_h` text,
  `red_cards_a` text,
  `red_cards_h` text,
  `saves_a` text,
  `saves_h` text,
  `bonus_a` text,
  `bonus_h` text,
  `bps_a` text,
  `bps_h` text,
  `team_h_difficulty` int DEFAULT NULL,
  `team_a_difficulty` int DEFAULT NULL,
  `pulse_id` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
