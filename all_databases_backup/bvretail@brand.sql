-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: bvretail    Table: brand
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `brand`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `brand` (
  `Profile_Id` text,
  `Brand_Id` text,
  `Advertising_awareness` text,
  `Brand_advantage` text,
  `Brand_affinity` text,
  `Consider` text,
  `Consumer_segment` text,
  `Frequency_instore` text,
  `Frequency_online` text,
  `Image_evaluation_convenient` text,
  `Image_evaluation_easy_to_find` text,
  `Image_evaluation_environmentally_friendly` text,
  `Image_evaluation_ethical` text,
  `Image_evaluation_exciting` text,
  `Image_evaluation_for_people_like_me` text,
  `Image_evaluation_friendly` text,
  `Image_evaluation_good_service` text,
  `Image_evaluation_good_value` text,
  `Image_evaluation_premium` text,
  `Image_evaluation_quality` text,
  `Image_evaluation_stylish` text,
  `Image_evaluation_trusted` text,
  `Image_evaluation_wide_range` text,
  `In_store_satisfaction` text,
  `Negative_buzz` text,
  `Not_consider` text,
  `Online_satisfaction` text,
  `Positive_buzz` text,
  `Preference` text,
  `Recommendation` text,
  `Spontaneous_associations` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
