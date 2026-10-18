# Public-source safeguards

Do not commit credentials, real tenant/resource identifiers, account addresses,
registry extracts, generated reports or private operational evidence. Configure
real resources privately. Template GUIDs use the prefix
`00000000-0000-4000-8000-` followed by twelve hexadecimal characters.

Install Gitleaks from its official release or an existing package manager, then
enable this clone's staged checks (no global Git changes):

```sh
git config core.hooksPath .githooks
```

Alternatively install the supplied pre-commit configuration. Both routes inspect
exact staged bytes and fail closed when Gitleaks is missing. Hooks are opt-in per
clone and Git can bypass them; required PR checks and GitHub push protection add
further layers. CI scans full reachable history and current source, checks private
file types and identities, and runs operator/boundary tests. The only secret-scan
exception is an exact synthetic checksum in two named fixtures. Inline Gitleaks
bypass comments are ignored. No scanner detects every kind of sensitive content.

If a secret is committed, stop publication, revoke/rotate it through its provider,
and assess history, PR references, logs and caches. Deleting today's file does not
remove historical exposure. Use private reporting, never paste secrets into issues.
The public source checks do not certify tenant deployment or the private full suite.
