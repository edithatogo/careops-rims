# RIMS public source edition

> Sanitised development source with fresh history. Read [scope](PUBLIC_SOURCE.md)
> and [security setup](SECURITY.md). Native acceptance is not claimed.

# CHHHS research publications: current web-first work package

Start with [START_HERE.md](START_HERE.md) and [the plugin opening prompt](handoff/POWERBI_PLUGIN_START_HERE.md). Ten new Conductor tracks prioritise the existing Power BI report and ordinary web UI. UTM/Desktop is conditional. No live report/model/VM changes are claimed by this release.

The earlier v0.3 source is preserved as a baseline with known defects; old deployment instructions below are historical, not the current route.

---

## Historical v0.3 source README

# CHHHS Research Publications

Browser-first Power BI/Fabric project for a monthly Cairns and Hinterland Hospital and Health Service publication report.

The canonical report combines **PubMed affiliation discovery** with the **Queensland Health DORA CHHHS RSS feed**, deduplicates cross-source records conservatively and retains source/attribution evidence.

Start with [START_HERE.md](START_HERE.md). For browser deployment without Power BI Desktop, use [docs/FABRIC_BROWSER_DEPLOYMENT.md](docs/FABRIC_BROWSER_DEPLOYMENT.md).

Core governance artefacts are in `contracts/`; implementation history and acceptance gates are in `conductor/`.
