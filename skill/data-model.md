# Data Model

## Categories

Paths are **dot-notation** (same as `create_category` / DB). Examples only — nothing is seeded automatically; create categories before `write_entry`.

```
tech
tech.servers
tech.programming
tech.programming.mycode
projects
projects.active
life
knowledge
archive
```

## Entry fields

```
id
title
keywords[]
description
content
importance_score
metadata
gitea_url
repo_visibility
repo_owner
```

## Relation types

`link_entries` accepts any non-empty string; Postgres stores it as given. Neo4j relationship **type** is the string **uppercased**, so use names that are valid as Cypher rel types (e.g. `depends_on` → `DEPENDS_ON`).

Presets understood by `find_pattern()` for filtering edges (substring match in the query string):

```
related_to  depends_on  used_by  part_of  supersedes
references  deployed_on  runs_on  owned_by  implements
```
