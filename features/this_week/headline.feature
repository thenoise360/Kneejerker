Feature: The one decision at the top of This Week
  The headline is the first rule that fires, in a fixed order:
  a doubtful starter, then a starter with no match, then unused free
  transfers, then the captain choice, which always applies.

  Background:
    Given my starters are "Saka", "Haaland" and "Salah"
    And our predictions rank "Haaland" above "Salah" above "Saka"

  Scenario: A doubtful starter comes first
    Given "Saka" has a 25 percent chance of playing
    And "Salah" has no match this gameweek
    When the headline is chosen
    Then the headline decision is "injuries" because "starter_doubt" about "Saka"

  Scenario: A starter with no match comes next
    Given "Salah" has no match this gameweek
    When the headline is chosen
    Then the headline decision is "transfers" because "starter_blank" about "Salah"

  Scenario: Unused free transfers come before the captain
    Given I have 2 free transfers
    When the headline is chosen
    Then the headline decision is "transfers" because "unused_free_transfers"

  Scenario: Otherwise it's the captain choice
    When the headline is chosen
    Then the headline decision is "captaincy" because "captain_choice" about "Haaland"

  Scenario: Changing the order changes the headline
    Given "Saka" has a 25 percent chance of playing
    When the headline is chosen with the captain rule first
    Then the headline decision is "captaincy" because "captain_choice" about "Haaland"

  Scenario: A fit starter subbed off early is not called a doubt
    Given "Haaland" was subbed off early last game
    When the headline is chosen
    Then the headline decision is "captaincy" because "captain_choice" about "Haaland"

  Scenario: A starter one booking from a ban is not called a doubt
    Given "Haaland" is one booking from a ban
    When the headline is chosen
    Then the headline decision is "captaincy" because "captain_choice" about "Haaland"

  Scenario: Nothing to do on injuries when everyone is fit
    When the injuries decision is worked out
    Then the injuries decision is "nothing_to_do"

  Scenario: A guest is asked for their team on injuries
    Given I have not given a team number
    When the injuries decision is worked out
    Then the injuries decision is "needs_team"
