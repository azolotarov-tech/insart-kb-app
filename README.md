# INSART Knowledge Base App

A documentation portal that fetches and renders content live from a GitHub repository via the GitHub API.

## Tech Stack

- **Backend**: Python / Flask 3.1.3
- **Templating**: Jinja2
- **Markdown rendering**: `markdown` + `pymdownx` extensions
- **Frontend**: Vanilla JS + custom CSS (no framework)
- **Content source**: GitHub API (`vzherebetskyiInsart/insart-knowledge-base`)
- **Deployment**: Vercel

## Project Structure

```
insart-kb-app/
├── app.py              # Flask app — routing, GitHub API fetching, markdown rendering
├── requirements.txt    # Python dependencies
├── vercel.json         # Vercel deployment config
├── static/
│   ├── logo.png
│   └── logo.svg
└── templates/
    ├── base.html       # Shared layout, nav, search, theme toggle
    ├── home.html       # Homepage
    ├── section.html    # Section index page
    └── page.html       # Individual document page
```

## Running Locally

**Prerequisites:** Python 3.x and pip.

```bash
# Install dependencies
pip install -r requirements.txt

# Start the development server
python app.py
```

The app starts at [http://localhost:8080](http://localhost:8080) with hot-reload enabled.

## Environment Variables

| Variable       | Required | Description                                                                                                                                           |
| -------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GITHUB_TOKEN` | Optional | GitHub personal access token. Raises the API rate limit from 60 to 5,000 requests/hour. Recommended for local development and required in production. |

Set it in your shell or a `.env` file before starting the app:

```bash
export GITHUB_TOKEN=your_personal_access_token
```

## Notes

- Content is fetched from GitHub on each request and cached for 5 minutes (300 s TTL).
- A git submodule at `./repo` points to the content repository but is not needed — the app uses the API, not local files.

# AI Search

## Indexing

All logic necessary for documents fetching and indexing into the vector db is located in the index.py file. You need to run it only once in order to fetch all docs from the github repo and put them into the database. This is also useful in case of migrations i.e. if you decide to migrate everything to a different database.

## TODO:

-- confidence levels
-- change format of the answer
-- list of subfolders and add concurrent uploading to github and voyage
-- show note that something is draft if draft
