# Reproduce Relay

A skill project for interactive fiction / visual novel script generation.

## Overview

This project contains Claude Code skills for automating the expansion of skeleton scripts into production-ready interactive fiction dialogue. It takes outline spreadsheets with scene beats, choice branches, and placeholder dialogue, and generates complete scripts matching the game engine's exact row-by-row format.

## Project Structure

```
├── .gitignore
├── README.md
├── SKILLS-INDEX.md
├── data/                    # Work files (not versioned)
└── skills/
    └── interactive-fiction-writer/
        ├── SKILL.md         # Skill definition
        ├── scripts/         # Python scripts for the pipeline
        ├── references/      # Format specs and guides
        ├── templates/       # Prompt templates
        └── runs/            # Intermediate run data (not versioned)
```

## Usage

1. Place your skeleton `.xlsx` file in the `data/` directory
2. Invoke the `interactive-fiction-writer` skill
3. The skill will process the skeleton through a two-pass generation pipeline
4. Output is written back to an `.xlsx` file

## Skills

See [SKILLS-INDEX.md](SKILLS-INDEX.md) for available skills.

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) for running scripts
- Claude Code CLI
