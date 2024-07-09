-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: 2021_2022_elementsummary    Table: history
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `history`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `history` (
  `element` int DEFAULT NULL,
  `fixture` int DEFAULT NULL,
  `opponent_team` int DEFAULT NULL,
  `total_points` int DEFAULT NULL,
  `was_home` int DEFAULT NULL,
  `kickoff_time` text,
  `team_h_score` int DEFAULT NULL,
  `team_a_score` int DEFAULT NULL,
  `round` int DEFAULT NULL,
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
  `influence` float DEFAULT NULL,
  `creativity` float DEFAULT NULL,
  `threat` float DEFAULT NULL,
  `ict_index` float DEFAULT NULL,
  `value` int DEFAULT NULL,
  `transfers_balance` int DEFAULT NULL,
  `selected` int DEFAULT NULL,
  `transfers_in` int DEFAULT NULL,
  `transfers_out` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
