Feature: Whether a team beats their chances
  So a first-timer can tell if a team is over or under performing, the Team page gives one verdict and one reason.

  Scenario: A team has been beating their chances
    Given 8 finished games averaging 0.75 better than predicted
    When the record summary is written for "Arsenal"
    Then the headline is "Arsenal have been beating their chances"
    And early days is false

  Scenario: No finished games are logged yet
    Given no finished games, with scoring started on "2026-10-08"
    When the record summary is written for "Arsenal"
    Then the headline is "No finished games logged yet"
    And the reason mentions "8 October 2026"

  Scenario: A returning user checks a team early in the season
    Given 3 finished games averaging 0.75 better than predicted
    When the record summary is written for "Arsenal"
    Then early days is true
    And the headline is "Arsenal have been beating their chances"
