# 01_LOGIC.md

# Review System — Application Logic Specification

## 1. Project Objective

Build a local terminal-based application to help monitor, fetch, store, display, and analyze public review data related to selected Hermina hospital locations.

The application will run locally using:

* Python
* PostgreSQL local database
* Interactive terminal interface
* Review data fetching module
* Gemini API analysis module

The application should not require users to type command-line arguments.
The user only runs:

```bash
python main.py
```

After running the command, the application must open an interactive terminal menu.

---

## 2. Product Name

Use this application name:

```text
Review System
```

Alternative internal short name:

```text
Hermina Review Monitor
```

---

## 3. Main Objective

The system should allow users to:

1. Manage Hermina hospital locations.
2. Fetch or sync review data for selected locations.
3. Store review data into PostgreSQL.
4. Avoid duplicated review data.
5. Display review data from the database.
6. Analyze review data using Gemini API.
7. Store AI analysis results.
8. Show review summaries per location.
9. Export review and analysis data.

---

## 4. MVP Scope

The MVP is a local terminal application.

Included in MVP:

* Interactive terminal menu.
* Local PostgreSQL database.
* Location management.
* Review fetching.
* Review storage.
* Deduplication logic.
* Gemini-based analysis.
* Review display.
* Summary display.
* Export to CSV or JSON.
* Fetch logs.
* Basic error handling.

Not included in MVP:

* Web dashboard.
* Authentication.
* User role management.
* Background worker.
* Real-time scheduler.
* WhatsApp/email alert.
* Multi-tenant support.
* Production deployment.

---

## 5. Application Startup Flow

When the user runs:

```bash
python main.py
```

The program must show:

```text
========================================
     Review System
========================================
Fetch, monitor, and analyze Hermina location reviews.
========================================

Main Menu

1. Manage Hermina Locations
2. Fetch / Sync Reviews
3. View Review Data
4. Analyze Reviews with Gemini
5. View Analysis Summary
6. Export Data
7. View Fetch Logs
8. System Settings
0. Exit

Select menu:
```

The application must keep running until the user selects `0. Exit`.

After every completed action, the program should return to the previous menu or main menu.

---

## 6. Menu Structure

### 6.1 Main Menu

```text
Main Menu

1. Manage Hermina Locations
2. Fetch / Sync Reviews
3. View Review Data
4. Analyze Reviews with Gemini
5. View Analysis Summary
6. Export Data
7. View Fetch Logs
8. System Settings
0. Exit
```

---

## 7. Location Management Logic

### 7.1 Location Menu

```text
Manage Hermina Locations

1. Add New Location
2. View All Locations
3. View Active Locations
4. Update Location
5. Activate / Deactivate Location
6. Delete Location
0. Back to Main Menu

Select menu:
```

---

### 7.2 Add New Location

The system should ask the user to input:

* Hospital name
* Branch name
* City
* Address
* Latitude
* Longitude
* Review source
* External place ID
* Active status

Default values:

```text
hospital_name = Hermina
source = google_places
is_active = true
```

Example input flow:

```text
Hospital Name [default: Hermina]:
Branch Name: Hermina Depok
City: Depok
Address: Jl. Siliwangi No. 50, Depok
Latitude:
Longitude:
Source [default: google_places]:
External Place ID:
Is Active? [Y/n]:
```

Validation:

* Branch name is required.
* External place ID is required.
* Source is required.
* Duplicate external place ID should not be allowed.
* If latitude or longitude is empty, allow null.

---

### 7.3 View Locations

Display locations in table format.

Example:

```text
ID | Hospital | Branch         | City   | Source        | Active
---------------------------------------------------------------
1  | Hermina  | Hermina Depok  | Depok  | google_places | Yes
2  | Hermina  | Hermina Bogor  | Bogor  | google_places | Yes
3  | Hermina  | Hermina Bekasi | Bekasi | google_places | No
```

---

### 7.4 Update Location

