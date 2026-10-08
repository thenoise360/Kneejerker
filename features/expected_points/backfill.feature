Feature: Past seasons can be replayed with only the data available at the time

  Scenario: A replayed gameweek is forecast by a model trained only on earlier gameweeks
    Given stored history for 2025 gameweeks 1 to 8
    When I backfill from 2025 gameweek 6
    Then gameweek 6 was forecast by a model trained on gameweeks 1 to 5
    And gameweek 8 was forecast by a model trained on gameweeks 1 to 7

  Scenario: Replayed forecasts are stored as backfill with their season
    Given stored history for 2025 gameweeks 1 to 8
    When I backfill from 2025 gameweek 6
    Then the log holds 2025 forecasts for gameweeks 6, 7 and 8 marked as backfill
    And an accuracy row marked as backfill exists for each of those gameweeks

  Scenario: Running the backfill again adds nothing new
    Given stored history for 2025 gameweeks 1 to 8
    And gameweeks 6 and 7 of 2025 were already backfilled
    When I backfill from 2025 gameweek 6
    Then only gameweek 8 is written
