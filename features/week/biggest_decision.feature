Feature: The single biggest decision this week
  Before the deadline, the Week tab offers one decision with a reason, framed as the user's call.

  Background:
    Given this week's fixtures

  Scenario: A starter is a doubt
    Given my starter "Saka" has a 25 percent chance of playing because "Hamstring injury"
    And my captain is "Haaland"
    When the biggest decision is chosen
    Then the decision kind is "availability"
    And the reason mentions "Saka"
    And the reason ends with "your call."

  Scenario: Everyone is fit, so it's the captain choice
    Given my captain is "Haaland"
    And our prediction ranks "Salah" above "Haaland"
    When the biggest decision is chosen
    Then the decision kind is "captain"
    And the reason mentions "Salah"

  Scenario: No predictions yet
    Given my captain is "Haaland"
    And there are no predictions
    When the biggest decision is chosen
    Then there is no decision

  Scenario: A returning guest with no team number
    Given there is no team
    And our prediction ranks "Salah" above "Haaland"
    When the guest decision is chosen
    Then the decision kind is "captain"
    And the reason mentions "Salah"
