# Colorado Ballot Explorer: Vision

*Working draft, October 2026. Scope: Colorado only. Other states may follow next year.*

## Why we're doing this

Voting well is harder than it should be, and the hard part usually isn't the top of the ballot.

- **Ballots are long, and most of it is local.** A single Boulder ballot in 2026 carries federal and state races, 14 statewide measures, 13 judges up for retention, county offices, city races and measures, and special district questions. The local items are the ones people know least about and the ones existing tools miss most often.
- **The official information exists, but it's scattered.** The state Blue Book, county clerk sample ballots, city council packets, local news, candidate sites. Nobody should need six tabs and an afternoon to understand their own ballot.
- **Existing tools are incomplete or clunky.** BallotReady covers federal, state and county measures by default and leaves municipal and special district items to paid partner versions. Ballotpedia is broad but hard to navigate and thin at the local level. When we built a Boulder worksheet from news coverage alone, it missed six minor-party candidates, seven appellate judges and every local measure outside the City of Boulder.
- **People arrive unprepared.** Many voters decide down-ballot items in the booth, or skip them. A simple way to research ahead and bring your decisions with you changes that.

**The point:** give every Colorado voter an easy, complete, private way to see what's on their ballot, look into each item from good sources, keep track of what they're deciding, and take their choices with them when they vote.

## What it is

A free, nonpartisan public service where Colorado voters enter a ZIP code or address and see every contest and question on their ballot. They can mark choices, keep notes, follow links to research, and write out a short list to use when filling in their mail ballot or voting in person. Everything stays on their own device.

## Scope

- **Colorado only.** Doing one state completely is better than many states partially, and completeness is the whole point.
- **Why Colorado works as the starting point:**
  - 64 counties, a manageable number to verify by hand.
  - Counties publish compiled sample ballots (Boulder and Larimer both posted theirs in September 2026), which give a clear definition of "complete."
  - The state publishes the nonpartisan Blue Book for every statewide measure.
  - All-mail voting means every voter gets a ballot weeks ahead, which is exactly the window when people research and decide.
- **Out-of-state ZIP codes** get a short, friendly message that the app covers Colorado only, with a link to that state's official election site.
- **Expansion is a later decision.** After a full Colorado cycle, we'll decide whether and where to expand next year, based on what we learned about data collection, verification effort, and how people used it.

## Who it's for

- Colorado voters who want to understand their whole ballot, not just the headline races.
- First-time and newly moved voters who don't know their local districts.
- People who decide over days or weeks, talk it over with family, and want a place to keep their thinking.
- People filling in their mail ballot at the kitchen table, and anyone voting in person at a vote center who wants a cheat sheet they made themselves.

## Core principles

1. **Complete or clearly labeled.** If we can't show every candidate and every question for a place, we say so plainly. A partial ballot presented as complete is worse than no ballot.
2. **Private by design.** No accounts, no logins, no server-side storage of choices or notes. Your data never leaves your device unless you move it yourself.
3. **Nonpartisan.** We help people see and organize their ballot. We never try to persuade anyone how to vote.
4. **Honest about uncertainty.** A ZIP code can cross district lines. When something depends on your exact address, we show it and say so, instead of guessing.
5. **Simple.** Usable on a phone in a few minutes, by anyone, with no setup.

## What people can do

### 1. See their ballot
- **ZIP lookup (research mode).** Shows everything that could be on ballots in that ZIP. Items that depend on exact location are marked, for example "If you're in State House District 10." Clearly labeled as research and exploration, not an official ballot.
- **Address lookup (precise mode).** Narrows to the exact ballot for a location. See the privacy section for how this works without sending an address anywhere.
- **Guided narrowing.** For people who know their city or districts, simple pickers trim the list without entering an address.
- Items appear in official ballot order and grouped the way the printed ballot is: federal, state, legislature, judges, county, city, special districts, then measures.

### 2. Research each item
Every contest and question links out to good sources rather than summarizing opinions in-app:
- **Official sources first:** the Colorado Blue Book, GoVoteColorado, county clerk sample ballots and TABOR notices, full ballot text.
- **Nonpartisan explainers:** Ballotpedia, League of Women Voters (VOTE411), local nonprofit newsrooms.
- **Candidates in their own words:** campaign websites and official filings, for every candidate on the ballot, minor parties included.
- **Both sides of measures:** links to the organized support and opposition campaigns, always shown together.

### 3. Keep track of decisions
- Yes/No sliders for measures and retention, with a clear "undecided" middle.
- Checkboxes for candidates, with vote limits enforced ("vote for up to five") and ranking where the race uses ranked choice.
- **Notes on any item,** for questions, what a friend said, or the back and forth when you're unsure.
- Progress at a glance: how many items you've decided.

### 4. Take it with you
- **Write out my ballot:** an abbreviated list of decisions, with or without notes and undecided items, ready to copy, print or save.
- Formatted to match the order of the printed ballot, so it's quick to work through while filling in a mail ballot or at a vote center: short and easy to scan.
- Reminders of Colorado basics: ballots must be received (not postmarked) by 7 p.m. on Election Day, with links to drop box and vote center locations.

## Privacy and security

This is the most important part of the design. People's political choices are sensitive, and the safest data is data we never have.

### Commitments
- **No accounts and no login.** There is nothing to sign up for.
- **No server-side storage.** Choices and notes live only in the browser on the person's device.
- **Nothing leaves the device unless the person moves it.** They can export a file and open it on another computer. That's the only way data travels.
- **No tracking.** No analytics, no ad tech, no third-party scripts, no cookies, no fingerprinting.

