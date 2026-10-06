Feature: One thing you got right
  Every personal recap celebrates something, even in a bad week.

  Scenario: The captain delivered
    Given a squad where captain "Salah" scored 12 points
    When we look for one thing they got right
    Then the tier is "captain"
    And the reason mentions "Salah"

  Scenario: Nothing scored well but a pick was sound
    Given a squad where nobody scored more than 3 points
    And starter "Isak" blanked with 1 point in a kind fixture
    When we look for one thing they got right
    Then the tier is "sound_blank"
    And the reason mentions "kind fixture"

  Scenario: Missing data for every player
    Given a squad with no player results
    When we look for one thing they got right
    Then the tier is "showed_up"

  Scenario: A returning user's first week back went badly
    Given a squad where nobody scored more than 1 point
    When we look for one thing they got right
    Then the tier is "showed_up"
    And the reason mentions "fresh start"
