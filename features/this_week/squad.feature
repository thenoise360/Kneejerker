Feature: Knowing your squad before the deadline
  Your picks for the coming gameweek stay private until the deadline, so we
  start from your last finished gameweek and add any transfers made since.

  Scenario: No transfers since last gameweek
    Given my gameweek 5 team has "Raya" in goal and "Saka" starting
    When we work out my squad for gameweek 6
    Then my squad includes "Saka" as a starter

  Scenario: I've already made a transfer for this week
    Given my gameweek 5 team has "Raya" in goal and "Saka" starting
    And I transferred "Saka" out for "Palmer" for gameweek 6
    When we work out my squad for gameweek 6
    Then my squad includes "Palmer" as a starter
    And my squad does not include "Saka"

  Scenario: I played my free hit last week
    Given my gameweek 4 team has "Raya" in goal and "Saka" starting
    And I played my free hit in gameweek 5 with "Isak" instead of "Saka"
    When we work out my squad for gameweek 6
    Then my squad includes "Saka" as a starter
    And my squad does not include "Isak"

  Scenario: My bank never shows as negative
    Given my gameweek 5 team has "Raya" in goal and "Saka" starting
    And I have 0.5 million in the bank
    And I transferred "Saka" out for "Palmer" for gameweek 6 paying 1.0 million more
    When we work out my squad for gameweek 6
    Then my bank is 0.0 million
