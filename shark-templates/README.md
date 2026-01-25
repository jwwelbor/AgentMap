# Shark CLI Templates

This directory contains templates for creating new epics, features, and tasks.

## Available Templates

### epic.md

Template for creating new epic files. Contains:
- YAML frontmatter with epic metadata
- Structured sections for goal, business value, quick reference
- Placeholders for epic components (personas, journeys, requirements, metrics, scope)

### feature.md

Template for creating new feature PRD files. Contains:
- YAML frontmatter with feature metadata
- Structured sections for goal, user personas, user stories, requirements
- Acceptance criteria, success metrics, dependencies, and integrations

### task.md

Template for creating new task files. Contains:
- YAML frontmatter with task metadata
- Structured sections for goals, success criteria, implementation guidance
- Validation gates and testing requirements

## Usage

Templates are automatically copied to your project's `shark-templates/` directory when you run:

```bash
shark init
```

To create new entities using templates:

**Epic**:
```bash
shark epic create --key=E01 --title="User Authentication System"
```

**Feature**:
```bash
shark feature create --epic=E01 --key=F01 --title="OAuth Login Integration"
```

**Task**:
```bash
shark task create "Build Login" --epic=E01 --feature=F01 --agent=backend
```

The creation commands will automatically populate the templates with the correct keys and metadata.

## Customization

You can customize these templates to match your team's workflow and documentation standards. After running `shark init`, edit the templates in your project's `shark-templates/` directory.
