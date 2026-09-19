---
type: llm
focus: last_message
weight: 1
---
The answer says spells of the old school are removed from characters' known spells (and from pinned spells if that key exists), because otherwise they would stay castable forever. It says this happens lazily when the character is loaded or rendered (not as a database migration), and that a spell is only removed if its document resolves and its school is identifiable and not practised.
