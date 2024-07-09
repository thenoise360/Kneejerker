-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: 2021_2022_elementsummary    Table: fixtures
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `fixtures`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `fixtures` (
  `id` int DEFAULT NULL,
  `code` int DEFAULT NULL,
  `team_h` int DEFAULT NULL,
  `team_h_score` int DEFAULT NULL,
  `team_a` int DEFAULT NULL,
  `team_a_score` int DEFAULT NULL,
  `event` int DEFAULT NULL,
  `finished` int DEFAULT NULL,
  `minutes` int DEFAULT NULL,
  `provisional_start_time` int DEFAULT NULL,
  `kickoff_time` text,
  `event_name` text,
  `is_home` int DEFAULT NULL,
  `difficulty` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
