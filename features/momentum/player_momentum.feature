Feature: Player momentum
  A player is Rising, Steady or Cooling, with one plain reason.

  Scenario: A forward with kinder fixtures and a key teammate back is Rising
    Given a forward whose team expects 1.6 goals a game against a typical 1.4
    And a key teammate "Saka" with a 0.20 share who is back in the team
    When the momentum is worked out
    Then the label is "Rising"
    And the reason mentions "fixtures"

  Scenario: A player whose team has no game and no teammate changes is Steady
    Given a forward whose team has no game in the window
    And no teammate changes
    When the momentum is worked out
    Then the label is "Steady"
    And position is "not_tracked"
    And manager is "not_tracked"

  Scenario: A defender with tougher fixtures and a key midfielder out is Cooling
    Given a defender whose next three opponents are expected to score 1.8 against a typical 1.4
    And a key teammate "Palmer" with a 0.25 share who is out
    When the momentum is worked out
    Then the label is "Cooling"
