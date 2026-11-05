# Changelog

All notable changes to Plumb. Versions follow [semantic versioning](https://semver.org): a change that moves anyone's grade is at least a minor version.

## [1.0.1] — 2026-11-05

### Added
- Goals can track all liquid savings together (`"bucket": "liquid"`), which suits emergency and move-out funds.

### Changed
- The Plumb wordmark in reports is now black.
- Releases include `plumb.zip` for the Claude app's "Upload a skill" screen, next to `plumb.skill`.
- Clearer install steps for non-technical users, including how to share Plumb with a friend.

### Fixed
- Net worth chart labels no longer repeat (e.g. two "₱1.8M" ticks).
- What-if can add assets (`new_assets`), so a home or car purchase no longer shows the whole loan as a loss in net worth.

## [1.0.0] — 2026-11-05

First versioned release.

### Added
- **One-click install:** every GitHub Release includes a ready-to-install `plumb.skill`.
- **Goal timelines:** each goal shows its monthly pace, an estimated date and, with a deadline, how much it needs per month. Goals can track one account or your whole net worth, and can start without a target.
- **What-if:** compare today with a change (new rent, a raise, a loan, a big purchase) before you decide. Nothing is saved.
- **Income and spending chart** in the report, scaled to 30 days so biweekly and monthly check-ins compare.
- **Typo guard:** a balance that jumps suspiciously isn't recorded until you confirm it.
- **Automatic backups:** the last 10 versions of your ledger are kept, with `backups` and `restore` commands.
- **Foreign-currency holdings:** keep US ETFs and other foreign assets in their own currency. Exchange-rate moves don't count as progress or loss in your score.
- **Question cards:** tap-to-answer questions where your Claude app supports them, a checklist so Plumb only asks about what you have, and quick, detailed or screenshot modes for entering balances.
- Automated tests on every push and pull request, a contributing guide, and issue templates.

### Changed
- The report's assessment is a plain paragraph instead of a highlighted callout.
- Revaluation reminders and the equity table only cover assets valued by estimate (property, vehicles, businesses, valuables).
- Report titles use the possessive "’s" for every name ("Louis’s").
