# A location on a mirrored event, and planned drives (nemik:W723, life:W52)

Read 2026-10-19 from web search results; nothing here was tried against a real phone or account.

life's ask: the operator wants no hand entry of planned drives. `nemik-calendar-write` emits one
VEVENT per dated waypoint (UID `nemik:<repo>:W<n>`) with SUMMARY and an optional VALARM, and no
LOCATION. Two questions: can a waypoint carry an address (nemik:W721, W722), and do Waze and
Google Maps read it?

## What was found

- **Waze reads calendar events and sends a leave-by alert.** In Waze: Plan a drive, Connect
  calendar, allow access. It syncs with the device's default calendar, so a calendar kept in
  another app has to be synced into that default calendar first. All calendars are included unless
  hidden under Plan a drive, Your calendars. Source: [Sync your calendar with
  Waze](https://support.google.com/waze/answer/6341187?hl=en) (Waze help, via search summary).
- **The event needs a complete address in its location**: street, house number and city. If the
  Planned drives screen offers "Set address", the address was not understood and no reminder is
  sent. Alerts use real-time traffic and the expected drive time, and the app needs location
  access "Allow all the time" (Android) or "Always" (iOS). Same Waze help page, and
  [SlashGear's summary](https://www.slashgear.com/1944201/hidden-waze-features/), which adds that
  the commute event needs a destination and an arrival time.
- **Apple Calendar** sets a leave-time alert from an event's location and skips destinations more
  than three hours away: [Apple Calendar help, Add locations and travel
  info](https://help.apple.com/calendar/mac/10.11/en.lproj/icl43600.html) (an older macOS page).

## What could not be confirmed

- Whether an event from a **subscribed ICS feed** (as opposed to one written into the device's
  default calendar) is read by Waze's calendar sync. Waze reads the device's default calendar, so
  the answer depends on whether the feed is subscribed into a calendar the device syncs.
- Whether **Google Calendar** gives a leave-by notification for events from a subscribed ICS feed.
  The search found a third-party add-on page saying Google Calendar has no built-in automatic
  travel time; that is a vendor's marketing claim and was not checked against Google's own help.
- Whether Google Maps itself reads calendar events for planned drives.
- Whether a VALARM written by nemik-calendar-write could be placed at the leave-by moment: that
  depends on a travel time nemik does not have.

## So

Item 1 (a LOCATION on the event) is necessary and is carded. Whether it is sufficient for the
operator's phone depends on which calendar the phone syncs the mirrored events into, and that is
a question for the operator's setup, not one these sources settle: **operator: act** try one dated
waypoint with a full street address as its location, once nemik:W722 lands, and see whether Waze's
Planned drives lists it.
