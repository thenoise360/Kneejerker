Feature: How worried should I be about a player?
  Each risk uses its own signal, scaled to the same tiers. No judgement calls,
  just thresholds on real data.

  Scenario: The official game rules a player out
    Given a player with a 0 percent chance of playing because "Knee injury"
    When we assess the risk for gameweek 6
    Then the risk tier is "confirmed"
    And a reason is "ruled_out"

  Scenario: An official doubt
    Given a player with a 25 percent chance of playing because "Hamstring"
    When we assess the risk for gameweek 6
    Then the risk tier is "high"
    And the risk is 75 percent

  Scenario: A regular starter who didn't feature last game
    Given a fit player whose last five games were 90, 90, 88, 90 and 0 minutes
    When we assess the risk for gameweek 6
    Then the risk tier is "high"
    And a reason is "missed_last_game"

  Scenario: A bench player who rarely plays is not a worry
    Given a fit player whose last five games were 0, 10, 0, 0 and 0 minutes
    When we assess the risk for gameweek 6
    Then the risk tier is "low"

  Scenario: One booking away from a ban
    Given a fit player with 4 yellow cards this season
    When we assess the risk for gameweek 6
    Then the risk tier is "high"
    And a reason is "one_booking_from_ban"

  Scenario: The early-season ban no longer applies after gameweek 19
    Given a fit player with 4 yellow cards this season
    When we assess the risk for gameweek 20
    Then the risk tier is "low"
