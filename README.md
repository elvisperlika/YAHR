# Yet Another HR

YAHR is your personal HR assistant. It analyzes your resume, finds the best job for you, and helps you improve your resume to get better job opportunities.

## Features

- Analyze your resume and find the best job for you
- Suggest the best way to improve your resume
- Provide you with the best job opportunities based on your resume

## Architecture

- PDF Parser Agent — extracts skills, experience, education from the CV PDF
- Job Searcher Agent — uses web search APIs (e.g. SerpAPI, Adzuna, LinkedIn scraping) to find open positions
- Matching/Ranker Agent — scores each job against the parsed CV profile
- Orchestrator Agent — coordinates all the above, driven by the CLI

## Dependencies

- MarkItDown
- Gemini models
- Typer
- Rich
- git+https://github.com/tensorflow/docs
  - ipython
  - jupyter
  - nbconvert
  - nbformat
  - nbqa
  - ruff
  - autoflake