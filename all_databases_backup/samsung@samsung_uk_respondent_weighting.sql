-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: samsung    Table: samsung_uk_respondent_weighting
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `samsung_uk_respondent_weighting`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `samsung_uk_respondent_weighting` (
  `profileId` int DEFAULT NULL,
  `weightingMultiplier` float DEFAULT NULL,
  `startDate` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