The system should:

1. Show all locations.
2. Ask user to select location ID.
3. Show current location data.
4. Ask which field to update.
5. Save the updated data.

Editable fields:

* hospital_name
* branch_name
* city
* address
* latitude
* longitude
* source
* external_place_id
* is_active

---

### 7.5 Activate / Deactivate Location

The system should:

1. Show all locations.
2. Ask user to select location ID.
3. Toggle active status.
4. Confirm success message.

Example:

```text
Location Hermina Depok has been deactivated.
```

---

## 8. Fetch / Sync Review Logic

### 8.1 Fetch Menu

```text
Fetch / Sync Reviews

1. Fetch Reviews for One Location
2. Fetch Reviews for All Active Locations
3. Dry Run Fetch for One Location
4. View Last Fetch Result
0. Back to Main Menu

Select menu:
```

---

### 8.2 Fetch Reviews for One Location

Flow:

1. Show active locations.
2. Ask user to select location ID.
3. Confirm selected location.
4. Start fetch process.
5. Normalize fetched review data.
6. Generate review hash.
7. Check duplicate data.
8. Insert only new review data.
9. Save fetch log.
10. Show fetch result.

Example output:

```text
Fetching reviews for Hermina Depok...

Source          : google_places
Location        : Hermina Depok
Total fetched   : 20
Inserted        : 5
Duplicate       : 15
Failed          : 0
Status          : Success

Press Enter to continue...
```

---

### 8.3 Fetch Reviews for All Active Locations

Flow:

1. Get all active locations.
2. Loop through each active location.
3. Run fetch process per location.
4. Save fetch log per location.
5. Show final summary.

Example output:

```text
Sync completed.

Total locations processed : 5
Success                   : 5
Failed                    : 0
Total reviews fetched      : 100
Total inserted             : 22
Total duplicate            : 78
```

---

### 8.4 Dry Run Fetch

Dry run fetch should:

* Fetch data from source.
* Normalize response.
* Show sample data.
* Not insert anything to database.
* Not create permanent review records.
* May still create a fetch log with status `dry_run`.

Example output:

```text
Dry Run Result

Location      : Hermina Depok
Source        : google_places
Total fetched : 20

Sample Reviews:
1. Rating 5 - Pelayanan baik dan dokter ramah.
2. Rating 3 - Antrean cukup lama.
3. Rating 1 - Admin kurang responsif.

No data was inserted.
```

---

## 9. Review Data Logic

### 9.1 Review Data Menu

```text
View Review Data

1. View All Reviews
2. View Reviews by Location
3. View Reviews by Rating
4. View Reviews by Sentiment
5. Search Review Text
6. View Latest Reviews
0. Back to Main Menu

Select menu:
```

---

### 9.2 View All Reviews

Display paginated review data.

Default limit:

```text
20 reviews per page
```

Fields to show:

* Review ID
* Location
* Rating
* Reviewer name
* Review text preview
* Review time
* Analysis status

Example:

```text
ID | Location       | Rating | Reviewer | Review Preview              | Time       | Analyzed
--------------------------------------------------------------------------------------
1  | Hermina Depok  | 5      | Andi     | Pelayanan sangat baik...    | 2026-06-18 | Yes
2  | Hermina Bogor  | 2      | Budi     | Antrean terlalu lama...     | 2026-06-18 | No
```

---

### 9.3 View Reviews by Location

Flow:

1. Show locations.
2. Ask user to select location ID.
3. Display reviews for selected location.
4. Allow filter by rating or date range if needed.

---

### 9.4 View Reviews by Rating

Flow:

1. Ask user to input rating from 1 to 5.
2. Display matching reviews.

Validation:

* Rating must be numeric.
* Rating must be between 1 and 5.

---

### 9.5 Search Review Text

Flow:

1. Ask user to input search keyword.
2. Search review text using case-insensitive matching.
3. Display matching reviews.

Example:

