# Yet Another HR

YAHR is a command-line tool that acts as your personal career co-pilot. It reads your resume, searches for relevant job openings, scores them against your profile, and tells you exactly how to improve your CV to maximize your chances — all from the terminal.

## Features

- Analyze your resume and find the best job for you
- Suggest the best way to improve your resume
- Provide you with the best job opportunities based on your resume

## Architecture

Built on the A2A Protocol (an open standard for agent-to-agent communication), YAHR is composed of four specialized agents that work together under a single orchestrator:

Job Searcher Agent — queries web search APIs to discover open positions matching your background
Matching/Ranker Agent — parses your CV into a structured profile and scores each job against it
CV Assistant Agent — analyzes the gaps between your profile and the top-ranked jobs, then gives you concrete suggestions to strengthen your resume
Orchestrator Agent — ties everything together and exposes the full workflow through an intuitive CLI interface

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