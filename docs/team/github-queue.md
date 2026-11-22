# Open GitHub work for Lumi

Snapshot from November 22, 2026. GitHub listed 13 open pull requests and 19 open issues. The PR descriptions report their own test results. Use the checks below to verify the changes together before the demo.

Start with sign-in, since real reports and votes depend on it. The UI work is stacked. Review and merge in this order so each PR is compared against the right base: **#64 → #69 → #70 → #71 → #75**. Coordinate #77 with that stack because both edit the sign-in header.

## Open pull requests

| PR | What it does | What to check |
|---|---|---|
| [#77 Sign-in fix](https://github.com/LuisMend12/Lumi/pull/77) | Updates Clerk and replaces old sign-in controls so people can log in again. | Sign in by email and Google, then submit a report and vote. Keep the new Clerk controls when combining the header edits. |
| [#75 Winter design](https://github.com/LuisMend12/Lumi/pull/75) | Adds the Storm Center design, low-contrast map tiles, clearer route cards, and a live strip for reports. Landmark routes can open from a link. | Check route fit, report labels, and the scrolling strip on a phone. |
| [#74 Photo picker](https://github.com/LuisMend12/Lumi/pull/74) | Clears the old photo preview when the browser returns no file after canceling the picker. | Pick a photo, open the picker again, then cancel. Check that the empty photo prompt returns. |
| [#73 Reliability fixes](https://github.com/LuisMend12/Lumi/pull/73) | Counts only saved demo votes, retries a dropped database connection once, and shows a clearer error when the server returns an HTML error page. | Check the retry and vote-count tests. Confirm the retry cannot duplicate a write if the connection drops after the database saves it. |
| [#72 Upload size guard](https://github.com/LuisMend12/Lumi/pull/72) | Rejects oversized photo requests before the API reads the upload. | Confirm a normal phone upload still works through the deployed proxy. |
| [#71 Route pickers](https://github.com/LuisMend12/Lumi/pull/71) | Adds From and To pickers for BU landmarks, a My location choice, and map zoom buttons. | Make a route using only the keyboard. On a phone, grant and deny location permission. |
| [#70 Route editing](https://github.com/LuisMend12/Lumi/pull/70) | Protects a finished route from stray taps, labels the pins A and B, and explains the route styles and modes. | Confirm a third tap keeps the route in place and the edit controls still move either pin. |
| [#69 Location opt-in](https://github.com/LuisMend12/Lumi/pull/69) | Keeps the first visit focused on the map and makes nearby questions expandable. | In a fresh browser profile, confirm location permission appears after opting in, then try the nearby vote. |
| [#64 Live refresh](https://github.com/LuisMend12/Lumi/pull/64) | Refreshes visible routes and reports every 20 seconds and drops results from older route requests. | Block a segment on one phone and watch the second update. Change endpoints while a request is loading. |
| [#63 Photo review retry](https://github.com/LuisMend12/Lumi/pull/63) | Retries pending photos every 30 seconds and saves the outcome so it survives a restart. | Restore Mastra after a pending upload and verify the verdict. Check whether reopening votes between upload and review produce the same state after a restart. |
| [#62 Demo script](https://github.com/LuisMend12/Lumi/pull/62) | Adds the demo route, presentation steps, and fallbacks. The PR records a measured detour and reopening. | Rehearse the script in the browser and on a phone. |
| [#52 Accessible notice](https://github.com/LuisMend12/Lumi/pull/52) | Shows a note on the route card when Accessible starts or ends away from the chosen point. | Use it with #51 and confirm the note and dashed gap are visible. |
| [#51 Step-free starting points](https://github.com/LuisMend12/Lumi/pull/51) | Moves an Accessible endpoint off a stairs-only spot when it finds a mapped step-free connection within 100 meters. | Try GSU and Lansdowne. Confirm the route card explains the gap and the other modes keep their original endpoints. |

## Open issues

| Issue | What it means | Where it stands |
|---|---|---|
| [#76 Clerk sign-in](https://github.com/LuisMend12/Lumi/issues/76) | The current SDK is rejected, so people cannot sign in to report or vote. | #77 has the upgrade. Verify the real sign-in flow. |
| [#68 Winter look](https://github.com/LuisMend12/Lumi/issues/68) | Give the map and report states a consistent visual style. | #75 implements Storm Center. Check the phone layout. |
| [#67 More ways to start a route](https://github.com/LuisMend12/Lumi/issues/67) | People need landmark and location choices when tapping the map is hard or imprecise. | #71 adds the controls. Test keyboard and phone input. |
| [#66 Route controls](https://github.com/LuisMend12/Lumi/issues/66) | A stray tap can wipe a route, and pins and line styles need labels. | #70 addresses both. Check the legend and edit controls. |
| [#65 First-visit location prompt](https://github.com/LuisMend12/Lumi/issues/65) | New visitors see a location prompt before they know what the map does. | #69 adds opt-in and a smaller nearby prompt. |
| [#61 Reliability fixes](https://github.com/LuisMend12/Lumi/issues/61) | Vote totals, database reconnects, and some server errors can be misleading. | #73 addresses all three. |
| [#60 Reported location](https://github.com/LuisMend12/Lumi/issues/60) | Coordinates come from the device. A report photo and a nearby check cannot independently verify where a person was. | Decide how to describe this demo limitation and whether to add safeguards. |
| [#59 Updates across devices](https://github.com/LuisMend12/Lumi/issues/59) | One phone can miss a closure added by another until someone reloads. | #64 adds automatic refresh. Try it on two devices. |
| [#58 Large photo uploads](https://github.com/LuisMend12/Lumi/issues/58) | The server can spend resources reading an oversized photo before rejecting it. | #72 adds an early size check. Confirm normal uploads still pass through the host. |
| [#57 Vote limit](https://github.com/LuisMend12/Lumi/issues/57) | Saying “still blocked” three times can trigger the photo requirement on the next vote. | Decide whether confirmations should count toward the limit. |
| [#56 Broken preview](https://github.com/LuisMend12/Lumi/issues/56) | Canceling the picker after choosing a photo can leave a broken preview. | #74 clears it. Test canceling in the browser. |
| [#55 Nearby vote retry](https://github.com/LuisMend12/Lumi/issues/55) | A failed vote can hide the buttons, and dismissing a second sidewalk can bring back the first prompt. | Keep retry available after failure and remember which sidewalks were dismissed. |
| [#54 Old route overwrites a new one](https://github.com/LuisMend12/Lumi/issues/54) | A slow response can draw the previous route after the user picks new endpoints. | #64 adds a stale-result check. Test rapid edits and a pending report or vote. |
| [#53 Pending photos](https://github.com/LuisMend12/Lumi/issues/53) | A photo can stay under review after the reviewer comes back online. | #63 adds retries. Verify that a later verdict survives restart. |
| [#33 Accessible gaps](https://github.com/LuisMend12/Lumi/issues/33) | Some landmarks touch the walking network through stairs, so Accessible can return no route. | #51 moves eligible endpoints and #52 explains the gap. Try both together. |
| [#15 Deploy and rehearse](https://github.com/LuisMend12/Lumi/issues/15) | The demo needs a hosted site and an end-to-end phone rehearsal. | #62 covers the script. Verify HTTPS, location, uploads, and fallback cases on the hosted build. |
| [#14 Login](https://github.com/LuisMend12/Lumi/issues/14) | Reports and votes need a stable user ID so each person counts once. | Clerk is already integrated. Verify working login and authenticated writes after #77, then reconcile the old issue. |
| [#8 Demo route and services](https://github.com/LuisMend12/Lumi/issues/8) | Confirm the demo detour, the mapped paths, database access, and photo verdicts. | #62 records the route rehearsal. Record the path checks and current service checks in the issue using the Mastra photo-review script. |
| [#7 Parallel sidewalks](https://github.com/LuisMend12/Lumi/issues/7) | Two paths joining the same intersections can share a closure even when one is clear. | Parked unless it affects the demo route. |
