Feature: Week tab empty states
  Calm, plain-language copy whenever there is no live or upcoming gameweek to show

  Scenario Outline: Copy exists for each empty state
    When I ask for the this week copy for "<mode>"
    Then I get a title, eyebrow and body
    And the copy contains no acronyms

    Examples:
      | mode        |
      | pre_season  |
      | off_season  |
      | unavailable |
      | confirming  |

  Scenario: Missing data gives reassurance
    When I ask for the this week copy for "unavailable"
    Then the body says nothing is wrong on the user's side

  Scenario: An unknown mode has no empty copy
    When I ask for the this week copy for "mystery"
    Then there is no copy

  Scenario: Returning after weeks away in the off-season
    Given I have been away for weeks
    When I ask for the this week copy for "off_season"
    Then the body mentions a breather
    And the copy does not read like an error
