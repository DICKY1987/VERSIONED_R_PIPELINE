# BDD Feature: File Deduplication
# Version: 1.0.0
# Date: 2025-11-02
Feature: File Deduplication
  As a developer
  I want duplicate files to be detected automatically
  So that I don't commit the same file twice

  Scenario: New file is not marked as duplicate
    Given a new file "example.txt" with content "hello world"
    When I run the deduplicator plugin
    Then the file should not be marked as duplicate
    And the file should be allowed to proceed

  Scenario: Duplicate file is detected
    Given an existing file "original.txt" with hash "abc123"
    And a new file "duplicate.txt" with the same hash "abc123"
    When I run the deduplicator plugin on "duplicate.txt"
    Then the file should be marked as duplicate
    And the recommended action should be "quarantine"
    And the duplicate_of field should be "original.txt"

  Scenario: Plugin respects timeout
    Given a file that takes 60 seconds to process
    And the plugin timeout is set to 30 seconds
    When I run the deduplicator plugin
    Then the plugin should timeout gracefully
    And return an error status
