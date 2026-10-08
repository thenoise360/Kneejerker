Feature: We keep every week's forecasts so we can say how accurate we were

  Scenario: Forecasts made before the deadline are logged
    Given the gameweek 6 deadline is tomorrow
    When the daily job logs 3 forecasts
    Then 3 rows are written to the log

  Scenario: Forecasts made after the deadline are not logged
    Given the gameweek 6 deadline was an hour ago
    When the daily job logs 3 forecasts
    Then nothing is written to the log

  Scenario: The forecast of record is the last one before the deadline
    Given forecasts for a player of 4.0 on Wednesday, 5.0 on Thursday and 9.0 after the Friday deadline
    When I take the forecast of record
    Then it is 5.0

  Scenario: Accuracy waits for bonus to be confirmed
    Given gameweek 6 has finished but its data is not yet checked
    Then gameweek 6 is not settled

  Scenario: Accuracy compares us with the official number on the same players
    Given our forecasts of 6 and 2 and official forecasts of 3 and 3
    And the players actually scored 8 and 1
    When I work out the accuracy
    Then our average error is 1.5 and the official average error is 3.5
