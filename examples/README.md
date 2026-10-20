# BibMedEd API Example Notebook

## Overview

This notebook demonstrates the complete workflow of using the BibMedEd REST API to analyze a research corpus.

## Requirements

- Docker and Docker Compose installed
- Python 3.12+
- Jupyter Notebook

## Setup

1. Install the Python libraries:
```bash
   pip install requests pandas matplotlib jupyter
```

2. Start the API server:
```bash
   cd bibmeded
   docker compose up
```
- The server runs at http://localhost:8000
3. From the examples folder, Open this notebook in Jupyter:
```bash
   jupyter notebook sample_project_api.ipynb
```

## What the Notebook Shows

1. **Create or load the sample project** via POST `/api/projects/sample`
2. **Run analyses** via POST `/api/projects/{id}/analysis/{type}`:
   - Publications: yearly trends
   - Authors: top authors and co-authorship network
   - Keywords: keyword frequency
3. **Transform data** into pandas DataFrames
4. **Visualize** with matplotlib bar charts
5. **Export** the full dataset as a zip bundle

## Note

This example uses **synthetic sample data** bundled with BibMedEd. It does not require external API keys or internet access.
