# Security policy

Security fixes target the latest tagged release and `main`. Older releases may not receive backports.

Report a vulnerability through GitHub's [private vulnerability reporting](https://github.com/Francis-Lee-210/handbrake-automation/security/advisories/new). Include the affected version, a minimal reproduction using synthetic files, expected/actual behavior and the suspected impact. Do not attach credentials, personal videos or unredacted logs. There is no guaranteed response time.

This tool invokes a locally installed HandBrakeCLI and rearranges files in selected folders. The exact path/volume protections and their limits are documented in [usage](docs/usage.md#filesystem-boundaries). It does not defend against malicious processes running as the same user or root. Dependencies are installed and updated separately by the user.

For ordinary installation or usage problems, use a public bug report with private details removed.
