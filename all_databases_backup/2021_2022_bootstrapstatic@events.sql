-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: 2021_2022_bootstrapstatic    Table: events
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `events`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `events` (
  `id` int DEFAULT NULL,
  `name` text,
  `deadline_time` text,
  `average_entry_score` int DEFAULT NULL,
  `finished` int DEFAULT NULL,
  `data_checked` int DEFAULT NULL,
  `highest_scoring_entry` int DEFAULT NULL,
  `deadline_time_epoch` int DEFAULT NULL,
  `deadline_time_game_offset` int DEFAULT NULL,
  `highest_score` int DEFAULT NULL,
  `is_previous` int DEFAULT NULL,
  `is_current` int DEFAULT NULL,
  `is_next` int DEFAULT NULL,
  `cup_leagues_created` int DEFAULT NULL,
  `h2h_ko_matches_created` int DEFAULT NULL,
  `chip_plays_bboost` int DEFAULT NULL,
  `chip_plays_3xc` int DEFAULT NULL,
  `most_selected` int DEFAULT NULL,
  `most_transferred_in` int DEFAULT NULL,
  `top_element` int DEFAULT NULL,
  `points` text,
  `transfers_made` int DEFAULT NULL,
  `most_captained` int DEFAULT NULL,
  `most_vice_captained` int DEFAULT NULL,
  `chip_plays_freehit` int DEFAULT NULL,
  `chip_plays_wildcard` int DEFAULT NULL,
  `top_element_info` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