```text
Search keyword: antrean

Found 7 reviews containing "antrean".
```

---

## 10. Gemini Analysis Logic

### 10.1 Analysis Menu

```text
Analyze Reviews with Gemini

1. Analyze All Pending Reviews
2. Analyze Reviews by Location
3. Analyze Reviews by Rating
4. Re-run Analysis for Selected Review
5. Re-run Analysis by Location
0. Back to Main Menu

Select menu:
```

---

### 10.2 Analyze All Pending Reviews

Pending reviews are reviews that do not have records in `review_analysis`.

Flow:

1. Get all reviews without analysis.
2. Process reviews in batch.
3. Send review text and metadata to Gemini API.
4. Parse Gemini response.
5. Store analysis result.
6. Show summary.

Batch size default:

```text
20 reviews per batch
```

Example output:

```text
Analysis completed.

Total pending reviews : 45
Successfully analyzed : 43
Failed                : 2

Sentiment Result:
Positive : 21
Neutral  : 7
Negative : 13
Mixed    : 2
```

---

### 10.3 Analyze Reviews by Location

Flow:

1. Show locations.
2. Ask user to select location ID.
3. Get reviews for selected location that have not been analyzed.
4. Process analysis.
5. Store results.
6. Show summary.

---

### 10.4 Analyze Reviews by Rating

Flow:

1. Ask user to input rating.
2. Get reviews with selected rating that have not been analyzed.
3. Process analysis.
4. Store results.

Recommended use:

* Analyze rating 1 and 2 first to identify urgent service issues.

---

### 10.5 Re-run Analysis for Selected Review

Flow:

1. Ask user to input review ID.
2. Show review detail.
3. Ask confirmation to re-run analysis.
4. Send review to Gemini API again.
5. Save new analysis result.

Important:

* Do not delete old analysis result.
* Store new analysis result as a new row.
* Use `prompt_version` to identify the prompt used.

---

## 11. AI Analysis Output Specification

Gemini must return structured JSON.

Expected output:

```json
{
  "sentiment": "negative",
  "sentiment_score": 0.82,
  "issue_category": "waiting_time",
  "urgency": "medium",
  "summary": "Pasien mengeluhkan waktu tunggu yang lama.",
  "recommended_action": "Evaluasi alur antrean dan kapasitas petugas pada jam ramai.",
  "keywords": ["antrean", "lama", "pendaftaran"],
  "is_potential_viral": false,
  "is_patient_safety_issue": false
}
```

---

## 12. Sentiment Classification

Allowed sentiment values:

```text
positive
neutral
negative
mixed
unknown
```

Rules:

* `positive`: review contains praise, satisfaction, recommendation.
* `neutral`: review is factual or unclear.
* `negative`: review contains complaint or dissatisfaction.
* `mixed`: review contains both praise and complaint.
* `unknown`: review cannot be classified.

---

## 13. Issue Category Classification

Allowed issue categories:

```text
doctor_service
nurse_service
administration
waiting_time
cleanliness
facility
parking
billing
pharmacy
emergency_room
inpatient
customer_service
booking_system
staff_communication
security
food
general_praise
other
```

Category explanation:

| Category            | Meaning                                        |
| ------------------- | ---------------------------------------------- |
| doctor_service      | Review about doctors                           |
| nurse_service       | Review about nurses                            |
| administration      | Registration, front office, admission          |
| waiting_time        | Queue, waiting time, slow service              |
| cleanliness         | Cleanliness of room, toilet, public area       |
| facility            | Building, lift, AC, waiting room, equipment    |
| parking             | Parking space, parking flow, parking fee       |
| billing             | Payment, invoice, insurance, BPJS, price       |
| pharmacy            | Medicine, prescription, pharmacy queue         |
| emergency_room      | IGD / emergency service                        |
| inpatient           | Rawat inap experience                          |
| customer_service    | CS, call center, WA, information desk          |
| booking_system      | App, online booking, appointment system        |
| staff_communication | Staff attitude, clarity, empathy               |
| security            | Security staff or entrance flow                |
| food                | Patient food, canteen, meals                   |
| general_praise      | General positive review without specific issue |
| other               | Does not match any category                    |

