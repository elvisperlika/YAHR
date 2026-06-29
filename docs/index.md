# YAHR

![YAHR](image/logo.png)

Elvis Perlika

elvis.perlika@studio.unibo.it

# Abstract

YAHR (Yet Another HR) is a command-line tool that automates the job search from start to finish. It takes a resume in PDF form, converts it into a structured text profile, searches for matching open positions, scores each one against the candidate's background, and suggests concrete edits to the resume to better fit a chosen position. Everything happens in the terminal.

YAHR runs on the A2A (Agent-to-Agent) protocol, an open standard for communication between agents. Converting the resume is a separate command-line step; the rest of the work is split across three agents behind a single orchestrator. The Job Searcher finds openings, the Ranker scores them against the profile, and the CV Assistant compares the resume against a specific job and reports what to improve. The orchestrator reads each request, picks the agent that fits, and forwards the work. This report explains why YAHR exists, how it is built, and how the A2A protocol keeps its agents modular and loosely coupled.

# Domain

YAHR works in the domain of the job search: the process a person goes through to find work that fits them and to present themselves well enough to be called for an interview. Done by hand, this is slow, repetitive work. A candidate has to find openings across several sites, read each posting, judge how well it matches their background, and then decide whether and how to adjust their resume for the roles worth applying to. One resume rarely fits every posting equally well, so the tailoring has to be redone for each role.

YAHR treats this as a single-user problem. The only actor is the candidate, who runs the tool locally from the terminal and supplies one resume. There is no recruiter, no employer, and no shared account: every run is one person looking for work on their own machine. Keeping the domain this small lets the system treat the candidate's resume as the single source of truth about their background.

## Core Concepts

- Resume (or CV): the candidate's background, and the input to everything else. YAHR holds it as structured Markdown (a `# Name` heading, `##` sections, and bullets) produced by converting the source PDF. It is the only evidence the system may reason from; nothing reads in outside facts or invents experience that is not written down.
- Job (open position): one posting found for the candidate. Each has a stable id (used to drop duplicates across searches), a title, the hiring company, a location, the posting body, a link to apply, and, when listed, the gross annual salary. The posting body is the main text the system matches against.
- Query: what the candidate is looking for, in plain language. It can name a role and constraints such as location, salary, or contract type, and it can ask for a set number of results, as in "find 3 java jobs in Milan".
- Fit (score): how well a job matches the resume, on a scale from 0 to 100. Fit is judged on overlap: shared skills first, then relevant experience and seniority, then the role and domain, and finally any constraints the candidate stated.
- Gap: for one chosen job, a requirement the posting asks for that the resume does not clearly show. A gap is either something the candidate already has but worded poorly (reword) or something genuinely missing that they would need to acquire. The gap analysis pairs these with concrete edits to strengthen the resume for that specific job.

## Workflow

A full run moves through the domain in five stages. The PDF resume is converted into the Markdown profile. The candidate states a query. The system searches external job sources and gathers the matching openings. It scores each opening against the resume and ranks them best first. Finally, for a role the candidate cares about, it compares the resume against that posting and reports the gaps together with suggested edits. The candidate stays in control the whole way through: YAHR finds, scores, and advises, but it never applies on the candidate's behalf and never edits the resume itself.

# Design

## Component Diagram

### CLI Architecture

### Job Searcher Agent

### Ranker Agent

### CV Assistant Agent

# Tech Stack

# Code

# Testing

# Deployment

# Conclusion
