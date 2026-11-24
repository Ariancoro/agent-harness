# Repository

- Forja, Ariancoro's agent harness: skills, plugins and hooks that we publish for other projects to install.
- Paths:
  - Skills `.agents/skills/`.
  - Claude Code plugins `.claude/plugins/` and `.claude-plugin/`.
  - OpenSpec schemas `openspec/schemas/`.

# Skills

- When a skill is renamed, update every reference to it: `.claude-plugin/plugin.json`, `skills.sh.json`, `README.md` and other skills.

# Documentation

- Detailed conventions with examples live in `docs/`.
- When working on a task, use this map to find and read **only** the docs relevant to your task:

```
docs/
├── documentation-guidelines.md
└── skills/
    ├── plugin-registration.md
    └── skills-frontmatter.md
```
