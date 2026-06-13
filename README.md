# uShield OTA Filter CDN

This repository serves as the content delivery network (CDN) and automated backend for the [uShield Safari Extension](https://github.com/uShieldApp/uShield). 

It utilizes GitHub Actions to dynamically generate and host delta JSON rules daily, overcoming Apple's 30,000 rule limit for Safari Web Extensions.

## ⚙️ Architecture

1.  **Baseline Static Rules**: The `rules/` directory contains versioned folders (e.g., `v1.0.0/baseline/`). These folders hold the "static" JSON ad-blocking rules that are bundled natively within the uShield iOS App.
2.  **Daily GitHub Actions**: Every day, a GitHub Actions workflow (`.github/workflows/update-filters.yml`) runs the `generate_delta.py` script.
3.  **Delta Generation**: The script downloads the absolute latest ad-blocking lists from EasyList and Fanboy. It compares these fresh lists against our static `baseline`.
4.  **CDN Hosting**: It calculates the exact difference (delta) and publishes a `delta_rules.json` file back to the `main` branch. 
5.  **Over-The-Air Updates**: The uShield Safari Extension periodically fetches this tiny delta file and merges it with its native baseline. Users get 100% up-to-date protection without ever needing to update the app from the App Store!

## 📜 Credits & License

The filter rules generated and hosted here are entirely sourced from the incredible open-source community:

*   **EasyList (Core & Privacy)**
*   **Fanboy's Lists (Annoyance & Social)**
*   **Regional Filters**: ABPVN (Vietnam), ABPindo (Indonesia), and many others.

All generated lists are distributed under the [Creative Commons Attribution-ShareAlike 3.0 / GPLv3 Licenses](https://github.com/easylist/easylist).

*Note: This repository does not contain the uShield iOS source code.*
