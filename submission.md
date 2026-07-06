# Codebase Map

**Main Files and Roles:**
* `app.py`: Acts as the Flask application factory and handles database setup.
* `models.py`: Contains the SQLAlchemy database models for all entities (Users, Songs, Playlists, etc.).
* `routes/` directory: Handles incoming HTTP requests, routes them, and passes data to the services (e.g., `songs.py`, `playlists.py`).
* `services/` directory: Contains the actual business logic of the app where calculations and data manipulation happen (e.g., `streak_service.py`, `feed_service.py`).

**Data Flow Trace:**
When a user rates a song, the request hits the application through the `POST /songs/<song_id>/rate` endpoint. This is caught by `routes/songs.py`. The route doesn't process the logic itself; instead, it delegates the action by calling `notification_service.rate_song()` in the services layer, which updates the database.

## Bug 1: My listening streak keeps resetting
1. **How I reproduced it:** Looked at the logic for when a streak increments versus resets, noting that the bug specifically triggers when a user tries to continue their streak on a Sunday. 
2. **Navigation Strategy:** Checked `README.md` which pointed to `streak_service.py`. I traced the data flow inside `update_listening_streak()` and read the conditional block that determines when a streak increments. 
3. **The Root Cause:** The code incorrectly included `and today.weekday() != 6` in the increment condition. `today.weekday() == 6` corresponds to Sunday. Because of this, any time a user listens on a Sunday, the condition evaluated to False and dropped to the `else` block, incorrectly resetting their streak to 1 instead of incrementing it.
4. **Fix & Side-Effect Check:** Removed the `and today.weekday() != 6` condition entirely so the line is simply `elif days_since_last == 1:`. To check for side-effects, I verified the `days_since_last == 0` check directly above it to ensure same-day listens are still safely ignored, confirming the fix only impacts consecutive-day logic.

## Bug 2: Friends Listening Now shows people from yesterday
1. **How I reproduced it:** Reviewed the logic governing the recency cutoff for the "Friends Listening Now" feed to see why old listening events were surfacing.
2. **Navigation Strategy:** The README pointed to `feed_service.py`. I examined the `get_friends_listening_now()` function and traced how it calculates the `cutoff` variable to filter recent events.
3. **The Root Cause:** The `cutoff` calculation relies on a global constant `RECENT_THRESHOLD`. This was incorrectly set to `timedelta(hours=24)`. Therefore, the "Now" feed was sweeping up an entire day's worth of listening history instead of current activity.
4. **Fix & Side-Effect Check:** Changed `RECENT_THRESHOLD` from `timedelta(hours=24)` to `timedelta(hours=1)` so only genuinely current listeners appear. To ensure no side-effects, I checked the other function in the file, `get_activity_feed()`. Since `get_activity_feed()` relies on a strict `.limit()` parameter instead of a time threshold, I confirmed it was completely unaffected by this change.

## Bug 3: The same song keeps showing up twice in search
1. **How I reproduced it:** Triggered the search endpoint with a song known to have multiple tags, observing that the JSON response returned an identical song object for every tag associated with it.
2. **Navigation Strategy:** The README indicated the issue was inside `search_service.py`. I examined the `search_songs()` function and looked at the SQLAlchemy query structure, specifically spotting the `outerjoin` operation.
3. **The Root Cause:** The query joins the `song_tags` association table but lacks a `.distinct()` modifier. In SQL, joining a many-to-many relationship causes the database to return a row for every joined tag. Because the code did not filter these out, songs with multiple tags were duplicated in the final list.
4. **Fix & Side-Effect Check:** Inserted `.distinct()` into the SQLAlchemy query chain right before `.all()`. To verify no side-effects were introduced, I checked the other function in the file, `get_song()`. Because `get_song()` utilizes a direct `db.session.get(Song, song_id)` lookup rather than a joined query, it remains completely unaffected.

## Bug 4 (Stretch): I got notified when a friend added my song to a playlist but not when they rated it
1. **How I reproduced it:** Simulated rating a friend's song and then checked the notifications endpoint for that friend, verifying that no "song_rated" notification was generated.
2. **Navigation Strategy:** The README indicated the issue was inside `notification_service.py`. I compared the working `add_to_playlist()` function to the broken `rate_song()` function to see how their logic differed. 
3. **The Root Cause:** The root cause is architectural omission. While `add_to_playlist()` properly invokes `create_notification()` after saving its data, `rate_song()` lacked this function call entirely. It successfully saved the rating to the database but never triggered the subsequent notification workflow.
4. **Fix & Side-Effect Check:** I added the `create_notification()` call to the end of `rate_song()`, ensuring it included the `if song.shared_by != user_id:` condition so users don't get notified for rating their own songs. To check for side-effects, I verified that the core rating logic (updating existing vs. creating new ratings) was untouched and still returns the correct `Rating` object.

## Bug 5 (Stretch): The last song in a playlist never shows up
1. **How I reproduced it:** Created a playlist, added multiple songs, and fetched the playlist data to confirm the final song added was consistently missing from the returned list.
2. **Navigation Strategy:** The README indicated the issue was inside `playlist_service.py`. I focused on the `get_playlist_songs()` function since it handles returning the ordered list of songs.
3. **The Root Cause:** The return statement utilized a Python list slice: `songs[:-1]`. This slice syntax explicitly tells Python to return the list excluding the final element. Because of this, the last queried song was always intentionally dropped before the JSON response was constructed.
4. **Fix & Side-Effect Check:** Removed the `[:-1]` slice so the list comprehension iterates over the full `songs` array. To check for side-effects, I reviewed `get_playlist()` and `get_user_playlists()`. Since those functions only fetch playlist metadata and do not handle the `playlist_entries` join, they were completely unaffected by this change.

---

# Stretch Feature: Regression Test
* **Test File:** `tests/test_notifications.py` (New file created)
* **Behavior Verified:** Verifies that calling `rate_song()` successfully triggers the creation of a "song_rated" notification for the user who originally shared the song.
* **Why it would have failed previously:** Under the buggy code, `rate_song()` completely lacked the `create_notification()` function call. The test would have successfully added the rating to the database, but the final assertions checking the `Notification` query would have thrown an `AssertionError` because the length of `notifications` would be 0 instead of 1.

# AI Usage
* **Codebase Navigation:** I asked the AI to explain the structural differences between `add_to_playlist()` and `rate_song()` in the notification service, which helped me identify the missing function call for Bug 4.
* **Debugging Verification:** When investigating Bug 3, I provided the AI with the SQLAlchemy query from `search_service.py` to confirm my suspicion about how `outerjoin` behaves without a `.distinct()` modifier.
* **Course-Correction / Verification:** The AI initially suggested checking the `curl` commands manually in my terminal to verify fixes, but due to time constraints, I overrode that suggestion and verified the logic fixes directly by reviewing the surrounding boundary conditions in the code itself.

