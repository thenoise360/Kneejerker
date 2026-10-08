Feature: Supporting information for the Captain and vice choice
  Each option carries the official game's expected points, this week's match and recent form.
  A fuller player context says how the match looks, how the player has done
  and what happened in past meetings with this week's opponent.

  Scenario: The captain lean follows expected points
    Given my starters are "Saka", "Haaland" and "Salah"
    And their expected points are "Saka" 5.1, "Haaland" 7.4 and "Salah" 6.2
    When the captain choice is made
    Then the shortlist reads "Haaland", "Salah", "Saka"
    And the vice is "Salah"

  Scenario: A starter with no stored expected points is ranked last, not dropped
    Given my starters are "Saka", "Haaland" and "Salah"
    And their expected points are "Saka" 5.1 and "Haaland" 7.4
    When the captain choice is made
    Then the shortlist reads "Haaland", "Saka", "Salah"

  Scenario: Equal expected points are split by name
    Given my starters are "Saka", "Haaland" and "Salah"
    And their expected points are "Saka" 6.0, "Haaland" 6.0 and "Salah" 6.0
    When the captain choice is made
    Then the shortlist reads "Haaland", "Saka", "Salah"

  Scenario: The rest of the squad is listed separately
    Given my starters are "Saka" and "Haaland"
    And "Salah" is on my bench
    And their expected points are "Saka" 5.1, "Haaland" 7.4 and "Salah" 9.0
    When the captain choice is made
    Then the shortlist reads "Haaland", "Saka"
    And the rest of the squad reads "Salah"

  Scenario Outline: Fixture difficulty uses a 20 percent line
    Given an attacker whose team usually scores 2.0 expected goals
    When their match is expected to bring <own> expected goals
    Then the difficulty is <difficulty>

    Examples:
      | own  | difficulty |
      | 2.4  | easier     |
      | 2.39 | average    |
      | 1.6  | tougher    |
      | 1.61 | average    |

  Scenario Outline: A defender cares about what the opponent scores
    Given a defender whose team usually concedes 1.0 expected goals
    When the opponent is expected to score <opp> expected goals
    Then the difficulty is <difficulty>

    Examples:
      | opp  | difficulty |
      | 0.8  | easier     |
      | 0.81 | average    |
      | 1.2  | tougher    |
      | 1.19 | average    |

  Scenario: Past meetings match clubs by code, not by id
    Given the opponent has club code 43
    And last season that club had id 12 and this season it has id 3
    And the player met them last season in gameweek 12 away for 90 minutes and 8 points
    And the player met other clubs too
    When past meetings are listed
    Then there is 1 past meeting, from season 2025, in gameweek 12, away, 90 minutes, 8 points

  Scenario: No past meetings gives an empty list
    Given the opponent has club code 43
    When past meetings are listed
    Then there are no past meetings

  Scenario Outline: The route needs one or two players
    When I ask for player context with ids "<ids>"
    Then the response status is <status>

    Examples:
      | ids   | status |
      |       | 400    |
      | 1,2,3 | 400    |
      | abc   | 400    |
      | 1     | 200    |
      | 1,2   | 200    |

  Scenario: The route never fails when the database is down
    Given the database is down
    When I ask for player context with ids "1"
    Then the response status is 200
    And the response status field is "unavailable"
