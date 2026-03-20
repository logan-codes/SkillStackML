# SkillStack ML

A collaborative repository for trialling and comparing machine learning workflow systems and models for the use of verifying an certificate is real/fake for SkillStack project.

---

## Overview

This repository functions like a **kitchen with multiple chefs experimenting with recipes**. The `main` branch is the restaurant menu — it only lists what's available. The `deploy` branch is the kitchen actively cooking one dish at a time. And `dev` is the recipe archive where all past and present experiments live, organised and ready to be built upon.

Collaborators branch off from `dev`, add their own workflow system, and merge back — keeping everything organised and comparable.

---

## Branch Structure

```
main        ← README only. The entry point. You are here.
│
├── deploy  ← The active system currently in production/use. One system at a time.
│
└── dev     ← All experimental systems, each in its own folder.
    ├── system-a/
    ├── system-b/
    ├── your-new-system/
    └── ...
```

| Branch   | Purpose              | Contents                         |
| -------- | -------------------- | -------------------------------- |
| `main`   | Documentation hub    | This README only                 |
| `deploy` | Active deployment    | The single current system in use |
| `dev`    | Experimentation base | All systems as organised folders |

## How to Contribute a New System

Think of `dev` as a shared lab bench. You take your own section of the bench (a branch), set up your experiment, and when you're done, you return your notes to the shared bench (merge back to `dev`).

### Step-by-step

**1. Branch from `dev`**

```bash
git checkout dev
git pull origin dev
git checkout -b your-system-name
```

**2. Create a folder for your system**

Add your system under a clearly named directory:

```
dev/
└── your-system-name/
    ├── README.md        ← Describe your system, models used, and results
    ├── config/
    ├── models/
    └── pipeline/
```

**3. Develop and document your system**

Each system folder should include its own `README.md` covering:

- System description and objective
- ML model(s) used and configuration
- How to run the pipeline
- Results and observations

**4. Merge back to `dev`**

```bash
git add .
git commit -m "feat: add [your-system-name] workflow"
git push origin your-system-name
# Open a Pull Request → dev
```

---

## Promoting a System to Deploy

When a system from `dev` is selected as the active one, it is promoted to the `deploy` branch. The `deploy` branch reflects the **single system currently in use** — it is overwritten, not accumulated.

```bash
git checkout deploy
git checkout dev -- your-system-name/
# Restructure as needed, then push
git push origin deploy
```

> ⚠️ The `deploy` branch is not a history of all systems — it represents the **current winner**. All systems and their history live in `dev`.

---

## Repository Rules

- **Do not push directly to `main` or `deploy`** — changes go through `dev` first.
- **Always branch from `dev`**, not `main` or `deploy`.
- **Each system must live in its own folder** within `dev`.
- **Document your system** with a `README.md` inside your folder before merging.
- Pull Requests into `dev` require at least one reviewer.

---

## Folder Naming Convention

Use lowercase, hyphenated names that describe the system:

```
✅  bert-classification-pipeline/
✅  llm-rag-system-v2/
✅  xgboost-tabular-baseline/
❌  MySystem/
❌  test123/
❌  new_folder/
```

---

## Getting Started

```bash
# Clone the repo
git clone <repo-url>
cd <repo-name>

# Switch to dev to explore existing systems
git checkout dev

# See all available systems
ls
```
