Feature: How strong a team is this week
  So a first-timer knows whether a team is weakened, the Team page gives one verdict and one reason.

  Scenario: Two main chance-creators are out
    Given a team that scores 1.9 a game and 1.5 with absences
    And "Saka" and "Odegaard" are missing chance-creators
    When the strength summary is written for "Arsenal"
    Then the headline is "Arsenal's attack is weaker this week"
    And the reason is "Two of their main chance-creators are out."

  Scenario: Nobody important is missing
    Given a team that scores 1.9 a game and 1.9 with absences
    When the strength summary is written for "Arsenal"
    Then the headline is "Arsenal are at full strength"
    And the reason is "Strong going forward, solid at the back."

  Scenario: A returning user checks a weakened defence
    Given a team that concedes 1.0 a game and 1.25 with absences
    And "Saliba" is a missing defender
    When the strength summary is written for "Arsenal"
    Then the headline is "Arsenal's defence is weaker this week"
    And the reason is "One of their regular defenders is out."