---

## 14. Urgency Classification

Allowed urgency values:

```text
low
medium
high
critical
unknown
```

Rules:

| Urgency  | Meaning                                                        |
| -------- | -------------------------------------------------------------- |
| low      | Minor comment, praise, or general feedback                     |
| medium   | Operational issue that needs follow-up                         |
| high     | Serious complaint, repeated issue, reputational risk           |
| critical | Patient safety, legal risk, viral risk, severe service failure |
| unknown  | Cannot be determined                                           |

---

## 15. Analysis Summary Logic

### 15.1 Summary Menu

```text
View Analysis Summary

1. Summary for All Locations
2. Summary by Location
3. Negative Review Summary
4. Critical Issue Summary
5. Top Issue Categories
6. Sentiment Distribution
0. Back to Main Menu

Select menu:
```

---

### 15.2 Summary for All Locations

Show:

* Total locations
* Total reviews
* Total analyzed reviews
* Total pending analysis
* Sentiment distribution
* Top issue categories
* Critical issue count
* Latest fetch time

Example:

```text
Overall Review Summary

Total Locations        : 8
Total Reviews          : 1,240
Analyzed Reviews       : 1,100
Pending Analysis       : 140

Sentiment:
Positive               : 620
Neutral                : 180
Negative               : 250
Mixed                  : 50

Top Issues:
1. Waiting Time        : 90
2. Administration      : 70
3. Parking             : 45
4. Pharmacy            : 40
5. Staff Communication : 32

Critical Issues        : 3
Latest Fetch           : 2026-06-19 10:30
```

---

### 15.3 Summary by Location

Show:

* Location name
* Total reviews
* Average rating
* Sentiment distribution
* Top issue categories
* Negative review examples
* Critical review examples
* Recommended management focus

Example:

```text
Location Summary: Hermina Depok

Total Reviews     : 250
Average Rating    : 4.2
Negative Reviews  : 35
Critical Issues   : 1

Top Issues:
1. Waiting Time
2. Administration
3. Pharmacy

Management Focus:
- Improve queue management during peak hours.
- Review admission desk response time.
- Monitor pharmacy waiting process.
```

---

### 15.4 Critical Issue Summary

Show only reviews where:

```text
urgency = high OR urgency = critical
```

Fields:

* Location
* Rating
* Review text
* Issue category
* Urgency
* Recommended action

---

## 16. Export Logic

### 16.1 Export Menu

```text
Export Data

1. Export All Reviews to CSV
2. Export Reviews by Location to CSV
3. Export Analysis Summary to CSV
4. Export Raw Reviews to JSON
0. Back to Main Menu

Select menu:
```

---

### 16.2 Export Rules

Export folder:

```text
exports/
```

Filename format:

```text
reviews_all_YYYYMMDD_HHMMSS.csv
reviews_location_{location_id}_YYYYMMDD_HHMMSS.csv
analysis_summary_YYYYMMDD_HHMMSS.csv
raw_reviews_YYYYMMDD_HHMMSS.json
```

After export, show:

```text
Export completed.
File saved to: exports/reviews_all_20260619_103000.csv
```

---

## 17. Fetch Log Logic

### 17.1 Fetch Log Menu

```text
View Fetch Logs

1. View Latest Fetch Logs
2. View Fetch Logs by Location
3. View Failed Fetch Logs
0. Back to Main Menu

Select menu:
```

---

### 17.2 Fetch Log Display

Fields:

* Log ID
* Location
* Source
* Status
* Total fetched
* Total inserted
* Total duplicate
* Started at
* Finished at
* Error message

Example:

