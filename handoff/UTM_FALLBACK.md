# Conditional UTM / Windows 11 fallback

Do not start this route merely because the Power BI connector is absent in a particular chat. Complete T08's actual plugin/web capability inspection. If a required authoring operation is genuinely unsupported, record its error and consider whether assisted browser editing solves it. Missing permissions or tenant policy must be resolved through the owner/admin, not bypassed with local tooling.

## Activation

Populate `config/fallback-decision.template.json` from real observations and owner approval, save it privately, and run `python scripts/webfirst_contracts.py fallback --input <private-decision.json>`. A pass is a policy check for authorised review, not permission to install software or proof the observation is genuine. T16 then governs the host changes.

## Existing VM first

1. Connect the specifically authorised Mac in Remote Desktop Commander. Its terminal/filesystem capabilities do not by themselves establish GUI control; verify actual browser/GUI tools before promising clicks.
2. Run `bash scripts/Inspect-UTM-Host.sh` on the Mac for read-only architecture, version and resource checks. Do not infer Apple Silicon or Intel from a browser user agent.
3. Identify the existing UTM VM and its current install stage from the user-selected VM/configuration or screenshot. Back up the powered-off VM before modifying it; do not create another VM by default.
4. Match Windows media to the host: ARM64 for Apple Silicon, x64 for Intel. Inspect the user's existing copy before downloading anything. Use UTM's normal virtualisation route with matching architecture and valid Windows licensing.
5. Review memory, CPU and disk allocation against actual host capacity and leave sufficient resources for macOS. No fixed allocation is justified before those resources are inspected.
6. Finish Windows setup and official UTM SPICE/guest tools as necessary. Preserve TPM, Secure Boot and endpoint controls. Do not use installer-check bypasses or disclose a product key in chat/logs.
7. Apply ordinary Windows updates. On ARM, verify Microsoft's documented September 2025 cumulative fix or its superseding updates using the actual build. Do not require the old KB to appear separately after a newer cumulative update.
8. Use a specifically approved shared project folder. Do not expose the entire home folder, configure public inbound ports, or disable security to make networking work.
9. Run `scripts/Inspect-PowerBI-Guest.ps1` inside Windows to collect read-only guest readiness. Install the regular Power BI Desktop app from Microsoft only at T17's approval step, not the Report Server edition.
10. Open the research PBIP, fix genuine native errors, refresh both sources, save a new PBIX, close and reopen it, and verify the active semantic model, visual bindings and full exports. A renamed ZIP or thin live-connected report is not a self-contained replacement PBIX.

UTM provides a Windows installation procedure. Microsoft's Power BI requirements now discuss Windows on ARM, but its virtual-desktop support statement names Azure Virtual Desktop and Windows 365 and does not certify UTM. Treat UTM performance/compatibility as a smoke-test gate, not a guarantee. Web acceptance remains preferred.

## Official references

- UTM Windows guide: https://docs.getutm.app/guides/windows/
- Microsoft Desktop installation and requirements: https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-get-the-desktop

No VM, installer, license or Windows security setting was changed while preparing this package.
