# Current-source privacy review — 28 October 2026

This patch removes unnecessary personal account, workstation or document metadata
from the current source. Original Git history is assessed separately and is not
rewritten. Native authentication profiles, deployment bindings and running services
are unchanged. Encryption is outside this review.

Local mount links were replaced with portable source links or private-workspace placeholders. Generic-key alerts identify two synthetic key digests and two crosswalk relationship labels, not service credentials. The source detector regex and example-user path are intentional detection/examples, not real workstation disclosures.
