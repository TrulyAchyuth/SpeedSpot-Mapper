# Decision 0001: Speed-test engine — M-Lab ndt7

**Status:** accepted (2026-11-01) · **Revisit:** after the campus pilot, or if M-Lab's terms change

## Question
Which genuine, browser-based speed test should SpeedSpot use: **M-Lab ndt7** or **Cloudflare's speed test**? We never simulate measurements, so whichever we pick must run real tests against real servers.

## What was checked, and how
Everything below comes from the providers' own documentation, their published code, or live checks of their servers' response headers on 2026-11-01. Nothing is from memory.

| | **M-Lab ndt7** (`@m-lab/ndt7` 0.1.5, Apache-2.0) | **Cloudflare** (`@cloudflare/speedtest` 1.15.0, MIT) |
|---|---|---|
| **Who runs the servers** | Measurement Lab, a non-profit research consortium | Cloudflare, a commercial CDN |
| **Download / upload** | Yes. About 10 s each over WebSockets, from Web Workers | Yes. HTTP GET/POST of increasing sizes to `speed.cloudflare.com/__down` and `/__up` |
| **Latency** | TCP MinRTT reported by the server (kernel TCP_INFO) during the test | Idle latency from 20 small requests (PerformanceResourceTiming), plus loaded latency |
| **Jitter** | Not reported directly. We use TCP RTTVar, the kernel's RTT variation, as an approximation | Reported directly ("average distance between consecutive latency measurements") |
| **Public data exposure** | **Every test is published** as open public-domain data, **including the IP address**, date and time ([privacy policy v4, 17 Feb 2025](https://www.measurementlab.net/privacy/)) | Not published raw. The package README says "measurement results are collected by Cloudflare on completion for the purpose of calculating aggregated insights". The code POSTs final results to `speed.cloudflare.com/__results` by default |
| **IP retention** | "All experiment data is retained indefinitely". Deletion is only possible with proof from your ISP that you held the IP | Cloudflare's Speed Test page says it receives the IP, derives city/country/ASN, truncates stored IPs to /24 (IPv4) or /48 (IPv6), and shares anonymised results with measurement partners. **No retention period found** |
| **Leaks to page scripts** | None beyond the test itself | Responses expose `cf-meta-ip`, `cf-meta-latitude/longitude/city/postalCode` (IP geolocation) to any page that calls them (seen in live headers) |
| **CORS** | Locate API: `Access-Control-Allow-Origin: *` (checked live). Tests use WebSockets, which CORS doesn't restrict | `Access-Control-Allow-Origin: *` and `Timing-Allow-Origin: *` on `__down`, with preflight allowed for `__up` (checked live) |
| **Browser compatibility** | Needs WebSocket + Web Workers, supported by all current browsers. Workers must be served from our own origin (we vendor them) | Needs Fetch + PerformanceResourceTiming with Timing-Allow-Origin. Supported by current browsers |
| **Third-party use allowed?** | **Yes, explicitly.** Third-party clients are a documented use case and must show users the privacy policy. Commercial integrations must contribute to the platform ([AUP](https://www.measurementlab.net/aup/)) | **Not documented.** The MIT licence covers the code, not use of Cloudflare's servers by other sites. An experimental `authorizationToken` "attributing the test to a registered customer" hints at a customer programme |
| **Usage limits** | Documented: interactive users "must not run more than 40 tests per day". M-Lab may add registration or fees for usage tiers | No published limits for third-party embedding |
| **Server choice** | Locate API returns the nearest servers (4 servers in Chennai for this location, checked live) | Nearest Cloudflare data centre (anycast) |
| **Data use** | About 10 s per direction at full speed, so a fast connection can use hundreds of MB | Ramps up to 250 MB downloads. Cloudflare says up to ~200 MB |

## Decision
**Use M-Lab ndt7.** The deciding factor is that it's **explicitly permitted and documented** for third-party, non-commercial clients like ours, with a clear published rate limit. Cloudflare's measurement quality (especially native jitter) is attractive, but its terms for other sites using its servers aren't published, and it sends results to Cloudflare by default.

M-Lab's big privacy cost, publishing the IP address forever, is handled by:
1. **Telling users plainly before every test** (an M-Lab AUP requirement as well as our own principle). The button reads "Agree and start test".
2. Never sending M-Lab anything else. No location goes to M-Lab: `client_name=speedspot-mapper` is the only metadata.
3. Enforcing M-Lab's 40-tests-a-day limit in the browser.

## Consequences
- **Jitter is approximate** (TCP RTTVar under load). This is documented on the Speed Test page footnote and in the API docs. If it proves misleading in the pilot, we could add a short idle-latency series.
- The engine sits behind `frontend/static/js/speedtest-engine.js` (`runSpeedTest()`), so switching later only means changing that file plus the server's `ENGINES` allow-list.
- If SpeedSpot ever becomes commercial, M-Lab requires a contribution to the platform.
- **Not yet verified:** a real end-to-end test from a browser, and accuracy against a reference test (see PROJECT_STATUS.md).

## Sources
- M-Lab privacy policy v4: https://www.measurementlab.net/privacy/
- M-Lab Acceptable Use Policy: https://www.measurementlab.net/aup/
- ndt7-js source (`src/ndt7.js`), npm `@m-lab/ndt7@0.1.5`
- Cloudflare speedtest README and `dist/speedtest.js`, npm `@cloudflare/speedtest@1.15.0`
- Cloudflare Speed Test privacy notes: https://radar.cloudflare.com/speedtest and https://www.cloudflare.com/speed-test/
- Live response headers: `speed.cloudflare.com/__down`, `__up` (OPTIONS) and `locate.measurementlab.net/v2/nearest/ndt/ndt7`, fetched 2026-11-01
