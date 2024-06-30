-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: bvretail    Table: profile
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `profile`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `profile` (
  `Profile_Id` text,
  `Demographic_Cell_Id` text,
  `Start_Date` text,
  `Addressed_mail_read` text,
  `Age` text,
  `Area_of_employment` text,
  `Car_ownership` text,
  `Cinema` text,
  `Cinema_frequency` text,
  `Customer_magazines_read` text,
  `Education_level` text,
  `Employment_status_asked` text,
  `Gender` text,
  `Home_ownership` text,
  `House_type` text,
  `Household_composition_new` text,
  `Household_income` text,
  `Income_comfortability` text,
  `Length_of_tennancy` text,
  `Neighbourhood_urban_rural` text,
  `Number_of_bedrooms` text,
  `Occupation` text,
  `Online_purchase_frequency` text,
  `Payment_method_asked` text,
  `Position_of_employment` text,
  `Region` text,
  `Relationship_status_asked` text,
  `Relationship_status_audience` text,
  `SEG1` text,
  `Sport_Athletics` text,
  `Sport_Boxing` text,
  `Sport_Cricket` text,
  `Sport_Cycling` text,
  `Sport_Football` text,
  `Sport_Formula_1` text,
  `Sport_Golf` text,
  `Sport_Motor_sports_not_Formula_1` text,
  `Sport_Rugby_League` text,
  `Sport_Rugby_Union` text,
  `Sport_Tennis` text,
  `Time_spent_commuting` text,
  `TV_services_used_Amazon_Prime` text,
  `TV_services_used_BT` text,
  `TV_services_used_EE_TV` text,
  `TV_services_used_Freesat` text,
  `TV_services_used_Freeview` text,
  `TV_services_used_Netflix` text,
  `TV_services_used_Now_TV` text,
  `TV_services_used_Sky` text,
  `TV_services_used_Sky_Go` text,
  `TV_services_used_TalkTalk` text,
  `TV_services_used_Virgin_Media` text,
  `Unaddressed_mail_read` text,
  `Vouchers_in_post` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