### Proposed architecture
- **Static site.** The app is plain files served from a CDN. There is no application server and no database.
- **Ballot data as static, versioned files.** Ballot content is published per Colorado county as public data files, plus one statewide file. The browser downloads the whole county or state file and does all filtering locally, so the server never learns which districts or choices someone cares about. Server and CDN access logs are disabled or minimized.
- **Address lookup that stays local.** Sending an address to a geocoding service would break the privacy promise, so precise mode avoids it:
  - District boundaries ship inside the county data file.
  - The person either allows the browser's location (computed on-device against the boundaries) or taps their home on a map. The point-in-district check happens entirely in the browser.
  - Map tiles, if used, are self-hosted so no third party sees where someone is looking.
  - ZIP lookup and guided narrowing remain fully available for people who'd rather share nothing.
- **Local storage.** Choices and notes are kept in the browser (IndexedDB). A visible **"Clear everything"** button removes it all. A **private session** option keeps nothing after the tab closes, for library and shared computers.
- **Export and import.** "Save to file" writes a small file the person controls. "Open file" loads it on another device. An optional QR code, generated on the device, can move choices to a phone without any server in between.
- **Works offline.** After the first visit, the app and that county's data work with no connection, including at the polling place.
- **Locked-down page.** A strict content security policy that only allows the site's own files, self-hosted fonts, and integrity checks on every script.
- **Open source.** Code and data are public so anyone can verify these claims, with a plain-language privacy page that matches what the code actually does.

### Threats we design against
- **Shared or borrowed devices:** private session mode, clear-everything, nothing stored by default on public computers.
- **Tampered or wrong ballot data:** every item links to its official source and the date it was checked; data files are versioned with a public changelog.
- **Look-alike or phishing copies:** one canonical domain, published file hashes, and an open-source build others can verify.
- **Pressure to reveal choices:** saved choices are a private plan, not a record of a vote, and the app never claims otherwise.

### Lessons from Searchboard
*To fill in: how searchboard.dev handles login-free use, local storage, data export, and what to carry over or improve here.*

## Staying nonpartisan

The app helps people see and organize their ballot. It does not tell them what to think.

- **Official ballot order** for candidates and measures. No reordering by popularity or party.
- **Every candidate shown equally,** with the same fields and the same treatment, minor parties and write-in options included.
- **No recommendations, scores, or "matches."** No quizzes that steer people toward candidates.
- **Measure descriptions follow a neutral style guide** modeled on the Blue Book: what a yes vote does, what a no vote does, the fiscal effect, nothing about whether it's good.
- **Both sides together.** Wherever we link to arguments for a measure, the arguments against appear right beside them.
- **Endorsements are links, not features.** If we surface them at all, they're presented as sources to explore, with groups from across the spectrum.
- **AI-assisted text is reviewed by a person** before it appears, and labeled where it's used.
- **Corrections are public.** A visible way to report an error, and a changelog of fixes.

## Completeness and data

- **Ground truth is the official sample ballot.** Each county's compiled sample ballot, or per-precinct ballot styles, defines what "complete" means. Everything in the app is checked against it.
- **Coverage is shown honestly.** Each county is either "Verified complete" (with the source and date checked) or "Statewide items only." Never a silent gap.
- **Every item carries provenance:** a link to its official source and the date it was verified.
- **How the Colorado data comes together:**
  - **Statewide:** candidates and measures from the Secretary of State's certified ballot and the Blue Book. One source for all 64 counties.
  - **Districts:** congressional, legislative, CU Regent, State Board of Education and judicial district boundaries from public data.
  - **Local:** each county's compiled sample ballot, extracted with AI and verified by a person, covering county offices, cities and towns, school districts, and special districts like fire, water, metro and transit.
- **Order of work:** counties by population first. The ten largest counties hold most of the state's voters, so they come first, then the rest until all 64 are verified.
- **Timing:** ballots for the Nov. 3, 2026 general election went out Oct. 2, so this cycle is a pilot: verify as many counties as we can before Election Day, starting with Boulder and Larimer, which are done. The November 2027 coordinated election (school boards, municipal races, local tax questions) is the first full cycle with all 64 counties.

## What we won't do

- Require an account or collect personal information.
- Store anyone's choices or notes on a server.
- Sell, share, or analyze data. There is none to sell.
- Recommend candidates or positions, or rank options.
- Show a partial ballot as if it were complete.
- Run ads or third-party tracking.

## How we'll know it's working

- **Coverage:** how many of Colorado's 64 counties, and what share of its voters, are verified complete against official sample ballots.
- **Accuracy:** error reports per election and time to fix them.
- **Usefulness:** people finish their ballot and use the write-out. Since we collect no analytics, we learn this through voluntary feedback, user testing, and outreach partners rather than tracking.
- **Trust:** organizations across the political spectrum are comfortable linking to it.

## Open questions

- Who hosts and maintains it long term, and how is it funded without compromising neutrality?
- Until all 64 counties are verified, should licensed data (such as BallotReady) fill gaps, clearly labeled as unverified, or should those counties show statewide items only?
- How do we handle Colorado's June primaries, odd-year coordinated elections, and special elections on the same footing as November?
- Would the Secretary of State or county clerks share ballot data or precinct files directly, rather than us extracting it from PDFs?
- Which Colorado partners (county clerks, League of Women Voters of Colorado, local newsrooms like Boulder Reporting Lab and Colorado Sun, libraries) would help with verification and reach?
- After Colorado, which state next, and what do we need to learn from this cycle before deciding?
- What's the right review process for neutral measure descriptions, and who sits on it?
