Feature: Expected points features only use what was known before the deadline

  Scenario: A feature never reads the gameweek it predicts
    Given a player who scored 2 points in gameweeks 1 to 4 and 20 points in gameweek 5
    When I build the features for gameweek 5
    Then the average points over the last 3 matches is 2.0

  Scenario: Form carries across seasons by player code
    Given a player with id 300 in 2025 who scored 6 points in each of his last 3 matches
    And the same player with id 41 in 2026
    When I build the features for 2026 gameweek 1
    Then the average points over the last 3 matches is 6.0
    And points per match this season is missing

  Scenario: A double gameweek adds both matches together
    Given a player who played twice in gameweek 7, scoring 5 and 8 points
    When I build the training rows
    Then gameweek 7 has a target of 13 points and 2 matches

  Scenario: A blank gameweek gives no training row
    Given a player whose club had no match in gameweek 8
    When I build the training rows
    Then there is no row for gameweek 8

  Scenario: A new player has empty form, not zeros
    Given a player with no earlier matches
    When I build the features for gameweek 3
    Then the average points over the last 3 matches is missing