```text
ID | Location       | Status  | Fetched | Inserted | Duplicate | Started At
--------------------------------------------------------------------------------
1  | Hermina Depok  | success | 20      | 5        | 15        | 2026-06-19 10:00
2  | Hermina Bogor  | failed  | 0       | 0        | 0         | 2026-06-19 10:05
```

---

## 18. System Settings Logic

### 18.1 Settings Menu

```text
System Settings

1. Check Database Connection
2. Check Gemini API Key
3. Check Review Source API Key
4. Show App Configuration
0. Back to Main Menu

Select menu:
```

---

### 18.2 Check Database Connection

The system should attempt to connect to PostgreSQL.

Output:

```text
Database connection: OK
```

or

```text
Database connection: FAILED
Error: <error_message>
```

---

### 18.3 Check Gemini API Key

The system should validate whether Gemini API key exists in environment variable.

Do not print the full API key.

Output:

```text
Gemini API Key: FOUND
Value: ************abcd
```

or

```text
Gemini API Key: NOT FOUND
```

---

## 19. Deduplication Logic

Every fetched review must generate a `review_hash`.

Hash input:

```text
source
external_place_id
external_review_id
reviewer_name
rating
review_text
review_time
```

If `external_review_id` does not exist, still generate hash using available fields.

Pseudo-code:

```python
def generate_review_hash(review):
    hash_input = "|".join([
        str(review.get("source", "")),
        str(review.get("external_place_id", "")),
        str(review.get("external_review_id", "")),
        str(review.get("reviewer_name", "")),
        str(review.get("rating", "")),
        str(review.get("review_text", "")),
        str(review.get("review_time", ""))
    ])

    return sha256(hash_input.encode("utf-8")).hexdigest()
```

Rules:

* If hash already exists in database, skip insert.
* Count skipped data as duplicate.
* If review text changes but reviewer and time are same, it may create a new hash.
* Store original raw payload for audit.

---

## 20. Error Handling Logic

The application must handle common errors gracefully.

### 20.1 Invalid Menu Input

If user enters invalid menu number:

```text
Invalid menu selection. Please try again.
```

Return to the same menu.

---

### 20.2 Empty Database

If no location exists:

```text
No Hermina locations found.
Please add a location first.
```

---

### 20.3 No Review Found

If selected location has no review:

```text
No reviews found for this location.
Please run fetch first.
```

---

### 20.4 API Error

If external API fails:

```text
Fetch failed.
Source: google_places
Error: <error_message>
```

Save error into fetch log.

---

### 20.5 Gemini Error

If Gemini API fails:

```text
Analysis failed for review ID: <review_id>
Error: <error_message>
```

Continue processing next review.

---

### 20.6 Database Error

If database operation fails:

```text
Database error occurred.
Error: <error_message>
```

Rollback transaction.

---

## 21. Recommended Internal Service Design

The terminal UI should not contain business logic.

Use this separation:

```text
terminal menu
    |
    calls service
    |
    service calls database / integration
    |
    returns result
    |
terminal menu displays result
```

Recommended services:

```text
LocationService
FetchService
ReviewService
AnalysisService
SummaryService
ExportService
FetchLogService
SettingsService
```

---

## 22. Service Responsibilities

### 22.1 LocationService

Responsible for:

* Add location
* Get all locations
* Get active locations
* Update location
* Activate/deactivate location
* Delete location

---

### 22.2 FetchService

Responsible for:

* Fetch review for one location
* Fetch review for all active locations
* Dry run fetch
* Normalize review payload
* Generate fetch result
* Create fetch log

---

### 22.3 ReviewService

Responsible for:

* Insert new review
* Check duplicate review
* Get reviews
* Search review text
* Filter reviews by location
* Filter reviews by rating
* Get latest reviews

---

### 22.4 AnalysisService

Responsible for:

* Get pending reviews
* Analyze review with Gemini
* Store analysis result
* Re-run analysis
* Track failed analysis

---

### 22.5 SummaryService

Responsible for:

