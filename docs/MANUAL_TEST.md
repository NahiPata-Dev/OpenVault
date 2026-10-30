# Judge Manual Test

## Sign in and verify the training blocker

1. Start the backend and frontend using the setup commands in the repository
   README. Open `http://127.0.0.1:5173`.
2. The login page displays the shared demo password, `northstar-demo`. Select
   **Requester C**. The app should open the resource list with a **DEMO DATA**
   banner.
3. Search for **oscilloscope**, then select **View details** on **Oscilloscope
   Training Station**. Confirm that the training requirement and supervised
   windows are shown.
4. In **Request this resource**, leave **Project** selected, enter a valid
   start and end in IST, and select **Submit request**. Expect **INELIGIBLE**
   with the `missing_training` blocker and its next action. No booking should
   be created.
5. To check the maintenance blocker, return to **Resources**, open
   **Maintenance Hold Resource**, submit a valid interval, and confirm the
   `maintenance_hold` blocker. The backend must not approve it.

## Complete an eligible request and handover

6. Select **Log out**, then sign in as **Requester A** with the same password.
   Find the oscilloscope station, open its details, and submit a **Project**
   request for a one-hour interval. Use a start time within the next 15 minutes
   (IST) so the check-in window is open after review. Expect **PENDING REVIEW**,
   not an approved booking.
7. Log out and sign in as **Lab Manager**. Open **Manager queue** and locate
   Requester A’s oscilloscope request. Review its eligibility and allocation
   recommendation. Enter a reason and select **Approve**. Expect a confirmed
   booking and an Access Contract.
8. Log out and sign in as **Requester A**. Open **My requests**, then
   **View Access Contract**. Check the **Access Contract (session conditions)**
   snapshot and its note that it is an application record, not a legal
   contract.
9. From **My requests**, complete **Check in** using the checklist. Expect a
   recorded check-in. Complete **Check out** with a worse physical condition
   than check-in (for example, change **OK** to **Minor wear**). Expect a
   discrepancy incident for review, without blame or penalty wording.

## Review the incident and audit history

10. Sign in as **Lab Manager**, open **Incidents**, and select the new
    oscilloscope discrepancy. Inspect its description and any recorded
    responses. **Current UI limitation:** the detail page has no response form
    or **Under review** action. The backend requires an incident to enter
    review before it can be resolved, so do not submit **Resolve incident**
    while the incident is still open. The API journey test verifies the full
    manager review, response, and resolution sequence.
11. Open **Audit timeline** and select **Oscilloscope Training Station**.
    Confirm events are in chronological order and include the request,
    approval, booking handover, incident, and resolution. Enter the booking ID
    from **My requests** under **Booking events** to inspect its audit records.
12. Return to the resource details and open **View Resource Memory**. Confirm
    the displayed metrics and recommendations are backend-provided and seeded
    data is labelled **DEMO DATA — not live institutional statistics**.

## Competing request / waitlist path

13. Sign in as **Requester A** and submit a **Project** request for a future
    one-hour slot on **Electronics Bench**. Sign in as **Requester B** and
    submit another request for the same interval.
14. As **Lab Manager**, open **Manager queue**. Confirm both requests have
    eligibility and allocation recommendations. Enter a reason and select
    **Waitlist** for one request first, while both are still pending; then
    select **Approve** for the other. As the waitlisted requester, open **My
    requests** and confirm the waitlist status and stored decision explanation.
    The waitlisted request must not show a confirmed booking.

The automated API test uses an isolated, seeded SQLite database and test-only
credentials; it does not change the judge database.
