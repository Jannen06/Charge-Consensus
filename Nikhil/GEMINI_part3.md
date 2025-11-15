You will output exactly one file.

===== dashboard.html =====

Create a single static HTML file `dashboard.html` that polls `/dashboard-data` every 2 seconds and renders a clean table.

Requirements:
- Minimal CSS and vanilla JavaScript only (no frameworks).
- The page must:
  - Poll GET /dashboard-data every 2000 ms using fetch().
  - Render columns: User DID, Text, SoC, Intent, Priority (colored: high=red, medium=orange, low=green), Recommendation, Timestamp.
  - Show a timestamp of last update at top.
  - When there are no items, show "No requests".
  - Provide a small debug area that prints the last raw JSON fetched (collapsible).
  - Use a small inline function to map priority to numeric order for sorting client-side (highest first).
- Security note:
  - The frontend must never include secrets; it will be served by the orchestrator.
- The file should be ready to drop into the project root and be served by FastAPI's FileResponse.

No extra text outside the file marker. The content must be a complete HTML file.