* Calculate sentiment distribution
* Calculate top issue categories
* Calculate critical issues
* Generate location summary
* Generate overall summary

---

### 22.6 ExportService

Responsible for:

* Export reviews to CSV
* Export reviews by location
* Export summary to CSV
* Export raw review JSON

---

### 22.7 FetchLogService

Responsible for:

* Create fetch log
* Update fetch log
* Get latest fetch logs
* Get failed fetch logs
* Get logs by location

---

### 22.8 SettingsService

Responsible for:

* Check database connection
* Check environment variables
* Check API key presence
* Show app configuration

---

## 23. Suggested Program Loop

Pseudo-code:

```python
def main():
    while True:
        show_main_menu()
        choice = input("Select menu: ")

        if choice == "1":
            location_menu()
        elif choice == "2":
            fetch_menu()
        elif choice == "3":
            review_menu()
        elif choice == "4":
            analysis_menu()
        elif choice == "5":
            summary_menu()
        elif choice == "6":
            export_menu()
        elif choice == "7":
            fetch_log_menu()
        elif choice == "8":
            settings_menu()
        elif choice == "0":
            print("Exiting Review System. Goodbye.")
            break
        else:
            print("Invalid menu selection. Please try again.")
```

---

## 24. User Experience Rules

The terminal app should be simple and readable.

Rules:

* Always show clear menu title.
* Always show confirmation after action.
* Always show error message if action fails.
* Always allow user to go back to previous menu.
* Do not crash on invalid input.
* Do not expose full API key.
* Do not show long JSON unless user selects raw view.
* Use simple table format for lists.
* Use pagination for long data.
* Use clear status messages.

---

## 25. Acceptance Criteria

Codex should generate an application logic that satisfies:

1. Running `python main.py` opens interactive terminal interface.
2. Main menu appears correctly.
3. User can navigate between menus.
4. User can add, view, update, activate/deactivate locations.
5. User can trigger fetch for one location.
6. User can trigger fetch for all active locations.
7. User can run dry fetch without inserting data.
8. System stores fetched reviews into PostgreSQL.
9. System prevents duplicate review insertion.
10. User can view reviews from terminal.
11. User can analyze pending reviews with Gemini API.
12. User can view analysis summary.
13. User can export data.
14. User can view fetch logs.
15. System handles invalid input without crashing.
16. Business logic is separated from terminal UI.
17. Raw review payload is stored for audit.
18. AI analysis result is stored separately from raw review data.
19. Old analysis result is not deleted during re-run.
20. Application can be extended later into web dashboard.

---

## 26. Development Priority

Build in this order:

### Phase 1 — Terminal Skeleton

* `main.py`
* Main menu
* Submenus
* Navigation
* Exit logic

### Phase 2 — Database Models

* Locations
* Reviews
* Review analysis
* Fetch logs

### Phase 3 — Location Management

* Add location
* View locations
* Update location
* Activate/deactivate location

### Phase 4 — Fetching Logic

* Fetch one location
* Fetch all active locations
* Normalize review
* Deduplicate review
* Save fetch log

### Phase 5 — Review Display

* View all reviews
* View by location
* View by rating
* Search text
* Latest reviews

### Phase 6 — Gemini Analysis

* Analyze pending reviews
* Analyze by location
* Analyze by rating
* Store structured result

### Phase 7 — Summary and Export

* Overall summary
* Location summary
* Critical issue summary
* Export CSV/JSON

---

## 27. Important Notes for Codex

* Do not build a web app in this phase.
* Do not require command-line arguments.
* Do not hardcode API keys.
* Use `.env` for configuration.
* Keep the terminal UI separate from service logic.
* Use PostgreSQL as the primary database.
* Store raw review data and analysis data separately.
* Make the code modular and easy to extend.
* External review fetching implementation can initially use mock data if real API is not ready.
* Gemini analysis implementation can initially be wrapped in a client class so it can be mocked during development.
