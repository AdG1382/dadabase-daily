# Dadabase Daily

One dad joke a day, fully automated: a website, an Instagram carousel every morning, and a
YouTube Short plus Instagram Reel every evening. Everything comes from `data/jokes.csv`.

## How it runs

| When (IST) | What | Workflow |
|---|---|---|
| 08:47 daily | Instagram carousel (setup slide, punchline slide) | `post.yml` |
| 18:53 daily | YouTube Short + Instagram Reel (voiceover + ba-dum-tss) | `post.yml` |
| Mondays | Renews the Instagram token | `refresh-token.yml` |
| On every change to jokes or code | Rebuilds and redeploys the website | `site.yml` |

Each run picks the next joke (`dadabase/queue.py`): festival and season jokes post only inside
their window (`data/seasons.json`, one a day), India and Global jokes alternate, and nothing
repeats until every joke has posted once. Posting history is saved in `data/state.json`.

A platform that isn't set up yet is skipped, so the pipeline is safe to run at any stage.
GitHub emails you when a run fails.

## Setup checklist

Add these under **Settings → Secrets and variables → Actions**.

**Secrets**

| Name | Where it comes from |
|---|---|
| `IG_ACCESS_TOKEN` | Meta app → Instagram API → API setup with Instagram login → Generate token |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET` | Google Cloud → APIs & Services → Credentials → OAuth client (Desktop app) |
| `YT_REFRESH_TOKEN` | Run `python scripts/get_youtube_token.py CLIENT_ID CLIENT_SECRET` on your computer |
| `GH_PAT` | GitHub → Settings → Developer settings → Fine-grained token, this repo only, permission "Secrets: Read and write" |

**Variables**

| Name | Value |
|---|---|
| `SITE_URL` | Leave unset to use `https://adg1382.github.io/dadabase-daily`; set to `https://dadabase.adityagagare.in` once the custom domain works |
| `YT_PRIVACY` | `public` (uploads stay private anyway until Google approves the API audit) |
| `SHOP_URL` | Leave empty until a merch store exists |

## Website hosting (GitHub Pages)

Settings → Pages → Source: **GitHub Actions**. Each post run builds the site and publishes it, so
Instagram can fetch that day's images and video from the site.

Custom domain: in Hostinger DNS add a `CNAME` record, name `dadabase`, target `adg1382.github.io`.
Then Settings → Pages → Custom domain: `dadabase.adityagagare.in`, tick Enforce HTTPS, and set the
`SITE_URL` variable to `https://dadabase.adityagagare.in`.

## Everyday commands

```bash
pip install -r requirements.txt
python -m dadabase queue --count 14          # what posts next
python -m dadabase preview --id DJ0001 --video   # render one joke locally into build/preview
python -m dadabase build-site                # build the website into site/
python -m dadabase avatar                    # profile picture for Instagram/YouTube
```

To add jokes, append rows to `data/jokes.csv` with the next `DJ####` id. To drop a joke,
type `cut` in its `status` column.

Fonts: Inter (SIL Open Font License, see `assets/fonts/LICENSE-Inter.txt`). The rimshot sound
is synthesised in code, so there are no audio licences to worry about.
