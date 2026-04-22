# Resume Tailor

A local Mac web app that screens job descriptions with Claude AI and tailors your resume to them, exporting a PDF from your Pages template and logging each application to an Excel tracker.

---

## 1. Install dependencies

```bash
pip install flask anthropic python-dotenv openpyxl
```

---

## 2. Set up your API key

Copy `.env.example` to `.env` and paste your Anthropic API key:

```bash
cp .env.example .env
```

Open `.env` and replace `your_key_here` with your real key. It should look like:

```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 3. Set up your Pages template

This is the most important setup step. The app finds specific placeholder tokens in your Pages document and replaces them with your tailored resume content.

### What tokens to add and where

Open Pages and design your resume layout. In the places where content will be swapped in, type these tokens **exactly as shown** — same capitalization, same curly braces:

| Token | Where to place it |
|---|---|
| `{{skills}}` | Where your skills list goes (e.g. a text box or inline after "Skills:") |
| `{{courses}}` | Where your relevant courses list goes |
| `{{project1_name}}` | The name / heading of your first project slot |
| `{{project1_bullets}}` | The bullet point body of your first project slot |
| `{{project2_name}}` | Name of second project slot |
| `{{project2_bullets}}` | Bullets of second project slot |
| `{{project3_name}}` | Name of third project slot |
| `{{project3_bullets}}` | Bullets of third project slot |

**Important notes:**
- Type the tokens as plain text. Do not bold them, italicize them, or apply any special formatting — the AppleScript replacement works on raw text and will replace the whole styled run.
- Skills will be filled in as a bullet-separated list, e.g. `Python • React • PostgreSQL`.
- Courses will be filled in the same way.
- Project bullets will be filled as separate lines, each starting with `•`.
- Everything else on your resume (your name, contact info, education, summary) stays fixed in the template — you type that directly in Pages and it never changes.

### Save the template

Save the Pages file somewhere you won't accidentally move it, for example:

```
/Users/yourname/Documents/ResumeTemplate.pages
```

You'll use this path in the next step.

---

## 4. Update the config block in app.py

Open `app.py`. The very first section is the config block:

```python
PAGES_TEMPLATE_PATH = "/path/to/your/template.pages"
PDF_OUTPUT_FOLDER   = "/path/to/your/output/folder"
MASTER_RESUME_PATH  = "master_resume.json"
```

Replace each path:

- **`PAGES_TEMPLATE_PATH`** — the full path to the Pages template you just created, e.g.:
  `/Users/yourname/Documents/ResumeTemplate.pages`

- **`PDF_OUTPUT_FOLDER`** — already set to `/Users/shrav/Desktop/tailored_resume`. Each export creates a subfolder inside it named `CompanyName_April20`, with the PDF saved as `ShravanthiMurugesan_Resume.pdf` inside. The subfolder is created automatically.

- **`MASTER_RESUME_PATH`** — leave this as `"master_resume.json"` unless you move the file.

---

## 5. Fill in master_resume.json

Open `master_resume.json` and replace the placeholder content with your real information. The structure is:

- **skills** — each has a `name` and `tags`. Tags are one or more of: `"language"`, `"framework"`, `"tool"`, `"soft"`. Claude uses these to pick the most relevant subset per role.
- **courses** — each has a `name` and `relevance_tags`. Tags are free-form descriptors like `"backend"`, `"ml"`, `"cs-fundamentals"`. Claude uses these to pick the most relevant 3–5.
- **projects** — each has a `name`, `description`, `bullets` (a list of strings), and `tags`. Include all projects you'd ever want on a resume. Claude picks the 3 best per job. Write bullets exactly as you want them to appear in your resume.

The `name`, `email`, `phone`, `linkedin`, `github`, and `education` fields are **not used by the tailoring logic** — they're just for your reference. Your fixed personal info lives directly in the Pages template.

---

## 6. Run the app

```bash
python app.py
```

Then open your browser and go to:

```
http://localhost:5000
```

The app stays running until you stop it. To stop it, press **Ctrl+C** in the terminal.

---

## 7. Using the app

1. Fill in **Company**, **Role**, optional **Job URL**, and paste the **job description**.
2. Click **Screen this job** — Claude reads the JD and returns a fit score, any flags (no sponsorship, seniority mismatch, security clearance), and a recommendation. This takes a few seconds.
3. If you want to proceed, click **Tailor & Export Resume** — Claude picks the best skills, courses, and 3 projects from your master resume, scores the match, and gives recruiter feedback. The app then fills your Pages template and exports a PDF. This takes about 10–15 seconds.
4. The results show you the ATS and recruiter scores, matched and missing keywords, and confirms where the PDF was saved and that the tracker was updated.
5. Click **Start over** to clear the form for your next application.

---

## 8. Application tracker (applications.xlsx)

The tracker file is created automatically at `applications.xlsx` in the same folder as `app.py` the first time you tailor a resume. It has these columns:

```
Company | Position | Referral? | Date Applied | Current Status | URL | JD | Fit Score | ATS Score | Recruiter Score | PDF Path
```

- **Referral?** and manual status updates are left blank for you to fill in.
- **Current Status** starts as "Applied" and you update it manually as the process moves forward.
- The file is **never overwritten** — each run appends a new row.

---

## 9. Migrate existing data from Google Sheets

If you have existing application data in Google Sheets:

1. Open your Google Sheet.
2. Open `applications.xlsx` in Excel or Numbers.
3. Make sure your Sheet columns are in this order (add or reorder as needed):
   `Company | Position | Referral? | Date Applied | Current Status | URL | JD | Fit Score | ATS Score | Recruiter Score | PDF Path`
4. Select and copy all data rows (not the header row) from Google Sheets.
5. Click the first empty row in `applications.xlsx` and paste.
6. Save.

If you don't have some columns (like Fit Score or ATS Score for old entries), just leave those cells blank.

---

## Troubleshooting

**"Could not load master_resume.json"** — Check that `MASTER_RESUME_PATH` in the config block points to the right file, and that the JSON is valid (no missing commas, no trailing commas).

**"AppleScript failed"** — This usually means one of these things:
- `PAGES_TEMPLATE_PATH` is wrong — double-check the full path.
- Pages needs Automation permission — go to System Settings → Privacy & Security → Automation, and make sure Terminal (or your Python runner) is allowed to control Pages.
- The token text in your Pages document has invisible formatting applied — try deleting and retyping the token in plain text.

**"Tailoring API call failed"** — Check that your `.env` file exists, contains the right key, and that your Anthropic account has API access.

**PDF output folder not found** — Make sure the folder at `PDF_OUTPUT_FOLDER` actually exists. The app doesn't create it automatically.
