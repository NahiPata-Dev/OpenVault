# Judge Manual Test

## Multi-city catalog and assistant-assisted request

1. Start the backend and frontend using the setup commands in the repository
   [README](../README.md). For one-click judge entry, set
   `JUDGE_LOGIN_ENABLED=true` in the backend environment before startup. The
   panel is hidden by default; when disabled, use normal email/password
   sign-in. Sign out if already authenticated and open the public home page.
   In **Browse by city**, verify the city cards and their resource and
   organization counts load from the public summary. Select **Hyderabad**; the
   city card takes a signed-out visitor to sign-in.
2. Select **Requester** in **Judge access**. This opens the fixed fictional
   requester sample account (Tara Iyer, Uppal Circuit & Fabrication House).
   In **Resources**, filter by
   **Hyderabad**, **Uppal**, and the Uppal Circuit organization; then search for
   **CO2 Laser Cutter**. Confirm that the card shows the institution and city,
   and that the detail page identifies the sample resource.
3. Open the floating **Booking assistant** and send exactly:

   > I need a laser cutter in Hyderabad tomorrow afternoon for a robotics prototype

   The assistant should suggest the Hyderabad laser resource and report an
   eligibility failure. Select **View details**, open **Requirements**, and
   inspect **Your eligibility** to see Tara's `Laser Safety Induction LSI-101`
   blocker. “Tomorrow afternoon” is not a precise time range understood by the
   rules parser, and “robotics prototype” is not one of the allowed-use values;
   the assistant does not silently choose those details.
4. Do not confirm a request while the blocker remains: the normal request API
   saves a blocked submission as **INELIGIBLE**, which a manager cannot approve.
   Use **Switch role** to enter as **Lab Manager Meera Nair** and open
   **Training sign-off**. Select
   **Tara Iyer**, **CO2 Laser Cutter**, and the listed
   **Laser Safety Induction LSI-101** requirement. Record a verified **Valid**
   sign-off with a current start date and a future end date. This is demo
   training data, not a real-world certification.
5. Use **Switch role** to return to **Requester**. Ask the assistant about the
   requester's eligibility again and confirm the failure count is cleared; if
   needed, use **View details** >
   **Requirements** to inspect the individual check. Prepare a draft with a
   specific future slot and allowed use, for example:

   > Prepare a draft for CO2 Laser Cutter in Hyderabad tomorrow 3pm to 5pm for a project

   The assistant should return a draft for review. Check the displayed resource,
   start and end times (IST), and purpose. Nothing is submitted until you select
   **Confirm request**.
6. Select **Confirm request**. For an eligible slot, expect **Submitted —
   pending review**; the response is still a request, not a confirmed booking.
   If a blocker remains, the server may save an **INELIGIBLE** request instead.
7. Use **Switch role** to enter as **Lab manager**, open **Manager queue**, and
   locate Tara's CO2 Laser Cutter request. Review the current eligibility and
   conflict checks; select **Approve** with the required reason only when the
   service allows it. Verify the decision and booking in the service response.
   The assistant did not make this decision; the authorized manager did.

## Judge role access and verify blockers

1. With `JUDGE_LOGIN_ENABLED=true`, confirm that the login page shows exactly
   the Requester, Lab manager, and Auditor judge entry options. Selecting an
   option opens that role's fixed fictional sample account without requesting
   an email or password.
2. Open **Switch role** and move between Requester, Lab manager, and Auditor.
   Confirm the session remains in judge mode and the navigation changes with
   the selected role. The auditor view is read-only; it must not expose admin
   or demo-reset actions.
3. Use the requester role and open **CO2 Laser Cutter**. The current sample
   requester has a `Laser Safety Induction LSI-101` blocker. Confirm the
   requirements and next action are displayed. Submitting while blocked must
   not create an approved booking.
4. Switch to **Lab manager** and open **Training sign-off**. Select the
   requester, resource, and `Laser Safety Induction LSI-101`; record a verified
   **Valid** sign-off with a current start date and a future end date. This is
   sample training data, not a real-world certification.
5. Switch back to **Requester** and re-check eligibility. The service's
   response determines whether the request can proceed; a clear blocker is
   never assumed by the UI. A maintenance hold remains in force even after its
   review date and cannot be bypassed by judge access.

## Complete an eligible request and handover

6. As **Requester**, choose a resource and future interval for which the
   service reports no eligibility blockers. Submit a **Project** request for a
   one-hour interval. Use a start time within the next 15 minutes (IST) only if
   the approved session is expected to begin soon; otherwise choose a suitable
   future slot. An eligible submission should be **PENDING REVIEW**, not an
   approved booking. If the service reports a blocker, resolve it before
   expecting that state.
7. Switch to **Lab manager**. Open **Manager queue** and locate the request.
   Review its eligibility and allocation recommendation. Enter a reason and
   select **Approve** only if the service allows the decision. Verify the
   resulting booking and Access Contract from the service response.
8. Switch back to **Requester**. Open **My requests**, then
   **View Access Contract**. Check the **Access Contract (session conditions)**
   snapshot and its note that it is an application record, not a legal
   contract.
9. From **My requests**, complete **Check in** using the checklist. Expect a
   recorded check-in. Complete **Check out** with a worse physical condition
   than check-in (for example, change **OK** to **Minor wear**). Expect a
   discrepancy incident for review, without blame or penalty wording.

## Review the incident and audit history

10. Switch to **Lab manager**, open **Incidents**, and select the new
    discrepancy. Inspect its description, add a response if needed, and move it
    to **Under review** with a written reason. Resolve or dismiss it only after
    review, with a written rationale. Confirm the outcome in the service
    response and audit history.
11. Open **Audit timeline** and select **Oscilloscope Training Station**.
    Confirm events are in chronological order and include the request,
    approval, booking handover, incident, and resolution. Enter the booking ID
    from **My requests** under **Booking events** to inspect its audit records.
12. Return to the resource details and open **View Resource Memory**. Confirm
    the displayed metrics and recommendations are backend-provided and seeded
    data is labelled **DEMO DATA — not live institutional statistics**.

## Competing request / waitlist path

13. The judge requester role always represents one fixed account and cannot be
    used to impersonate a second requester. To test competition, prepare two
    separate normal requester accounts in an isolated test deployment. Submit
    a **Project** request from each for the same future one-hour
    **Electronics Bench** slot.
14. As a manager account, open **Manager queue**. Confirm both requests have
    eligibility and allocation recommendations. Enter a reason and select
    **Waitlist** for one request first, while both are still pending; then
    select **Approve** for the other. As the waitlisted requester, open **My
    requests** and confirm the waitlist status and stored decision explanation.
    The waitlisted request must not show a confirmed booking.

The automated API test uses an isolated, seeded SQLite database and test-only
credentials; it does not change the judge database. Judge login is an
evaluation shortcut controlled by `JUDGE_LOGIN_ENABLED`; leave it disabled in
real deployments.
