-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: 2022_2023_bootstrapstatic    Table: teams
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `teams`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `teams` (
  `code` int DEFAULT NULL,
  `draw` int DEFAULT NULL,
  `form` int DEFAULT NULL,
  `id` int DEFAULT NULL,
  `loss` int DEFAULT NULL,
  `name` text,
  `played` int DEFAULT NULL,
  `points` int DEFAULT NULL,
  `position` int DEFAULT NULL,
  `short_name` text,
  `strength` int DEFAULT NULL,
  `team_division` int DEFAULT NULL,
  `unavailable` int DEFAULT NULL,
  `win` int DEFAULT NULL,
  `strength_overall_home` int DEFAULT NULL,
  `strength_overall_away` int DEFAULT NULL,
  `strength_attack_home` int DEFAULT NULL,
  `strength_attack_away` int DEFAULT NULL,
  `strength_defence_home` int DEFAULT NULL,
  `strength_defence_away` int DEFAULT NULL,
  `pulse_id` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
