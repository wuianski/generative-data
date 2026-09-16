# IG scrape → BLIP captions

Two-step pipeline, run manually:

1. **`scraper.py`** — logs into Instagram (persistent Firefox profile), scrolls the
   home feed, and downloads 100 unique post images into `data/YYYY-MM-DD/images/`.
   Duplicates are skipped via MD5 hashes (`seen_hashes.json`), and small images
   (avatars/icons, < 300 px) are filtered out.
2. **`caption.py`** — captions each image with BLIP
   (`Salesforce/blip-image-captioning-base`; uses CUDA on Windows/Linux, MPS on
   Apple Silicon, otherwise CPU) and writes `data/YYYY-MM-DD/captions.json`.

Each day's batch is self-contained:

```
data/
  2026-09-14/
    images/001.jpg … 100.jpg
    captions.json
```

Credentials live in `.env` (`INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD`),
see `.env.example`. [Firefox](https://www.mozilla.org/firefox/) must be
installed; Selenium downloads the matching geckodriver automatically.

## Setup — Windows

Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) and Firefox,
then in **Anaconda Prompt** (or PowerShell after `conda init`):

```bat
:: scraping env
conda create -n scraper python=3.11 -y
conda activate scraper
pip install -r requirements.txt

:: captioning env
conda create -n img2txt python=3.11 -y
conda activate img2txt
pip install -r requirements-caption.txt
:: with an NVIDIA GPU, install the CUDA build of torch instead:
::   pip install torch --index-url https://download.pytorch.org/whl/cu124
```

Copy `.env.example` to `.env` and fill in your Instagram credentials.

## Setup — macOS

Same as above (envs already exist on the original machine at
`~/miniforge3/envs/scraper` and `~/miniforge3/envs/img2txt`).

## Run

```bat
:: Windows
conda activate scraper
python scraper.py --limit 100
conda activate img2txt
python caption.py
```

```bash
# macOS
~/miniforge3/envs/scraper/bin/python scraper.py --limit 100
~/miniforge3/envs/img2txt/bin/python caption.py
```

Both scripts accept `--date YYYY-MM-DD` to target a specific day folder
(default: today). `caption.py` also accepts `--images-dir` to caption any
arbitrary folder, `--limit N` to caption only the first N images, and
`--device cuda|mps|cpu`.

### First run

The first run opens a visible Firefox window and logs in with the `.env`
credentials. If Instagram shows a security check, complete it by hand in that
window — the session is stored in `firefox_profile/` and reused afterwards,
so subsequent runs won't need to log in again. The first `caption.py` run
downloads the BLIP model (~1 GB) from Hugging Face.

If you scrape before midnight but caption after, pass the scrape date
explicitly: `caption.py --date YYYY-MM-DD`.

## Daily scheduling (Windows)

`run_daily.bat` runs both steps and logs to `logs\daily.log`. It assumes
Miniconda at `%USERPROFILE%\miniconda3` — edit the two paths at the top if
yours differs. Register it to run every day at 06:00:

```bat
schtasks /Create /TN "GenerativeData Daily" ^
  /TR "\"C:\path\to\generative-data\run_daily.bat\"" ^
  /SC DAILY /ST 06:00
```

Notes:

- Keep the default "run only when user is logged on" — the scraper opens a
  visible Firefox window and needs an interactive session.
- To let the task wake the laptop, open Task Scheduler → the task →
  Conditions → check "Wake the computer to run this task", and make sure the
  laptop is plugged in (or allow wake on battery in Power Options).
- Test immediately with `schtasks /Run /TN "GenerativeData Daily"`,
  check `logs\daily.log` for progress.
- Remove with `schtasks /Delete /TN "GenerativeData Daily" /F`.

## Output format

`data/YYYY-MM-DD/captions.json`:

```json
{
  "date": "2026-09-14",
  "generated_at": "2026-09-14T09:12:33",
  "model": "Salesforce/blip-image-captioning-base",
  "images_dir": "data/2026-09-14/images",
  "count": 100,
  "items": [
    { "file": "001.jpg", "caption": "a cat laying on a couch" }
  ]
}
```

Note: scraped content (`data/`) is git-ignored — it contains Instagram images
and should not be published.
