---
name: fact-grounding
description: How to turn calendar lines and current weather into facts an excuse can safely lean on. Use whenever gathering facts for an excuse, reading calendar.md, or fetching weather for a city.
---

# Fact grounding

An excuse is believable when the facts in it match the world the recipient can see. Your job is to hand the Storyteller facts that are real, so the excuse never depends on something invented.

## Calendar facts

`calendar.md` has one line per event: `date time title (attendees)`.

- Quote events exactly. Never add an event, change a time, or guess attendees.
- Mark each useful event as one of: **blameable** (dentist, car service, anything outside work the user could have been at), **conflicting** (overlaps the thing being skipped), or **skippable** (a meeting the user would rather miss).
- A recipient who is an attendee can check the calendar. Flag any event whose attendees include the recipient as **checkable**: an excuse must not contradict it.

## Weather facts

Fetch current weather with web fetch from Open-Meteo, no key needed:

`https://api.open-meteo.com/v1/forecast?latitude=<lat>&longitude=<lon>&current_weather=true`

Coordinates for the supported cities:

| City | Latitude | Longitude |
|---|---|---|
| london | 51.5 | -0.12 |
| new york | 40.71 | -74.01 |
| san francisco | 37.77 | -122.42 |
| bangalore | 12.97 | 77.59 |
| dubai | 25.2 | 55.27 |

Read `current_weather.temperature` and `current_weather.weathercode`. Codes 51 and above mean rain, snow or storms and can support a travel or commute excuse. Codes 0 to 3 are clear or cloudy: do not suggest a weather excuse.

If the city is unknown, use London and say so. If the request fails or times out, write `weather unavailable` and continue. A made-up weather fact is worse than none, because the recipient can check it in seconds.

## Output

At most 8 bullets, each tagged `[calendar]` or `[weather]`, each one a fact the Storyteller can quote.
