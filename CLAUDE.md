# SpeedSpot Mapper — Project Instructions

## Project identity

SpeedSpot Mapper is a public-facing Smart Cities application that helps ordinary people understand and explore internet connectivity in their neighbourhoods.

Core slogan: Your city. Your connection.

## Product philosophy

Build a genuinely useful application for the general public, not a complicated telecom monitoring dashboard.

Priorities:
1. User friendliness.
2. Convenience.
3. Accessibility.
4. Minimal aesthetics.
5. Functional reliability.
6. Technical quality.

## Design system

Use a minimal, premium and welcoming aesthetic.

Colours:
- Warm off-white: #F7F8F5
- Soft sage: #DCE9DF
- Natural green: #638B72
- Deep forest: #263B32
- Neutral grey: #E9EDE8

Design characteristics:
- Generous whitespace.
- Clean typography.
- Rounded cards.
- Subtle shadows.
- Simple icons.
- Smooth transitions.
- Responsive layouts.
- Mobile-first design.

Avoid:
- Neon colours.
- Excessive gradients.
- Cluttered dashboards.
- Unnecessary animations.
- Technical jargon in public-facing interfaces.

## Navigation

1. Home
2. Explore Map
3. Speed Test
4. Compare Providers
5. Insights

## Technical stack

- Python Flask backend.
- HTML, CSS and JavaScript frontend.
- SQLAlchemy ORM.
- SQLite initially.
- Leaflet.js mapping.
- Genuine speed-test integration.
- Browser geolocation with consent.
- Git and GitHub.

## Functional requirements

- Download and upload speed measurements.
- Latency and jitter.
- Consent-based geolocation.
- IP-to-ASN provider identification.
- Approximately 150 m grid aggregation.
- Network Quality Index.
- Crowd-sourced heatmap.
- Provider rankings.
- Guided navigation.
- City planner analytics.

## Engineering standards

- Build incrementally.
- Use modular architecture.
- Test every important feature.
- Never fabricate actual measurements.
- Never claim untested features work.
- Protect user privacy.
- Keep secrets outside source control.
- Maintain documentation.
- Explain important technical decisions.

Always inspect the existing code before modifying it. Preserve working functionality and avoid unnecessary rewrites.

After completing each development phase, update PROJECT_STATUS.md with implemented functionality, test results, known issues and remaining tasks.
