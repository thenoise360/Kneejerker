-- MySQLShell dump 1.0.2  Distrib Ver 8.0.26 for Win64 on x86_64 - for MySQL 8.0.26 (MySQL Community Server (GPL)), for Win64 (x86_64)
--
-- Host: localhost    Database: 2022_2023_detailedstats    Table: detailedstats
-- ------------------------------------------------------
-- Server version	8.0.26

--
-- Table structure for table `detailedstats`
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE IF NOT EXISTS `detailedstats` (
  `name` text,
  `Fouls` float DEFAULT NULL,
  `Yellow_cards` float DEFAULT NULL,
  `Saves` float DEFAULT NULL,
  `Punches` float DEFAULT NULL,
  `Goals_Conceded` float DEFAULT NULL,
  `Goal_Kicks` float DEFAULT NULL,
  `Penalties_Saved` float DEFAULT NULL,
  `Errors_leading_to_goal` float DEFAULT NULL,
  `Accurate_long_balls` float DEFAULT NULL,
  `Passes_per_match` float DEFAULT NULL,
  `Goals` float DEFAULT NULL,
  `Assists` float DEFAULT NULL,
  `Throw_outs` float DEFAULT NULL,
  `Clean_sheets` float DEFAULT NULL,
  `Passes` float DEFAULT NULL,
  `Catches` float DEFAULT NULL,
  `High_Claims` float DEFAULT NULL,
  `Own_goals` float DEFAULT NULL,
  `Sweeper_clearances` float DEFAULT NULL,
  `Red_cards` float DEFAULT NULL,
  `Clearances_off_line` float DEFAULT NULL,
  `Tackle_success_` float DEFAULT NULL,
  `Headed_goals` float DEFAULT NULL,
  `Through_balls` float DEFAULT NULL,
  `Last_man_tackles` float DEFAULT NULL,
  `Goals_with_right_foot` float DEFAULT NULL,
  `Duels_won` float DEFAULT NULL,
  `Successful_50_50s` float DEFAULT NULL,
  `Duels_lost` float DEFAULT NULL,
  `Goals_with_left_foot` float DEFAULT NULL,
  `Hit_woodwork` float DEFAULT NULL,
  `Recoveries` float DEFAULT NULL,
  `Big_Chances_Created` float DEFAULT NULL,
  `Blocked_shots` float DEFAULT NULL,
  `Cross_accuracy_` float DEFAULT NULL,
  `Interceptions` float DEFAULT NULL,
  `Crosses` float DEFAULT NULL,
  `Aerial_battles_lost` float DEFAULT NULL,
  `Clearances` float DEFAULT NULL,
  `Aerial_battles_won` float DEFAULT NULL,
  `Offsides` float DEFAULT NULL,
  `Headed_Clearance` float DEFAULT NULL,
  `Tackles` float DEFAULT NULL,
  `Shooting_accuracy_` float DEFAULT NULL,
  `Shots_on_target` float DEFAULT NULL,
  `Penalties_scored` float DEFAULT NULL,
  `Freekicks_scored` float DEFAULT NULL,
  `Big_chances_missed` float DEFAULT NULL,
  `Goals_per_match` float DEFAULT NULL,
  `Shots` float DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
