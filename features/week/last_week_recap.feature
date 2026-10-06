Feature: Last week recap for everyone
  So a nervous first-timer can see how the week went in plain English,
  the Last week tab gives a verdict on the average score and one standout reason.

  Scenario: A typical week with a clear standout
    Given gameweek 5 finished with an average of 48 and a highest score of 126
    And "Haaland" scored 17 points with 3 goals and 3 bonus
    When the guest recap is built
    Then the headline is "A fairly typical week"
    And the reason is "Haaland led the way with a hat-trick and a full haul of bonus points."
    And the numbers include an average of 48

  Scenario: The gameweek has no scores yet
    Given gameweek 6 has no finished scores
    When the guest recap is built
    Then the recap is not ready
    And the not-ready message mentions gameweek 6

  Scenario: A returning user opens an older finished gameweek
    Given gameweek 2 finished with an average of 81 and a highest score of 161
    And "Palmer" scored 14 points with 2 goals and 0 bonus
    When the guest recap is built
    Then the headline is "A high-scoring week"
    And the reason is "Palmer led the way with two goals."
