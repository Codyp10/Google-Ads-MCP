# Google Ads MCP Server

A remote MCP (Model Context Protocol) server that wraps the Google Ads API. Connect it to Claude.ai as a custom connector to create and manage Google Ads campaigns through conversation.

## Features

- **Multi-account support** — manage campaigns across all accounts under your MCC
- **16 tools** covering the full campaign lifecycle:
  - Account management (list accounts, set active account)
  - Campaign creation (Search, Display, Performance Max)
  - Ad groups, keywords, negative keywords
  - Responsive Search Ads with headline/description pinning
  - Assets (sitelinks, callouts, call, structured snippets, images)
  - Bulk structure preview and push
- **Safe by default** — all campaigns created PAUSED unless explicitly told otherwise
- **Streamable HTTP transport** — compatible with Claude.ai custom MCP connectors

## Project Structure

```
├── main.py                     # Entry point
├── src/
│   ├── server.py               # MCP server definition (all 16 tools)
│   ├── tools/
│   │   ├── accounts.py         # list_accessible_accounts, set_active_account
│   │   ├── campaigns.py        # create_campaign
│   │   ├── ad_groups.py        # create_ad_group
│   │   ├── keywords.py         # add_keywords, add_negative_keywords
│   │   ├── ads.py              # create_rsa
│   │   ├── assets.py           # sitelinks, callouts, call, snippets, images
│   │   ├── pmax.py             # create_pmax_campaign, create_asset_group
│   │   └── structure.py        # preview_structure, push_structure
│   └── utils/
│       └── google_ads_client.py # Google Ads API client wrapper
├── scripts/
│   ├── get_refresh_token.py    # OAuth2 flow to generate refresh token
│   └── verify_connection.py    # Test API connection
├── google-ads.yaml             # Local credentials (gitignored)
├── Dockerfile                  # Container config
├── railway.toml                # Railway deployment config
├── render.yaml                 # Render deployment config
├── requirements.txt            # Python dependencies
└── .env.example                # Environment variable template
```

## Local Setup

### Prerequisites

- Python 3.10+ (3.12 recommended)
- A Google Ads developer token (Explorer Access or higher)
- OAuth2 credentials JSON from Google Cloud Console

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Generate OAuth2 refresh token

Place your OAuth2 credentials JSON in the project root, then run:

```bash
python scripts/get_refresh_token.py
```

This opens a browser for Google sign-in and saves the refresh token to `google-ads.yaml`.

### 3. Configure google-ads.yaml

Fill in your developer token and MCC customer ID:

```yaml
developer_token: "YOUR_DEVELOPER_TOKEN"
client_id: "your-client-id.apps.googleusercontent.com"
client_secret: "GOCSPX-..."
refresh_token: "1//0..."
login_customer_id: "1234567890"
use_proto_plus: true
```

### 4. Verify connection

```bash
python scripts/verify_connection.py
```

### 5. Run locally

```bash
# HTTP mode (for testing with Claude.ai)
python main.py

# Stdio mode (for local MCP clients)
python main.py --stdio
```

The server starts on `http://0.0.0.0:8000` with the MCP endpoint at `/mcp`.

## Deploy to Railway

1. Push your code to a GitHub repository (credentials are gitignored).

2. Create a new project on [Railway](https://railway.app) and connect your repo.

3. Add these environment variables in Railway's dashboard:

   | Variable | Value |
   |----------|-------|
   | `GOOGLE_ADS_DEVELOPER_TOKEN` | Your developer token |
   | `GOOGLE_ADS_CLIENT_ID` | Your OAuth2 client ID |
   | `GOOGLE_ADS_CLIENT_SECRET` | Your OAuth2 client secret |
   | `GOOGLE_ADS_REFRESH_TOKEN` | Your refresh token |
   | `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Your MCC customer ID (no dashes) |
   | `PORT` | `8000` |

4. Railway will auto-detect the Dockerfile and deploy. Your MCP endpoint will be:
   ```
   https://your-app.up.railway.app/mcp
   ```

## Deploy to Render

1. Push your code to a GitHub repository.

2. Create a new **Web Service** on [Render](https://render.com) and connect your repo.

3. Render will detect `render.yaml`. Add the same environment variables as above in the Render dashboard (marked `sync: false` in render.yaml for security).

4. Your MCP endpoint will be:
   ```
   https://your-app.onrender.com/mcp
   ```

## Connect to Claude.ai

1. Deploy the server to Railway or Render (see above).

2. In Claude.ai, go to **Settings > MCP Connectors > Add Connector**.

3. Enter your deployed MCP endpoint URL:
   ```
   https://your-app.up.railway.app/mcp
   ```

4. Claude will discover all 16 tools automatically.

5. Start a conversation:
   > "List my Google Ads accounts"
   > "Set the active account to We Paint Texas"
   > "Create a Search campaign called 'Spring Sale' with a $20/day budget targeting the US"

## Available Tools

| Tool | Description |
|------|-------------|
| `tool_list_accessible_accounts` | List all accounts under your MCC |
| `tool_set_active_account` | Set which account to target |
| `tool_create_campaign` | Create Search/Display/Shopping campaign |
| `tool_create_ad_group` | Create ad group linked to a campaign |
| `tool_add_keywords` | Add keywords to an ad group |
| `tool_add_negative_keywords` | Add negatives at campaign or ad group level |
| `tool_create_rsa` | Create Responsive Search Ad |
| `tool_add_sitelinks` | Add sitelink assets |
| `tool_add_callouts` | Add callout assets |
| `tool_add_call_asset` | Add phone number asset |
| `tool_add_structured_snippets` | Add structured snippet assets |
| `tool_add_image_asset` | Upload image from file or URL |
| `tool_create_pmax_campaign` | Create Performance Max campaign |
| `tool_create_asset_group` | Create PMax asset group with creatives |
| `tool_preview_structure` | Preview full campaign structure (dry run) |
| `tool_push_structure` | Push full campaign structure to Google Ads |

## Notes

- All campaigns are created **PAUSED** by default
- Every tool accepts an optional `customer_id` to target any account
- Budget values use **micros** (1 dollar = 1,000,000 micros)
- The `push_structure` tool creates entities in order: campaign -> ad groups -> keywords -> ads -> assets
- Explorer Access developer tokens can read and create but have daily limits
