Feature: Gameweek state for the Week tab
  The Week tab needs to know what "this week" and "last week" mean right now,
  based on the official gameweek calendar.

  Scenario: Before gameweek 1
    Given the season has gameweeks 1 to 3 and none has started
    When the week view is resolved
    Then this week is "pre_season" for gameweek 1
    And last week is "none"

  Scenario: Deadline passed and games in progress
    Given gameweek 5 deadline has passed and its games are still being played
    When the week view is resolved
    Then this week is "live" for gameweek 5
    And last week is "final" for gameweek 4

  Scenario: Finished but data not yet checked
    Given gameweek 5 has finished but its data is not yet checked
    When the week view is resolved
    Then this week is "confirming" for gameweek 5
    And last week is "final" for gameweek 4

  Scenario: Between gameweeks
    Given gameweek 5 is complete and checked and gameweek 6 has not started
    When the week view is resolved
    Then this week is "upcoming" for gameweek 6
    And last week is "final" for gameweek 5

  Scenario: Final gameweek done so the season is over
    Given the final gameweek 38 is complete and checked
    When the week view is resolved
    Then this week is "off_season" with no gameweek
    And last week is "final" for gameweek 38

  Scenario: Gameweek data could not be fetched
    Given the gameweek data could not be fetched
    When the week view is resolved
    Then this week is "unavailable" with no gameweek
    And last week is "none"

  Scenario: An event with a missing deadline is ignored
    Given gameweek 5 is live and gameweek 6 has no deadline
    When the week view is resolved
    Then this week is "live" for gameweek 5

  Scenario: Returning user sees current data, not stale data
    Given someone last looked during gameweek 3
    And gameweek 7 is complete and checked and gameweek 8 has not started
    When the week view is resolved
    Then this week is "upcoming" for gameweek 8
    And last week is "final" for gameweek 7
