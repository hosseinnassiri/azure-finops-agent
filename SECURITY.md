# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue. Use GitHub's private vulnerability reporting:
open <https://github.com/hosseinnassiri/azure-finops-agent/security/advisories/new>, or go to the **Security** tab
and choose **Report a vulnerability**.

Include what you found, how to reproduce it, and which version (`plugins/roastbot/.claude-plugin/plugin.json`) or
commit you tested. You'll get an answer within a week.

## In scope

- Any way RoastBot could change Azure resources, which it should never do. That includes the skill running a
  finding's `fix_command`, or a bundled module writing to Azure.
- The plugin reading or writing files outside its output folder, or sending data anywhere its
  [privacy policy](plugins/roastbot/PRIVACY.md) doesn't list.
- Credentials, tokens or personal data (such as email addresses from activity logs) leaking into reports or roasts.
- The release pipeline: anything that could publish code that didn't come from `main`.

## Supported versions

Only the latest release gets fixes. Update the plugin with `/plugin marketplace update roastbot`.
