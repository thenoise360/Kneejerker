-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: surveys    Table: p023604_samsung_da_insights_conjoint
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `p023604_samsung_da_insights_conjoint`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `p023604_samsung_da_insights_conjoint` (
  `dataId` int NOT NULL,
  `responseId` int DEFAULT NULL,
  `varCode` varchar(45) DEFAULT NULL,
  `CH1` int DEFAULT NULL,
  `CH2` int DEFAULT NULL,
  `optValue` int DEFAULT NULL,
  `text` varchar(45) DEFAULT NULL,
  `serverTimeStamp` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`dataId`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
