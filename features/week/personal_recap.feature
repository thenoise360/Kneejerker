Feature: Personal last week recap
  A known team sees their score against the average and one thing they got right.

  Scenario: Above average week
    Given the average last week was 48
    And my team scored 61 points with 4 points of transfer costs
    When my personal recap is built
    Then the verdict tier is "above"

  Scenario: The team number can't be found for that gameweek
    Given the average last week was 48
    And my team number is not found
    When my personal recap is built
    Then I see a gentle not-found message for gameweek 5

  Scenario: Returning after weeks away to a tough week
    Given the average last week was 60
    And my team scored 30 points with 0 points of transfer costs
    When my personal recap is built
    Then the verdict tier is "tough"
    And the verdict does not contain "bad"
